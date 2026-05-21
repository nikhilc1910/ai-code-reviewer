"""Pydantic schemas for structured review output."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICE = "best_practice"


CONFIDENCE_VERIFY_THRESHOLD = 60


class ReviewComment(BaseModel):
    file_path: str
    line_start: int = Field(ge=1)
    line_end: Optional[int] = None
    symbol_name: Optional[str] = None
    severity: Severity
    category: Category
    message: str
    suggestion: Optional[str] = None
    confidence: int = Field(ge=0, le=100)

    @field_validator("line_end", mode="before")
    @classmethod
    def default_line_end(cls, v: Optional[int], info) -> Optional[int]:
        if v is None and "line_start" in info.data:
            return info.data["line_start"]
        return v

    @property
    def needs_verification(self) -> bool:
        return self.confidence < CONFIDENCE_VERIFY_THRESHOLD

    @property
    def confidence_bucket(self) -> str:
        if self.confidence >= 80:
            return "high"
        if self.confidence >= CONFIDENCE_VERIFY_THRESHOLD:
            return "medium"
        return "low"


class ReviewBatch(BaseModel):
    repo_url: str
    comments: list[ReviewComment] = Field(default_factory=list)
    files_analyzed: int = 0
    chunks_reviewed: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def high_confidence(self) -> list[ReviewComment]:
        return [c for c in self.comments if c.confidence_bucket == "high"]

    @property
    def medium_confidence(self) -> list[ReviewComment]:
        return [c for c in self.comments if c.confidence_bucket == "medium"]

    @property
    def low_confidence(self) -> list[ReviewComment]:
        return [c for c in self.comments if c.confidence_bucket == "low"]


class CodeChunk(BaseModel):
    file_path: str
    language: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None  # function | class | module_fragment
    line_start: int
    line_end: int
    source: str
    imports: list[str] = Field(default_factory=list)
