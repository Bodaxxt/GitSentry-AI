# schemas.py — Pydantic Output Schemas for GitSentry AI
# Defines the structured data models for code review results.

from pydantic import BaseModel, Field
from typing import Literal, List


class CodeIssue(BaseModel):
    """Represents a single identified bug, vulnerability, or code smell."""

    file: str = Field(
        description="The name of the source file where the issue was found."
    )
    issue: str = Field(
        description="A concise, one-line summary of the bug or vulnerability (e.g., 'SQL Injection via unsanitized input')."
    )
    severity: Literal["Low", "Medium", "High", "Critical"] = Field(
        description=(
            "The severity level of the issue. Must be exactly one of: "
            "'Low' (minor code smell), 'Medium' (potential bug), "
            "'High' (security risk or data loss), 'Critical' (exploitable vulnerability)."
        )
    )
    explanation: str = Field(
        description=(
            "A detailed technical explanation of why this is an issue, its potential impact, "
            "and any relevant references (e.g., OWASP Top 10, CWE IDs, performance implications)."
        )
    )
    suggested_fix: str = Field(
        description=(
            "The corrected, production-ready code snippet that should replace the buggy code. "
            "Include only the relevant fixed section, properly indented."
        )
    )


class ReviewReport(BaseModel):
    """The complete code review report for a single file."""

    summary: str = Field(
        description=(
            "A high-level executive summary of the overall code quality, "
            "listing the total number of issues found and their distribution by severity."
        )
    )
    issues: List[CodeIssue] = Field(
        description="A list of all identified issues, ordered from most critical to least critical.",
        default_factory=list,
    )
