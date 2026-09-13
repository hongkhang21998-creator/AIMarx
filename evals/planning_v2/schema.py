"""Closed proposal contract for TRAIN-01; separate from the runtime and planning-v1."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(min_length=1, max_length=2000, pattern=r"\S")]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,47}$")]
Version = Annotated[int, Field(strict=True, ge=1, le=2**31-1)]
WORKER_OUTPUTS = {
    "extract": "facts-v1", "ask_user": "question-v1",
    "draft": "draft-v1", "verify": "review-v1",
}


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceRef(Closed):
    source_id: Id
    version: Version
    block_id: Id

    def key(self) -> tuple[str, int, str]:
        return self.source_id, self.version, self.block_id


class Source(SourceRef):
    text: Annotated[str, StringConstraints(min_length=1, max_length=16000, pattern=r"\S")]
    classification: Literal["public", "synthetic", "internal", "restricted", "unknown"]


class PlanningInput(Closed):
    request: Text
    as_of: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+07:00$")]
    sources: Annotated[list[Source], Field(max_length=32)]

    @model_validator(mode="after")
    def unique_sources(self):
        from datetime import datetime
        datetime.fromisoformat(self.as_of)
        keys = [s.key() for s in self.sources]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate source identity")
        versions: dict[str, int] = {}
        for source in self.sources:
            if source.source_id in versions and versions[source.source_id] != source.version:
                raise ValueError("multiple versions of one source")
            versions[source.source_id] = source.version
        return self


class Citation(SourceRef):
    quote: Text


class OutputRef(Closed):
    step_id: Id
    output_schema_id: Literal["facts-v1", "question-v1", "draft-v1", "review-v1"]


class Step(Closed):
    id: Id
    goal: Text
    worker_id: Literal["extract", "ask_user", "draft", "verify"]
    depends_on: Annotated[list[Id], Field(max_length=5)]
    source_refs: Annotated[list[SourceRef], Field(max_length=32)]
    input_refs: Annotated[list[OutputRef], Field(max_length=5)]
    output_schema_id: Literal["facts-v1", "question-v1", "draft-v1", "review-v1"]
    completion_checks: Annotated[list[Text], Field(min_length=1, max_length=6)]


class Proposal(Closed):
    schema_version: Literal["proposal-v2"]
    decision: Literal["plan", "ask", "no_action", "out_of_scope"]
    requested_product: Text
    evidence_quotes: Annotated[list[Citation], Field(max_length=32)]
    missing_information: Annotated[list[Text], Field(max_length=12)]
    steps: Annotated[list[Step], Field(max_length=6)]

    @model_validator(mode="after")
    def sequence(self):
        if self.decision in ("no_action", "out_of_scope"):
            if self.steps or self.missing_information:
                raise ValueError("terminal decision must have no steps or questions")
        elif self.decision == "ask":
            if (not self.missing_information or len(self.steps) != 1
                    or self.steps[0].worker_id != "ask_user"):
                raise ValueError("ask must stop at one ask_user step with missing information")
        elif (not self.steps or self.missing_information
              or any(s.worker_id == "ask_user" for s in self.steps)):
            raise ValueError("plan requires steps and no unresolved questions")

        seen: dict[str, Step] = {}
        for step in self.steps:
            if step.id in seen:
                raise ValueError("duplicate step id")
            if WORKER_OUTPUTS[step.worker_id] != step.output_schema_id:
                raise ValueError("worker/output contract mismatch")
            if len(set(step.depends_on)) != len(step.depends_on):
                raise ValueError("duplicate dependency")
            if any(dep not in seen for dep in step.depends_on):
                raise ValueError("dependency must precede step (no self, cycle or forward reference)")
            # Explicit chain: a backend must not interpret independent steps as parallel jobs.
            if seen and next(reversed(seen)) not in step.depends_on:
                raise ValueError("each step must wait for the immediately preceding step")
            refs = [r.key() for r in step.source_refs]
            if len(set(refs)) != len(refs):
                raise ValueError("duplicate step source reference")
            output_ids = [r.step_id for r in step.input_refs]
            if len(set(output_ids)) != len(output_ids):
                raise ValueError("duplicate output reference")
            for ref in step.input_refs:
                if (ref.step_id not in step.depends_on
                        or seen[ref.step_id].output_schema_id != ref.output_schema_id):
                    raise ValueError("input output must match a declared earlier dependency")
            seen[step.id] = step
        quotes = [(q.key(), q.quote) for q in self.evidence_quotes]
        if len(set(quotes)) != len(quotes):
            raise ValueError("duplicate citation")
        return self
