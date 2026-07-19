"""LLM-based job scoring tool."""
from __future__ import annotations

import json
from typing import Any

from llm.client import LlmClient
from tools.schemas import CandidateProfile, MatchResult

CATEGORY = "matching"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "score_job_match",
        "description": "Uses LLM judgment to score a job posting against a candidate profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "description": "The CandidateProfile dictionary."
                },
                "job_url": {
                    "type": "string",
                    "description": "URL of the job."
                },
                "job_description": {
                    "type": "string",
                    "description": "The full text of the job description."
                },
                "match_threshold": {
                    "type": "integer",
                    "description": "Minimum score (0-100) to consider it a match."
                }
            },
            "required": ["profile", "job_url", "job_description", "match_threshold"]
        }
    }
}


async def score_job_match(
    profile: dict[str, Any], 
    job_url: str, 
    job_description: str, 
    match_threshold: int
) -> MatchResult:
    """Use LLM to deeply analyze job fit, weighing requirements and seniority."""
    client = LlmClient()
    
    schema = MatchResult.model_json_schema()
    
    # Exclude job_url, is_above_threshold from the prompt since we inject it manually
    prompt = (
        "You are an expert recruiter evaluating a candidate for a job.\n"
        "Carefully read the candidate profile and the job description.\n"
        "1. Check if the candidate's experience level matches the seniority required.\n"
        "2. Evaluate overlap with REQUIRED skills, not just nice-to-have.\n"
        "3. Provide a score from 0 to 100.\n"
        "4. Provide a 2-3 sentence rationale.\n\n"
        "Return a valid JSON object matching this schema (omitting job_url and is_above_threshold):\n"
        '{"type": "object", "properties": {"score": {"type": "integer"}, "rationale": {"type": "string"}}}\n\n'
        f"Candidate Profile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Job Description:\n{job_description}\n\n"
        "Provide ONLY the raw JSON string with no markdown wrappers."
    )
    
    messages = [
        {"role": "system", "content": "You are a recruitment scoring assistant. You output only valid JSON."},
        {"role": "user", "content": prompt}
    ]
    
    message = await client.decide(messages=messages, tools=[])
    content = message.content or ""
    
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    try:
        data = json.loads(content)
        score = data.get("score", 0)
        return MatchResult(
            job_url=job_url,
            score=score,
            rationale=data.get("rationale", "No rationale provided."),
            is_above_threshold=(score >= match_threshold)
        )
    except Exception as e:
        return MatchResult(
            job_url=job_url,
            score=0,
            rationale=f"Failed to parse LLM response: {e}\nRaw content: {content}",
            is_above_threshold=False
        )
