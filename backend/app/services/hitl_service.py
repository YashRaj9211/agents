"""
Human-in-the-loop (HITL) request registry.

Why this exists
---------------
An agent sometimes must ask the user something before it can continue: confirming
a destructive command, picking between alternatives, or supplying information the
model cannot infer. ADK 2.5 has no built-in suspend/resume hook for
``runner.run_async``, so questions are modelled as an ordinary tool call that
blocks:

* the ``ask_user`` tool (:mod:`tools.hitl_tools.ask_user`) publishes a
  ``human_input_request`` event on the run's replayable event buffer,
* the tool then *awaits* an :class:`asyncio.Future` held here,
* ``POST /api/hitl/{question_id}/answer`` resolves that future, which unsticks the
  agent inside the same task -- so the run continues on its original SSE stream
  and the waiting costs no extra turn.

Awaiting a future (as opposed to a blocking sleep) is what keeps this safe: the
event loop stays free, so the run's heartbeats keep flowing and other sessions
keep working while one run waits on a human.

State is deliberately in-memory. Runs themselves are process-local and a restart
already marks leftovers ``interrupted`` (see ``app.main.lifespan``), so a
persisted question would outlive the agent that asked it.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.services.hitl")

#: Question shapes the UI knows how to render.
HITL_KINDS = ("confirm", "choice", "multi_choice", "text")

#: Bindings accepted for a ``confirm`` question, mapped to a yes/no answer.
_AFFIRMATIVE = {"yes", "y", "true", "1", "ok", "okay", "approve", "approved", "confirm", "proceed"}
_NEGATIVE = {"no", "n", "false", "0", "deny", "denied", "cancel", "reject", "stop"}


class HumanInputError(RuntimeError):
    """Raised for an unknown, expired or already-answered question."""


@dataclass
class PendingHumanInput:
    """One unanswered question, plus the future the asking tool is blocked on."""

    question_id: str
    session_id: str
    run_id: Optional[str]
    agent_id: Optional[str]
    kind: str
    question: str
    options: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    future: Optional[asyncio.Future] = field(default=None, repr=False)

    def summary(self) -> Dict[str, Any]:
        """JSON-safe shape for the HTTP endpoint (never exposes the future)."""
        return {
            "question_id": self.question_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "kind": self.kind,
            "question": self.question,
            "options": self.options,
            "created_at": self.created_at,
        }

    @property
    def answered(self) -> bool:
        return bool(self.future is not None and self.future.done())


def normalize_options(options: Any) -> List[Dict[str, str]]:
    """Coerces model-supplied options into ``[{label, value, description?}]``.

    The model may pass plain strings, dicts, or a mix of both; a stable shape
    keeps the React card simple and lets the answer post back the *value* rather
    than a display label.
    """
    if not options:
        return []
    if isinstance(options, dict):
        options = [options]
    if isinstance(options, str):
        options = [options]

    normalized: List[Dict[str, str]] = []
    for entry in options:
        if isinstance(entry, dict):
            label = str(entry.get("label") or entry.get("value") or "").strip()
            if not label:
                continue
            item = {
                "label": label,
                "value": str(entry.get("value") or label),
            }
            description = entry.get("description")
            if description:
                item["description"] = str(description)
            normalized.append(item)
        else:
            label = str(entry).strip()
            if label:
                normalized.append({"label": label, "value": label})
    return normalized[:12]


def coalesce_answer(kind: str, raw: Any, options: List[Dict[str, str]]) -> Any:
    """Validates/normalizes a posted answer against the question's kind."""
    if kind == "multi_choice":
        if isinstance(raw, (list, tuple, set)):
            values = [str(v) for v in raw]
        elif raw is None:
            values = []
        else:
            # A single value is still a valid (one-item) multi-select.
            values = [str(raw)]
        allowed = {o["value"] for o in options} | {o["label"] for o in options}
        accepted = [v for v in values if not allowed or v in allowed]
        if values and not accepted:
            raise HumanInputError("None of the submitted options are valid for this question")
        return accepted

    if raw is None:
        return ""

    if kind == "confirm":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in _AFFIRMATIVE:
            return True
        if text in _NEGATIVE:
            return False
        raise HumanInputError(f"Expected a yes/no answer, received {raw!r}")

    if kind == "choice":
        value = str(raw)
        allowed = {o["value"] for o in options} | {o["label"] for o in options}
        if allowed and value not in allowed:
            raise HumanInputError(f"{value!r} is not one of this question's options")
        return value

    # Free text: anything the user typed is a fair answer.
    return str(raw)


def render_answer(kind: str, answer: Any, options: List[Dict[str, str]]) -> str:
    """Human-readable rendering handed back to the model."""
    if kind == "confirm":
        return "Yes" if answer else "No"
    if kind == "multi_choice" and isinstance(answer, list):
        labels = []
        for value in answer:
            match = next(
                (o["label"] for o in options if value in (o["value"], o["label"])),
                value,
            )
            labels.append(str(match))
        return ", ".join(labels) if labels else "(none selected)"
    if kind == "choice":
        match = next(
            (o["label"] for o in options if answer in (o["value"], o["label"])),
            answer,
        )
        return str(match)
    return str(answer)


