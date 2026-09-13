"""Strict JSON + contract/grounding checks. Semantic acceptance requires a human."""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .schema import PlanningInput, Proposal

MAX_OUTPUT_BYTES = 64 * 1024


def strict_json(raw: str) -> Any:
    if type(raw) is not str or len(raw.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("output must be text <= 64 KiB")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError("non-finite JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def validate_proposal(candidate: Any, input_data: Any) -> dict:
    """Only structural/reference validation; never a dispatch or permission gate."""
    result = {"schema_valid": False, "references_valid": False,
              "structural_pass": False, "status": "fail", "issues": [],
              "semantic_status": "needs_human_review", "execution_authorized": False}
    try:
        context = PlanningInput.model_validate(input_data)
    except (ValidationError, ValueError):
        result["issues"].append({"code": "invalid_input"})
        return result
    try:
        proposal = Proposal.model_validate(candidate)
    except ValidationError as exc:
        result["issues"].extend({"code": "invalid_proposal", "path": list(e["loc"]),
                                 "type": e["type"]} for e in exc.errors())
        return result
    result["schema_valid"] = True
    sources = {s.key(): s.text for s in context.sources}
    cited = set()
    for quote in proposal.evidence_quotes:
        key = quote.key()
        if key not in sources:
            result["issues"].append({"code": "unknown_source_or_version"})
        elif quote.quote not in sources[key]:
            result["issues"].append({"code": "quote_not_found"})
        else:
            cited.add(key)
    for step in proposal.steps:
        for ref in step.source_refs:
            if ref.key() not in sources:
                result["issues"].append({"code": "unknown_step_source", "step": step.id})
            elif ref.key() not in cited:
                result["issues"].append({"code": "uncited_step_source", "step": step.id})
    if sources and not proposal.evidence_quotes:
        result["issues"].append({"code": "missing_evidence"})
    result["references_valid"] = not result["issues"]
    result["structural_pass"] = result["references_valid"]
    if result["structural_pass"]:
        result["status"] = "needs_human_review"
    return result


def score_raw(raw: str, input_data: Any) -> dict:
    try:
        parsed = strict_json(raw)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return {"json_valid": False, "schema_valid": False, "references_valid": False,
                "structural_pass": False, "status": "fail", "issues": [{"code": "invalid_json"}],
                "semantic_status": "needs_human_review", "execution_authorized": False}
    return {"json_valid": True, **validate_proposal(parsed, input_data)}
