import pytest
from pydantic import ValidationError

from tro_ly_van_ban.agent_workflow import (
    AgentId,
    AgentResult,
    InferencePacket,
    TrainingExample,
    ready_agents,
    validate_result,
)


DOC = "a" * 64


def packet(**changes):
    data = {
        "task_id": "TASK-001",
        "agent_id": "research",
        "model_profile": "aimarx-qwen25-3b",
        "prompt_version": "research.v1",
        "fragments": [{
            "fragment_id": "DOC1-P1-C1", "document_id": DOC,
            "version": 1, "page": 1, "text": "Ủy ban yêu cầu báo cáo trước ngày 20/09.",
        }],
        "evidence": [{
            "source_id": "SRC-1", "fragment_id": "DOC1-P1-C1",
            "quote": "yêu cầu báo cáo", "verified": True,
        }],
        "output_schema_id": "research.v1",
        "max_output_tokens": 512,
        "temperature_milli": 0,
    }
    data.update(changes)
    return InferencePacket.model_validate(data)


def result(**changes):
    data = {
        "task_id": "TASK-001", "agent_id": "research",
        "findings": [{"claim": "Có yêu cầu báo cáo.", "source_ids": ["SRC-1"]}],
        "uncertainties": [], "blocking_errors": [], "proposed_output": None,
    }
    data.update(changes)
    return AgentResult.model_validate(data)


def test_packet_contains_text_only_and_rejects_file_or_authority_fields():
    for forbidden in ("file", "path", "binary", "approved", "endpoint", "api_token"):
        with pytest.raises(ValidationError):
            packet(**{forbidden: "not allowed"})


def test_only_verified_exact_local_evidence_can_leave_gateway():
    with pytest.raises(ValidationError, match="unverified"):
        packet(evidence=[{
            "source_id": "SRC-1", "fragment_id": "DOC1-P1-C1",
            "quote": "yêu cầu báo cáo", "verified": False,
        }])
    with pytest.raises(ValidationError, match="exact local fragment"):
        packet(evidence=[{
            "source_id": "SRC-1", "fragment_id": "DOC1-P1-C1",
            "quote": "nội dung do model bịa", "verified": True,
        }])


def test_remote_result_cannot_approve_and_invented_citations_are_rejected():
    with pytest.raises(ValidationError):
        result(approved=True)
    with pytest.raises(ValueError, match="valid local evidence"):
        validate_result(packet(), result(findings=[{
            "claim": "Không có nguồn.", "source_ids": ["SRC-404"],
        }]))


def test_eight_agent_graph_waits_for_all_three_independent_reviews():
    completed = {AgentId.INTAKE, AgentId.RESEARCH, AgentId.ANALYSIS, AgentId.DRAFTING}
    assert set(ready_agents(completed)) == {
        AgentId.FORMAT_REVIEW, AgentId.EVIDENCE_REVIEW, AgentId.RISK_REVIEW,
    }
    completed |= {AgentId.FORMAT_REVIEW, AgentId.EVIDENCE_REVIEW}
    assert ready_agents(completed) == (AgentId.RISK_REVIEW,)
    completed.add(AgentId.RISK_REVIEW)
    assert ready_agents(completed) == (AgentId.FINALIZER,)
    completed.add(AgentId.FINALIZER)
    assert ready_agents(completed) == ("human_review",)


@pytest.mark.parametrize(
    "status,training_approved,export_approved,eligible",
    [
        ("approved", True, True, True),
        ("pending", True, True, False),
        ("rejected", True, True, False),
        ("approved", False, True, False),
        ("approved", True, False, False),
    ],
)
def test_training_requires_separate_human_training_and_export_permissions(
    status, training_approved, export_approved, eligible
):
    example = TrainingExample(
        packet=packet(), result=result(), human_status=status,
        training_approved=training_approved, export_approved=export_approved,
    )
    assert example.eligible_for_training is eligible


def test_training_example_binds_task_and_agent():
    with pytest.raises(ValidationError, match="another task"):
        TrainingExample(
            packet=packet(), result=result(task_id="TASK-002"), human_status="pending"
        )
