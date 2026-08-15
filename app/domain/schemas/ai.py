"""
AI Integration Pydantic Schemas
===============================
Request and response models for AI Issue Generator, AI Sprint Planner,
AI Documentation Generator, AI Bug Analysis, and AI Project Summary.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. AI ISSUE GENERATOR
# ---------------------------------------------------------------------------

class GeneratedIssueItem(BaseModel):
    title: str = Field(..., description="Generated issue title")
    description: str = Field(..., description="Detailed markdown description")
    priority: str = Field("MEDIUM", description="Issue priority: LOW, MEDIUM, HIGH, URGENT")
    status: str = Field("TODO", description="Target initial status")
    subtasks: List[str] = Field(default_factory=list, description="Subtask titles")


class AIIssueGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="Natural language task or feature prompt")
    count: int = Field(3, ge=1, le=10, description="Number of issues to generate")


class AIIssueGenerateResponse(BaseModel):
    prompt: str
    generated_issues: List[GeneratedIssueItem]
    summary: str


# ---------------------------------------------------------------------------
# 2. AI SPRINT PLANNER
# ---------------------------------------------------------------------------

class AISprintPlanRequest(BaseModel):
    sprint_name: str = Field(..., description="Name of target sprint e.g. 'Sprint 14'")
    sprint_goal: str = Field(..., description="Target sprint objective or theme")
    capacity_issues: int = Field(5, ge=1, le=20, description="Target issue capacity")


class SprintAllocationItem(BaseModel):
    issue_id: str
    identifier: str
    title: str
    priority: str
    reason: str


class AISprintPlanResponse(BaseModel):
    sprint_name: str
    sprint_goal: str
    recommended_issues: List[SprintAllocationItem]
    capacity_used: int
    rationale: str
    risk_assessment: str


# ---------------------------------------------------------------------------
# 3. AI DOCUMENTATION GENERATOR
# ---------------------------------------------------------------------------

class AIDocumentationRequest(BaseModel):
    doc_type: str = Field("README", description="Documentation type: README, ARCHITECTURE, API, RELEASE_NOTES")
    additional_notes: Optional[str] = Field(None, description="Custom guidelines or context")


class AIDocumentationResponse(BaseModel):
    doc_type: str
    title: str
    content_markdown: str


# ---------------------------------------------------------------------------
# 4. AI BUG ANALYSIS
# ---------------------------------------------------------------------------

class AIBugAnalysisRequest(BaseModel):
    issue_id: Optional[str] = Field(None, description="Target issue ID")
    bug_title: str = Field(..., description="Title or summary of the bug")
    bug_description: str = Field(..., description="Bug description or symptoms")
    stack_trace: Optional[str] = Field(None, description="Error log or stack trace")


class AIBugAnalysisResponse(BaseModel):
    bug_title: str
    root_cause_explanation: str
    severity: str
    reproduction_steps: List[str]
    suggested_fix_description: str
    code_fix_snippet: Optional[str] = None


# ---------------------------------------------------------------------------
# 5. AI PROJECT SUMMARY
# ---------------------------------------------------------------------------

class AIProjectSummaryRequest(BaseModel):
    period_days: int = Field(14, ge=1, le=90, description="Time window in days")


class AIProjectSummaryResponse(BaseModel):
    project_id: str
    project_name: str
    total_issues: int
    completed_issues: int
    progress_percentage: float
    executive_summary: str
    key_accomplishments: List[str]
    identified_risks: List[str]
    recommendations: List[str]
