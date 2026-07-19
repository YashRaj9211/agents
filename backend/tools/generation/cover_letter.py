"""Tool to generate a tailored cover letter using the LLM."""
from __future__ import annotations

import json
from typing import Any

from llm.client import LlmClient

CATEGORY = "generation"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_cover_letter",
        "description": "Generates a tailored cover letter based on a candidate profile and job description.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "description": "The candidate profile."
                },
                "job_description": {
                    "type": "string",
                    "description": "The job description text."
                }
            },
            "required": ["profile", "job_description"]
        }
    }
}


async def generate_cover_letter(profile: dict[str, Any], job_description: str) -> str:
    """Uses LLM to write a cover letter."""
    client = LlmClient()
    
    prompt = (
        "You are an expert career coach writing a cover letter for a candidate.\n"
        "Using the candidate profile and the job description, write a compelling, "
        "professional, and concise cover letter (max 3-4 paragraphs).\n"
        "Do not invent experience. Emphasize the intersection of their actual skills "
        "and the job's core requirements.\n\n"
        f"Candidate Profile:\n{json.dumps(profile, indent=2)}\n\n"
        f"Job Description:\n{job_description}\n\n"
        "Return ONLY the cover letter text, ready to be pasted into a text box or saved as a file."
    )
    
    messages = [
        {"role": "system", "content": "You are a professional cover letter writer. Output only the letter text."},
        {"role": "user", "content": prompt}
    ]
    
    message = await client.decide(messages=messages, tools=[])
    
    # Check if blocked or failed
    if not message.content or message.content.startswith("BLOCKED:"):
        return f"Failed to generate cover letter: {message.content}"
        
    return message.content.strip()
