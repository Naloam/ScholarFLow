from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TaskFamily = Literal["text_classification", "tabular_classification"]
BenchmarkKind = Literal["builtin", "remote_csv", "remote_jsonl", "remote_json"]


class BenchmarkSource(BaseModel):
    kind: BenchmarkKind = "builtin"
    name: str | None = None
    url: str | None = None
    task_family_hint: TaskFamily | None = None
    text_field: str | None = None
    label_field: str | None = None
    feature_fields: list[str] = Field(default_factory=list)
    split_field: str | None = None
    train_split_values: list[str] = Field(default_factory=lambda: ["train"])
    test_split_values: list[str] = Field(default_factory=lambda: ["test", "validation", "dev"])
    test_ratio: float = 0.3
    limit_rows: int | None = None


class AutoResearchRunRequest(BaseModel):
    topic: str
    task_family_hint: TaskFamily | None = None
    docker_image: str | None = None
    language: str = "en"
    paper_ids: list[str] | None = None
    max_rounds: int = 3
    benchmark: BenchmarkSource | None = None


class DatasetSpec(BaseModel):
    name: str
    description: str
    train_size: int
    test_size: int
    input_fields: list[str] = Field(default_factory=list)
    label_space: list[str] = Field(default_factory=list)


class BaselineSpec(BaseModel):
    name: str
    description: str


class MetricSpec(BaseModel):
    name: str
    goal: str
    description: str


class AblationSpec(BaseModel):
    name: str
    description: str


class ResearchPlan(BaseModel):
    topic: str
    title: str
    task_family: TaskFamily
    problem_statement: str
    motivation: str
    proposed_method: str
    research_questions: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    planned_contributions: list[str] = Field(default_factory=list)
    experiment_outline: list[str] = Field(default_factory=list)
    scope_limits: list[str] = Field(default_factory=list)


class ExperimentSpec(BaseModel):
    task_family: TaskFamily
    benchmark_name: str
    benchmark_description: str
    dataset: DatasetSpec
    baselines: list[BaselineSpec] = Field(default_factory=list)
    metrics: list[MetricSpec] = Field(default_factory=list)
    hypothesis: str
    ablations: list[AblationSpec] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    search_strategies: list[str] = Field(default_factory=list)


class SystemMetricResult(BaseModel):
    system: str
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None


class ResultTable(BaseModel):
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ResultArtifact(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    primary_metric: str
    best_system: str | None = None
    system_results: list[SystemMetricResult] = Field(default_factory=list)
    tables: list[ResultTable] = Field(default_factory=list)
    logs: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    objective_system: str | None = None
    objective_score: float | None = None


class LiteratureInsight(BaseModel):
    paper_id: str | None = None
    title: str
    year: int | None = None
    source: str | None = None
    insight: str
    method_hint: str | None = None
    gap_hint: str | None = None


class ExperimentAttempt(BaseModel):
    round_index: int
    strategy: str
    goal: str
    status: Literal["done", "failed"]
    summary: str
    critique: str | None = None
    code_path: str | None = None
    artifact: ResultArtifact | None = None


class AutoResearchRunRead(BaseModel):
    id: str
    project_id: str
    topic: str
    status: Literal["queued", "running", "done", "failed"]
    task_family: TaskFamily | None = None
    benchmark: BenchmarkSource | None = None
    plan: ResearchPlan | None = None
    spec: ExperimentSpec | None = None
    literature: list[LiteratureInsight] = Field(default_factory=list)
    attempts: list[ExperimentAttempt] = Field(default_factory=list)
    artifact: ResultArtifact | None = None
    generated_code_path: str | None = None
    paper_path: str | None = None
    paper_markdown: str | None = None
    paper_draft_version: int | None = None
    docker_image: str | None = None
    error: str | None = None
    selected_round_index: int | None = None
    created_at: datetime
    updated_at: datetime


class AutoResearchRunList(BaseModel):
    items: list[AutoResearchRunRead] = Field(default_factory=list)
