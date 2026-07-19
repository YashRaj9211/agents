"""Tool to analyze raw resume text into a structured profile via LLM."""
from __future__ import annotations

import json
from typing import Any

from llm.client import LlmClient
from tools.schemas import CandidateProfile

CATEGORY = "resume"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_resume",
        "description": "Analyzes raw resume text and extracts a structured CandidateProfile.",
        "parameters": {
            "type": "object",
            "properties": {
                "resume_text": {
                    "type": "string",
                    "description": "The plain text content of the candidate's resume."
                }
            },
            "required": ["resume_text"]
        }
    }
}


async def analyze_resume(resume_text: str) -> CandidateProfile:
    """Use the LLM to extract structured data from raw resume text."""
    client = LlmClient()
    
    # We ask the LLM to output a JSON object matching CandidateProfile schema
    schema = CandidateProfile.model_json_schema()
    
    prompt = (
        "You are an expert recruitment data extractor.\n"
        "Analyze the following resume text and extract the candidate's profile.\n"
        "Return a valid JSON object matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Resume text:\n"
        f"{resume_text}\n\n"
        "Provide ONLY the raw JSON string with no markdown wrappers or other text."
    )
    
    messages = [
        {"role": "system", "content": "You are a data extraction assistant. You output only valid JSON."},
        {"role": "user", "content": prompt}
    ]
    
    # Single-shot prompt, no tools
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
        return CandidateProfile(**data)
    except Exception as e:
        raise ValueError(f"Failed to parse LLM response into CandidateProfile: {e}\nRaw content: {content}") from e
