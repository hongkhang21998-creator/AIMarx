"""Offline synthetic review receipts; no model, network, runtime or permission grants."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError, model_validator

from evals.planning_v2.cli import build_input
from evals.planning_v2.schema import Closed, PlanningInput, Proposal, Text
from evals.planning_v2.score import validate_proposal

ROOT = Path(__file__).parent
Hash = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Identifier = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9_-]{0,63}$')]
SPLIT_COUNTS = {'train': 80, 'validation': 20, 'smoke-test': 20}
CHECKLIST = ('decision', 'grounding', 'missing_information', 'worker_order', 'no_escalation')
ERROR = 'TRAIN-02 dữ liệu hoặc quyết định duyệt không hợp lệ'
# Pin only after #46 is merged AND independently accepted in a follow-up PR.
SPLIT_AUDIT_APPROVED_SHA256 = None


class Blocked(ValueError):
    """A fixed, content-free reason safe to display in the offline CLI."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise ValueError(ERROR)
            obj[k] = v
        return obj
    def constant(_):
        raise ValueError(ERROR)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=constant)


class Rubric(Closed):
    critical_checks: Annotated[list[Text], Field(min_length=1)]
    missing_required: list[Text]


class Provenance(Closed):
    kind: Literal['synthetic']
    author: Literal['AI draft — human review required']
    real_documents_used: Literal[False]
    classification_labels: Literal['simulated']
    exposure: Literal['repository_exposed_not_blind']


class Receipt(Closed):
    sequence: Annotated[int, Field(strict=True, ge=1)]
    content_sha256: Hash
    reviewer: Text
    human_attestation: Literal[True]
    action: Literal['approve', 'reject']
    reason: Text
    checklist: dict[str, bool]
    training_approved: bool
    export_approved: bool
    reviewed_at: Text
    previous_sha256: Hash
    receipt_sha256: Hash

    @model_validator(mode='after')
    def valid_receipt(self):
        if set(self.checklist) != set(CHECKLIST):
            raise ValueError(ERROR)
        if self.action == 'approve' and not all(self.checklist.values()):
            raise ValueError(ERROR)
        if self.action == 'reject' and (self.training_approved or self.export_approved):
            raise ValueError(ERROR)
        dt = datetime.fromisoformat(self.reviewed_at)
        if dt.utcoffset() != timezone.utc.utcoffset(dt):
            raise ValueError(ERROR)
        return self


class Case(Closed):
    id: Identifier
    source_family_id: Identifier
    template_family_id: Identifier
    category: Literal['clear', 'missing', 'multi_source', 'deadline', 'terminal', 'adversarial']
    split: Literal['train', 'validation', 'smoke-test']
    input: PlanningInput
    reference: Proposal
    rubric: Rubric
    provenance: Provenance
    source_sha256: Hash
    input_sha256: Hash
    content_sha256: Hash
    review_status: Literal['pending_human', 'approved', 'rejected']
    training_approved: bool
    export_approved: bool
    review_history: list[Receipt]


class Manifest(Closed):
    format: Literal['train02-v1']
    count: Annotated[int, Field(strict=True, ge=0)]
    split_counts: dict[str, int]
    cases_sha256: Hash
    contract_sha256: Hash
    exposure: Literal['repository_exposed_not_blind']


def contract_hash():
    envelope = build_input({'id': 'contract', 'input': {
        'request': 'contract', 'as_of': '2026-09-13T09:00:00+07:00', 'sources': []}})
    return digest({'instruction': envelope['instruction'], 'schema': envelope['output_schema']})


def content_hash(case):
    # Derived hashes/permissions/history excluded; every reviewed content field included.
    return digest({'contract_sha256': contract_hash(), **{k: case[k] for k in (
        'id', 'source_family_id', 'template_family_id', 'category', 'split',
        'input', 'reference', 'rubric', 'provenance')}})


