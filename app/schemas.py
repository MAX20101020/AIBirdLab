from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    bird_name: str
    confidence: float | None
    analyzed_at: datetime
    description: str | None = None
    source_details: str | None = None


class SpeciesStat(BaseModel):
    label: str
    count: int


class StatisticsOut(BaseModel):
    record_count: int
    species: list[SpeciesStat]
    highest: list[AnalysisOut]
    lowest: list[AnalysisOut]
    same_confidence: bool


class AnalysisResult(BaseModel):
    predictions: list[dict[str, Any]]
    saved: AnalysisOut | None


class DeleteResult(BaseModel):
    removed: int