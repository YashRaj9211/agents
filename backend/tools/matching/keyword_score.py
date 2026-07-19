"""Fast keyword-overlap scoring to act as a first-pass filter before sending jobs to the LLM."""
from __future__ import annotations

import re

CATEGORY = "matching"

SCHEMA = {
    "type": "function",
    "function": {
        "name": "keyword_score",
        "description": "Calculates a fast 0.0-1.0 keyword overlap score between a profile and a job.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills from the candidate profile."
                },
                "job_text": {
                    "type": "string",
                    "description": "The job description text."
                }
            },
            "required": ["profile_skills", "job_text"]
        }
    }
}


def keyword_score(profile_skills: list[str], job_text: str) -> float:
    """
    Very simple, fast keyword matching.
    In a real app, you'd replace this with sentence-transformers or NIM embeddings.
    """
    if not profile_skills or not job_text:
        return 0.0

    job_text_lower = job_text.lower()
    # tokenize job text roughly to avoid partial matches inside words if possible, 
    # but since skills can be multi-word, simple string presence check is safer for now.
    
    matches = 0
    for skill in profile_skills:
        # Check if the skill appears as a word boundary
        skill_lower = skill.lower()
        if re.search(r'\b' + re.escape(skill_lower) + r'\b', job_text_lower):
            matches += 1
            
    return matches / len(profile_skills)