def effective_review(case):
    history = case['review_history']
    if not history or history[-1]['content_sha256'] != content_hash(case):
        return 'pending_human', False, False
    last = history[-1]
    return ('approved' if last['action'] == 'approve' else 'rejected',
            last['training_approved'], last['export_approved'])


def refresh(case):
    """Explicit editing helper: changed content invalidates the receipt, never reapproves."""
    result = copy.deepcopy(case)
    result['source_sha256'] = digest(result['input']['sources'])
    result['input_sha256'] = digest(result['input'])
    result['content_sha256'] = content_hash(result)
    status, training, export = effective_review(result)
    result.update(review_status=status, training_approved=training, export_approved=export)
    validate_case(result)
    return result


def validate_case(case):
    try:
        Case.model_validate(case)
        if case['provenance']['real_documents_used'] is not False:
            raise ValueError(ERROR)
        if (case['source_sha256'] != digest(case['input']['sources'])
                or case['input_sha256'] != digest(case['input'])
                or case['content_sha256'] != content_hash(case)):
            raise ValueError(ERROR)
        if not validate_proposal(case['reference'], case['input'])['structural_pass']:
            raise ValueError(ERROR)
        if case['rubric']['missing_required'] != case['reference']['missing_information']:
            raise ValueError(ERROR)
        previous = '0' * 64
        for seq, receipt in enumerate(case['review_history'], 1):
            if receipt['human_attestation'] is not True:
                raise ValueError(ERROR)
            if (receipt['sequence'] != seq or receipt['previous_sha256'] != previous
                    or receipt['receipt_sha256'] != digest({k: v for k, v in receipt.items()
                                                           if k != 'receipt_sha256'})):
                raise ValueError(ERROR)
            previous = receipt['receipt_sha256']
        if effective_review(case) != (case['review_status'], case['training_approved'], case['export_approved']):
            raise ValueError(ERROR)
    except (ValidationError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError(ERROR) from None
    return case


def manifest_for(cases):
    return {'format': 'train02-v1', 'count': len(cases),
            'split_counts': dict(Counter(c['split'] for c in cases)),
            'cases_sha256': digest(cases), 'contract_sha256': contract_hash(),
            'exposure': 'repository_exposed_not_blind'}


def validate_dataset(cases, manifest):
    try:
        Manifest.model_validate(manifest)
        if type(cases) is not list or not cases or manifest != manifest_for(cases):
            raise ValueError(ERROR)
        for case in cases:
            validate_case(case)
        # Review routing needs unique IDs even before optional #46 integration.
        if len({c['id'] for c in cases}) != len(cases):
            raise ValueError(ERROR)
    except (ValidationError, KeyError, TypeError, ValueError):
        raise ValueError(ERROR) from None
    return cases


def load_dataset(directory=ROOT):
    directory = Path(directory)
    return validate_dataset(read_json(directory / 'cases.json'), read_json(directory / 'manifest.json'))


def split_audit(cases):
    """Reuse #46 only. Missing module is a visible dependency, never a clean audit."""
    try:
        import importlib
        module = importlib.import_module('evals.training.split_audit')
    except ModuleNotFoundError as exc:
        if exc.name == 'evals.training.split_audit':
            return {'status': 'blocked_dependency_46', 'findings': []}
        raise
    if (SPLIT_AUDIT_APPROVED_SHA256 is None
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != SPLIT_AUDIT_APPROVED_SHA256):
        return {'status': 'blocked_unreviewed_dependency_46', 'findings': []}
    rows = [{'sample_id': c['id'], 'source_family_id': c['source_family_id'],
             'template_family_id': c['template_family_id'],
             'split': 'test' if c['split'] == 'smoke-test' else c['split'],
             'source_hash': c['source_sha256']} for c in cases]
    findings = module.audit_splits(rows)
    if type(findings) is not list:
        raise ValueError(ERROR)
    return {'status': 'findings' if findings else 'ok', 'findings': findings}


def shingles(text):
    words = re.findall(r'\w+', re.sub(r'\d+', 'NUMBER', unicodedata.normalize('NFC', text).casefold()))
    return set(zip(words, words[1:])) or set(words)


def near_duplicates(cases, baseline=(), threshold=0.65):
    """Word-bigram Jaccard; compare source blocks and complete request+source text."""
    if not 0 < threshold <= 1:
        raise ValueError(ERROR)
    def views(c):
        blocks = [s['text'] for s in c['input']['sources']]
        return [shingles(c['input']['request'] + ' ' + ' '.join(blocks))] + [shingles(s) for s in blocks]
    records = [(c, 'train02', views(c)) for c in cases] + [(c, 'baseline', views(c)) for c in baseline]
    findings = []
    for i, (a, origin_a, av) in enumerate(records[:len(cases)]):
        for b, origin_b, bv in records[i + 1:]:
            score = max((len(x & y) / len(x | y) if x | y else 0) for x in av for y in bv)
            if score >= threshold:
                findings.append({'left': a['id'], 'right': b['id'], 'right_origin': origin_b,
                                 'cross_split': origin_b == 'baseline' or a['split'] != b['split'],
                                 'similarity': round(score, 4)})
    return findings


def review_case(case, *, expected_sha256, reviewer, action, reason, checklist,
                training_approved=False, export_approved=False, human_attestation=False):
    validate_case(case)
    if expected_sha256 != case['content_sha256'] or human_attestation is not True:
        raise ValueError(ERROR)
    result = copy.deepcopy(case)
    receipt = {'sequence': len(result['review_history']) + 1, 'content_sha256': expected_sha256,
               'reviewer': reviewer, 'human_attestation': human_attestation, 'action': action,
               'reason': reason, 'checklist': checklist, 'training_approved': training_approved,
               'export_approved': export_approved, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
               'previous_sha256': result['review_history'][-1]['receipt_sha256'] if result['review_history'] else '0' * 64}
    receipt['receipt_sha256'] = digest(receipt)
    result['review_history'].append(receipt)
    return refresh(result)


def review_queue(cases):
    for c in cases:
        validate_case(c)
        yield {'id': c['id'], 'content_sha256': c['content_sha256'], 'split': c['split'],
               'input': copy.deepcopy(c['input']), 'reference': copy.deepcopy(c['reference']),
               'rubric': copy.deepcopy(c['rubric']), 'review_status': c['review_status'],
               'review_history': copy.deepcopy(c['review_history']),
               'checklist': dict.fromkeys(CHECKLIST, False),
               'notice': 'LOCAL REVIEW ONLY; not model input; no human approval recorded by this queue'}


def inference_input(case):
    validate_case(case)
    return build_input(case)


def export_rows(cases, split, baseline=None):
    if baseline is None:
        from evals.planning_v2.cli import load_cases
        baseline = load_cases()
    if split not in ('train', 'validation'):
        raise Blocked('Smoke-test/reference không được xuất thành dữ liệu huấn luyện')
    validate_dataset(cases, manifest_for(cases))
    selected = [c for c in cases if c['split'] == split]
    if not selected or any(effective_review(c) != ('approved', True, True) for c in selected):
        raise Blocked('Mọi mẫu được chọn phải được duyệt đúng hash và đủ quyền train/export')
    if split_audit(cases)['status'] != 'ok':
        raise Blocked('Export bị chặn: cần split_audit #46 đạt, không bỏ qua dependency/findings')
    if any(f['cross_split'] for f in near_duplicates(cases, baseline)):
        raise Blocked('Export bị chặn: có nguồn gần trùng khác tập/baseline cần xử lý')
    return [{'prompt': json.dumps(inference_input(c), ensure_ascii=False, sort_keys=True),
             'completion': json.dumps(c['reference'], ensure_ascii=False, sort_keys=True)} for c in selected]
