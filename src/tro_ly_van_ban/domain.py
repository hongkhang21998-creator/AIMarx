from pydantic import BaseModel, ConfigDict, Field


class EvidenceValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=2000)
    block_id: str
    quote: str = Field(min_length=1, max_length=4000)


class TaskProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: EvidenceValue
    deadline: EvidenceValue | None = None


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: EvidenceValue | None = None
    agency: EvidenceValue | None = None
    document_date: EvidenceValue | None = None
    tasks: list[TaskProposal] = Field(default_factory=list, max_length=30)
    missing: list[str] = Field(default_factory=list, max_length=30)


def validate_evidence(extraction: Extraction, blocks: list[dict]) -> None:
    sources = {b["id"]: b["text"] for b in blocks}
    values = [extraction.number, extraction.agency, extraction.document_date]
    for task in extraction.tasks:
        values.extend([task.request, task.deadline])
    for item in filter(None, values):
        # Extractive fields only: the source must contain the exact quote and value.
        # This does not prove semantic classification; a person reviews that next.
        if item.block_id not in sources or item.quote not in sources[item.block_id] or item.value not in item.quote:
            raise ValueError("Dữ kiện không có trích đoạn nguyên văn hợp lệ")