class HumanInputService:
    """Process-wide registry of outstanding questions."""

    def __init__(self) -> None:
        self._pending: Dict[str, PendingHumanInput] = {}
        #: session_id -> question_ids, so a reloaded page can find its card again.
        self._by_session: Dict[str, List[str]] = {}

    # ───────── creation ─────────
    def create_request(
        self,
        *,
        session_id: str,
        question: str,
        kind: str = "confirm",
        options: Any = None,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> PendingHumanInput:
        """Registers a question and returns it unresolved.

        The caller publishes the matching ``human_input_request`` event and then
        awaits :meth:`wait`, so the question exists in both the run's event buffer
        (for replay) and this registry (for the answer endpoint).
        """
        normalized_kind = (kind or "confirm").strip().lower()
        if normalized_kind not in HITL_KINDS:
            logger.warning("Unknown HITL kind %r, falling back to 'text'", kind)
            normalized_kind = "text"

        normalized_options = (
            normalize_options(options) if normalized_kind in {"choice", "multi_choice"} else []
        )
        if normalized_kind in {"choice", "multi_choice"} and not normalized_options:
            raise HumanInputError(
                f"An {normalized_kind!r} question needs at least one option"
            )

        record = PendingHumanInput(
            question_id=str(uuid.uuid4()),
            session_id=str(session_id),
            run_id=str(run_id) if run_id else None,
            agent_id=agent_id,
            kind=normalized_kind,
            question=str(question or "").strip() or "The agent needs your input to continue.",
            options=normalized_options,
            future=asyncio.get_running_loop().create_future(),
        )

        self._pending[record.question_id] = record
        self._by_session.setdefault(record.session_id, []).append(record.question_id)
        logger.info(
            "HITL question %s (%s) opened for session %s run %s",
            record.question_id,
            record.kind,
            record.session_id,
            record.run_id,
        )
        return record

    # ───────── lookup ─────────
    def get(self, question_id: str) -> Optional[PendingHumanInput]:
        return self._pending.get(str(question_id))

    def pending_for_session(self, session_id: str) -> List[PendingHumanInput]:
        ids = self._by_session.get(str(session_id), [])
        return [self._pending[i] for i in ids if i in self._pending]

    def pending_for_run(self, run_id: str) -> List[PendingHumanInput]:
        target = str(run_id)
        return [p for p in self._pending.values() if p.run_id == target]

    def any_pending(self) -> bool:
        return bool(self._pending)

    # ───────── resolution ─────────
    def resolve(self, question_id: str, raw_answer: Any) -> PendingHumanInput:
        """Answers a question exactly once. Raises :class:`HumanInputError` otherwise."""
        record = self.get(question_id)
        if record is None:
            raise HumanInputError(f"Question {question_id!r} is not pending (expired or already answered)")

        answer = coalesce_answer(record.kind, raw_answer, record.options)
        text = render_answer(record.kind, answer, record.options)

        if record.future is not None and not record.future.done():
            # ``set_result`` hands the agent the rendered answer; it unblocks the
            # awaiting ``ask_user`` call inside the run's own task.
            record.future.set_result(
                {
                    "status": "answered",
                    "answer": text,
                    "raw_answer": answer,
                    "kind": record.kind,
                }
            )

        self._forget(question_id)
        logger.info("HITL question %s answered with %r", question_id, text)
        return record

    def expire(self, question_id: str, reason: str = "timeout") -> None:
        """Resolves a question as unanswered (timeout) without raising."""
        record = self._pending.get(str(question_id))
        if record is None:
            return
        if record.future is not None and not record.future.done():
            record.future.set_result({"status": reason, "answer": "", "raw_answer": None})
        self._forget(record.question_id)
        logger.info("HITL question %s closed: %s", question_id, reason)

    def fail_all(self, session_id: str, reason: str = "cancelled") -> int:
        """Closes every question a session still has open.

        Called when a run is stopped so that a cancelled run does not leave a
        dangling card in the UI, and so the registry cannot leak entries.
        """
        affected = self.pending_for_session(session_id)
        for record in affected:
            if record.future is not None and not record.future.done():
                record.future.set_result({"status": reason, "answer": "", "raw_answer": None})
            self._forget(record.question_id)
        if affected:
            logger.info("Closed %d pending HITL question(s) for session %s (%s)", len(affected), session_id, reason)
        return len(affected)

    def _forget(self, question_id: str) -> None:
        record = self._pending.pop(str(question_id), None)
        if record is None:
            return
        ids = self._by_session.get(record.session_id)
        if not ids:
            return
        remaining = [i for i in ids if i != record.question_id]
        if remaining:
            self._by_session[record.session_id] = remaining
        else:
            self._by_session.pop(record.session_id, None)


#: Module-level singleton, mirroring ``get_run_manager()``.
_human_input_service = HumanInputService()


def get_hitl_service() -> HumanInputService:
    """Returns the process-wide HITL registry."""
    return _human_input_service


def reset_hitl_service() -> None:
    """Drops all pending questions. Test helper only."""
    _human_input_service._pending.clear()  # noqa: SLF001 - intentional test reset
    _human_input_service._by_session.clear()  # noqa: SLF001
