"""Shared Pydantic models for tools and skills."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """Extracted and structured candidate profile."""
    name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    skills: list[str] = Field(description="List of technical and soft skills")
    experience: list[dict[str, Any]] = Field(description="Work experience entries")
    education: list[dict[str, Any]] = Field(description="Education entries")
    target_roles: list[str] = Field(description="Job titles the candidate is targeting")


class JobPosting(BaseModel):
    """Information about a specific job posting."""
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    url: str = Field(description="URL to the job posting")
    location: str = Field(description="Job location")
    description: str = Field(description="Full job description text", default="")
    requirements: list[str] = Field(description="Key requirements", default_factory=list)
    posted_date: str = Field(description="Date posted", default="")


class MatchResult(BaseModel):
    """Result of scoring a job against a profile."""
    job_url: str = Field(description="The job URL")
    score: int = Field(description="Match score from 0 to 100")
    rationale: str = Field(description="Explanation for the score, weighing requirements and seniority")
    is_above_threshold: bool = Field(description="True if score >= configured threshold")


class SkillStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SkillResult(BaseModel):
    """Final output from running a skill."""
    status: SkillStatus
    summary: str = Field(description="High-level summary of what happened")
    jobs_processed: int = Field(default=0, description="Number of jobs evaluated")
    jobs_applied: int = Field(default=0, description="Number of applications submitted (or staged in dry_run)")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
