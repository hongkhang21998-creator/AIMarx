"""Fail-closed contract for the local-orchestrator / remote-inference workflow.

The local service owns original files, tools, evidence and approval.  A remote
model worker receives only bounded text fragments and returns an untrusted
proposal whose citations are checked locally.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class AgentId(StrEnum):
    INTAKE = "intake"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    DRAFTING = "drafting"
    FORMAT_REVIEW = "format_review"
    EVIDENCE_REVIEW = "evidence_review"
    RISK_REVIEW = "risk_review"
    FINALIZER = "finalizer"


REVIEW_AGENTS = frozenset(
    {AgentId.FORMAT_REVIEW, AgentId.EVIDENCE_REVIEW, AgentId.RISK_REVIEW}
)


class LocalFragment(BaseModel):
    """Text selected locally; never a filename, path or binary attachment."""

    model_config = ConfigDict(extra="forbid")
    fragment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: StrictInt = Field(ge=1)
    page: StrictInt | None = Field(default=None, ge=1)
    text: str = Field(min_length=1, max_length=4000)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9._:-]{1,120}$")
    fragment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    quote: str = Field(min_length=1, max_length=2000)
    verified: StrictBool


class InferencePacket(BaseModel):
    """Only object that an agent may submit to the model gateway."""

    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(pattern=r"^TASK-[A-Za-z0-9._:-]{1,120}$")
    agent_id: AgentId
    model_profile: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=64)
    fragments: list[LocalFragment] = Field(default_factory=list, max_length=20)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=40)
    output_schema_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,63}$")
    max_output_tokens: StrictInt = Field(ge=1, le=1024)
    temperature_milli: StrictInt = Field(ge=0, le=2000)

    @model_validator(mode="after")
    def evidence_is_local_and_exact(self):
        fragments = {item.fragment_id: item.text for item in self.fragments}
        if len(fragments) != len(self.fragments):
            raise ValueError("duplicate fragment_id")
        source_ids = {item.source_id for item in self.evidence}
        if len(source_ids) != len(self.evidence):
            raise ValueError("duplicate source_id")
        for item in self.evidence:
            if not item.verified:
                raise ValueError("unverified evidence cannot leave localhost")
            if item.fragment_id not in fragments or item.quote not in fragments[item.fragment_id]:
                raise ValueError("evidence is not bound to an exact local fragment")
        return self


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


class AgentResult(BaseModel):
    """Untrusted remote output.  It never contains an approval field."""

    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(pattern=r"^TASK-[A-Za-z0-9._:-]{1,120}$")
    agent_id: AgentId
    findings: list[Finding] = Field(default_factory=list, max_length=50)
    uncertainties: list[str] = Field(default_factory=list, max_length=30)
    blocking_errors: list[str] = Field(default_factory=list, max_length=30)
    proposed_output: str | None = Field(default=None, max_length=12000)


class TrainingExample(BaseModel):
    """A reviewed example; eligibility is computed locally, never by an agent."""

    model_config = ConfigDict(extra="forbid")
    packet: InferencePacket
    result: AgentResult
    human_status: str = Field(pattern=r"^(pending|approved|rejected)$")
    training_approved: StrictBool = False
    export_approved: StrictBool = False

    @model_validator(mode="after")
    def bind_run(self):
        if self.packet.task_id != self.result.task_id:
            raise ValueError("result belongs to another task")
        if self.packet.agent_id != self.result.agent_id:
            raise ValueError("result belongs to another agent")
        return self

    @property
    def eligible_for_training(self) -> bool:
        return (
            self.human_status == "approved"
            and self.training_approved
            and self.export_approved
        )


def validate_result(packet: InferencePacket, result: AgentResult) -> None:
    """Bind a remote result to its request and reject invented citations."""
    if result.task_id != packet.task_id or result.agent_id != packet.agent_id:
        raise ValueError("remote result is not bound to this inference packet")
    known = {item.source_id for item in packet.evidence}
    for finding in result.findings:
        if not finding.source_ids or any(source_id not in known for source_id in finding.source_ids):
            raise ValueError("finding lacks valid local evidence")


def ready_agents(completed: set[AgentId]) -> tuple[AgentId | str, ...]:
    """Deterministic eight-agent graph; the terminal action is human review."""
    if AgentId.INTAKE not in completed:
        return (AgentId.INTAKE,)
    if AgentId.RESEARCH not in completed:
        return (AgentId.RESEARCH,)
    if AgentId.ANALYSIS not in completed:
        return (AgentId.ANALYSIS,)
    if AgentId.DRAFTING not in completed:
        return (AgentId.DRAFTING,)
    pending_reviews = tuple(agent for agent in REVIEW_AGENTS if agent not in completed)
    if pending_reviews:
        return tuple(sorted(pending_reviews, key=str))
    if AgentId.FINALIZER not in completed:
        return (AgentId.FINALIZER,)
    return ("human_review",)
