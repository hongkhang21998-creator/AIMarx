"""Adversarial review/export tests. All approvals here belong to fictional test users."""
from __future__ import annotations
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.planning_v2.cli import load_cases as baseline_cases
from evals.training.train02 import core
from evals.training.train02.authoring import build_cases, REPRESENTATIVE_IDS
from evals.training.train02.cli import apply_reviews, write_new

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case():
    return copy.deepcopy(core.load_dataset()[0])


def approve(c, **overrides):
    options = dict(expected_sha256=c['content_sha256'], reviewer='Fictional test reviewer',
                   action='approve', reason='Synthetic test only', checklist=dict.fromkeys(core.CHECKLIST, True),
                   training_approved=True, export_approved=True, human_attestation=True)
    options.update(overrides)
    return core.review_case(c, **options)


def ready_dependency(monkeypatch):
    # Test double for an accepted #46 result; no reimplementation of its algorithm.
    monkeypatch.setattr(core, 'split_audit', lambda cases: {'status': 'ok', 'findings': []})


def test_committed_smoke_is_reproducible_pending_and_separated():
    cases = core.load_dataset()
    assert build_cases() == cases
    assert len(cases) == 120
    assert core.manifest_for(cases)['split_counts'] == {'train': 80, 'validation': 20, 'smoke-test': 20}
    assert len({c['source_family_id'] for c in cases}) == 30
    # Static authored family allocation reviewed here; production #46 is not copied.
    for split, count in [('train', 20), ('validation', 5), ('smoke-test', 5)]:
        assert len({c['template_family_id'] for c in cases if c['split'] == split}) == count
    family_sets = [{c['source_family_id'] for c in cases if c['split'] == split} for split in core.SPLIT_COUNTS]
    assert not family_sets[0] & family_sets[1] and not family_sets[0] & family_sets[2] and not family_sets[1] & family_sets[2]
    assert all(core.effective_review(c) == ('pending_human', False, False) and not c['review_history'] for c in cases)
    assert core.near_duplicates(cases, baseline_cases()) == []
    first = build_cases(REPRESENTATIVE_IDS)
    assert len(first) == 12
    assert {c['category'] for c in first} == {'clear', 'missing', 'multi_source', 'deadline', 'terminal', 'adversarial'}
    assert {c['reference']['decision'] for c in first} == {'plan', 'ask', 'no_action', 'out_of_scope'}


@pytest.mark.parametrize('field', ['id', 'input', 'rubric', 'provenance', 'review_history', 'source_sha256'])
def test_missing_case_fields_rejected(case, field):
    del case[field]
    with pytest.raises(ValueError, match=core.ERROR):
        core.validate_case(case)


@pytest.mark.parametrize('location', ['case', 'input', 'source', 'proposal', 'step', 'rubric', 'provenance'])
def test_extra_fields_rejected(case, location):
    obj = {'case': case, 'input': case['input'], 'source': case['input']['sources'][0],
           'proposal': case['reference'], 'step': case['reference']['steps'][0],
           'rubric': case['rubric'], 'provenance': case['provenance']}[location]
    obj['private_sentinel'] = 'DO_NOT_ECHO_SECRET_SENTINEL'
    with pytest.raises(ValueError) as exc:
        core.refresh(case)
    assert 'DO_NOT_ECHO_SECRET_SENTINEL' not in str(exc.value)


@pytest.mark.parametrize('mutation', ['quote', 'version', 'worker', 'cycle', 'bool_version', 'missing_rubric'])
def test_invalid_reference_not_repaired_by_hash_refresh(case, mutation):
    if mutation == 'quote':
        case['reference']['evidence_quotes'][0]['quote'] = 'Invented quote'
    elif mutation == 'version':
        case['reference']['evidence_quotes'][0]['version'] = 99
    elif mutation == 'worker':
        case['reference']['steps'][0]['worker_id'] = 'send_cloud'
    elif mutation == 'cycle':
        case['reference']['steps'][0]['depends_on'] = ['s3']
    elif mutation == 'bool_version':
        case['input']['sources'][0]['version'] = True
    else:
        case['rubric']['missing_required'] = ['not in proposal']
    with pytest.raises(ValueError):
        core.refresh(case)


def test_review_approval_and_revocation_are_copy_safe(case):
    before = copy.deepcopy(case)
    reviewed = approve(case)
    assert case == before
    assert core.effective_review(reviewed) == ('approved', True, True)
    rejected = approve(reviewed, action='reject', training_approved=False, export_approved=False,
                       reason='Fictional reviewer revokes approval', checklist=dict.fromkeys(core.CHECKLIST, False))
    assert core.effective_review(rejected) == ('rejected', False, False)
    assert len(rejected['review_history']) == 2
    assert core.effective_review(reviewed) == ('approved', True, True)


@pytest.mark.parametrize('field', ['request', 'as_of', 'reference', 'source_text', 'classification',
                                  'rubric', 'split', 'family', 'template', 'category'])
def test_edit_after_approval_invalidates_even_after_rehash(case, field):
    c = approve(case)
    if field == 'request': c['input']['request'] += ' Chỉ tạo bản nháp.'
    elif field == 'as_of': c['input']['as_of'] = '2026-09-14T09:00:00+07:00'
    elif field == 'reference': c['reference']['requested_product'] += ' (revised)'
    elif field == 'source_text': c['input']['sources'][0]['text'] += ' Dữ kiện bổ sung.'
    elif field == 'classification': c['input']['sources'][0]['classification'] = 'internal'
    elif field == 'rubric': c['rubric']['critical_checks'].append('Recheck scope')
    elif field == 'split': c['split'] = 'validation'
    elif field == 'family': c['source_family_id'] = 'changed-family'
    elif field == 'template': c['template_family_id'] = 'changed-template'
    else: c['category'] = 'multi_source'
    with pytest.raises(ValueError): core.validate_case(c)
    c = core.refresh(c)
    assert core.effective_review(c) == ('pending_human', False, False)
    assert c['review_history'] and c['review_status'] == 'pending_human'
    with pytest.raises(ValueError): core.export_rows([c], c['split'])


def test_stale_expected_hash_and_contract_change(case, monkeypatch):
    with pytest.raises(ValueError): approve(case, expected_sha256='a' * 64)
    reviewed = approve(case)
    monkeypatch.setattr(core, 'contract_hash', lambda: 'b' * 64)
    assert core.effective_review(reviewed) == ('pending_human', False, False)
    with pytest.raises(ValueError): core.validate_case(reviewed)


@pytest.mark.parametrize('overrides', [
    {'human_attestation': False}, {'human_attestation': 1}, {'reviewer': ' '},
    {'reason': ''}, {'training_approved': 'true'}, {'export_approved': 1},
    {'checklist': {}}, {'checklist': dict.fromkeys(core.CHECKLIST, False)},
    {'action': 'reject'}, {'action': 'pending'},
], ids=['no-human', 'integer-human', 'blank-reviewer', 'empty-reason', 'string-right',
        'int-right', 'empty-checks', 'failed-checks', 'reject-with-rights', 'unknown-action'])
def test_invalid_review_decisions(case, overrides):
    with pytest.raises(ValueError): approve(case, **overrides)


@pytest.mark.parametrize('field', ['reason', 'sequence', 'previous_sha256', 'receipt_sha256'])
def test_receipt_tampering_rejected(case, field):
    c = approve(case)
    c['review_history'][0][field] = 7 if field == 'sequence' else 'tampered'
    with pytest.raises(ValueError): core.validate_case(c)


def test_manually_flipped_permission_not_an_approval(case):
    case.update(review_status='approved', training_approved=True, export_approved=True)
    with pytest.raises(ValueError): core.validate_case(case)


def test_manifest_tampering_and_duplicate_ids(case):
    cases = [case]
    manifest = core.manifest_for(cases)
    for field, value in [('count', 2), ('split_counts', {'train': True}), ('contract_sha256', 'b' * 64), ('unexpected', True)]:
        wrong = dict(manifest, **{field: value})
        with pytest.raises(ValueError): core.validate_dataset(cases, wrong)
    repeated = [case, copy.deepcopy(case)]
    with pytest.raises(ValueError): core.validate_dataset(repeated, core.manifest_for(repeated))


@pytest.mark.parametrize('rights', [(False, False), (False, True), (True, False)])
def test_export_requires_both_rights(case, monkeypatch, rights):
    ready_dependency(monkeypatch)
    c = approve(case, training_approved=rights[0], export_approved=rights[1])
    with pytest.raises(ValueError): core.export_rows([c], 'train')


def test_export_rechecks_every_selected_sample(case, monkeypatch):
    ready_dependency(monkeypatch)
    c = approve(case)
    other = copy.deepcopy(case)
    other['id'] = 'unreviewed'
    other = core.refresh(other)
    with pytest.raises(ValueError): core.export_rows([c, other], 'train')
    # This is an offline fixture path, not approval/export of the real 120 records.
    rows = core.export_rows([c], 'train')
    assert len(rows) == 1 and set(rows[0]) == {'prompt', 'completion'}
    assert json.loads(rows[0]['completion']) == c['reference']
    assert set(json.loads(rows[0]['prompt'])) == {'id', 'input', 'output_schema', 'instruction'}


def test_smoke_test_cannot_become_training_export(case, monkeypatch):
    ready_dependency(monkeypatch)
    case['split'] = 'smoke-test'
    c = approve(core.refresh(case))
    with pytest.raises(ValueError): core.export_rows([c], 'smoke-test')
    with pytest.raises(ValueError): core.export_rows([c], 'train')


def test_missing_dependency_is_not_pass_and_export_blocks(case, monkeypatch):
    monkeypatch.setitem(sys.modules, 'evals.training.split_audit', None)
    assert core.split_audit([case])['status'] == 'blocked_dependency_46'
    with pytest.raises(ValueError, match='#46'): core.export_rows([approve(case)], 'train')


@pytest.mark.parametrize('finding', ['SOURCE_FAMILY_LEAK', 'TEMPLATE_FAMILY_LEAK', 'SOURCE_HASH_LEAK', 'DUPLICATE_SAMPLE_ID'])
def test_split_adapter_propagates_findings_and_blocks(case, monkeypatch, finding, tmp_path):
    from types import SimpleNamespace
    captured = []
    def fake(records):
        captured.extend(records)
        return [{'code': finding, 'key': 'fixture', 'sample_ids': ['a', 'b'], 'splits': ['test', 'train']}]
    module_file = tmp_path / 'accepted-fixture.py'
    module_file.write_text('# test double only', encoding='utf-8')
    monkeypatch.setattr(core, 'SPLIT_AUDIT_APPROVED_SHA256', core.hashlib.sha256(module_file.read_bytes()).hexdigest())
    monkeypatch.setitem(sys.modules, 'evals.training.split_audit', SimpleNamespace(audit_splits=fake, __file__=str(module_file)))
    c = approve(case)
    with pytest.raises(ValueError, match='#46'): core.export_rows([c], 'train')
    assert captured[0] == {'sample_id': c['id'], 'source_family_id': c['source_family_id'],
                           'template_family_id': c['template_family_id'], 'split': 'train',
                           'source_hash': c['source_sha256']}
    c['split'] = 'smoke-test'
    core.split_audit([core.refresh(c)])
    assert captured[-1]['split'] == 'test'


def test_near_duplicate_detects_renumbered_block_across_split(case, monkeypatch):
    ready_dependency(monkeypatch)
    c = approve(case)
    d = copy.deepcopy(case)
    d['id'] = 'different-id'
    d['split'] = 'validation'
    d['source_family_id'] = 'different-family'
    d['template_family_id'] = 'different-template'
    # Changed request and source ID still cannot hide identical block content.
    d['input']['request'] = 'Xin xem lại nội dung này.'
    d['input']['sources'][0]['text'] += ' Số hồ sơ 999.'
    d = core.refresh(d)
    findings = core.near_duplicates([c, d])
    assert findings and findings[0]['cross_split']
    with pytest.raises(ValueError, match='gần trùng'): core.export_rows([c, d], 'train')
    assert core.shingles('Ngày 12/10/2026') == core.shingles('Ngày 23/11/2027')
    assert core.near_duplicates([case], [case])[0]['right_origin'] == 'baseline'


def test_inputs_do_not_leak_gold_rubric_or_receipts(case, monkeypatch):
    ready_dependency(monkeypatch)
    case['reference']['requested_product'] = 'GOLD_SENTINEL'
    case['rubric']['critical_checks'].append('RUBRIC_SENTINEL')
    c = approve(core.refresh(case), reviewer='REVIEWER_SENTINEL', reason='REASON_SENTINEL')
    raw = json.dumps(core.inference_input(c), ensure_ascii=False)
    exported_prompt = core.export_rows([c], 'train')[0]['prompt']
    for sentinel in ['GOLD_SENTINEL', 'RUBRIC_SENTINEL', 'REVIEWER_SENTINEL', 'REASON_SENTINEL']:
        assert sentinel not in raw and sentinel not in exported_prompt
    queue = list(core.review_queue([c]))
    assert queue[0]['reference']['requested_product'] == 'GOLD_SENTINEL'
    queue[0]['reference']['requested_product'] = 'edited'
    assert c['reference']['requested_product'] == 'GOLD_SENTINEL'


def test_batch_review_is_all_or_nothing(case):
    spec = {'id': case['id'], 'expected_sha256': case['content_sha256'], 'action': 'approve',
            'reason': 'Test only', 'checklist': dict.fromkeys(core.CHECKLIST, True),
            'training_approved': True, 'export_approved': True}
    for decisions in [[spec, spec], [spec, {**spec, 'id': 'unknown'}], [{**spec, 'extra': True}], []]:
        with pytest.raises(ValueError): apply_reviews([case], decisions, 'Test person', True)
    assert not case['review_history']
    assert apply_reviews([case], [spec], 'Test person', True)[0]['review_status'] == 'approved'


def test_strict_json_and_no_output_overwrite(tmp_path):
    path = tmp_path / 'data.json'
    for raw in ['{"a": 1, "a": 2}', '{"a": NaN}']:
        path.write_text(raw, encoding='utf-8')
        with pytest.raises(ValueError): core.read_json(path)
    path.write_text('original', encoding='utf-8')
    with pytest.raises(FileExistsError): write_new(path, 'replacement')
    assert path.read_text(encoding='utf-8') == 'original'


def run_cli(*args):
    env = {**os.environ, 'PYTHONUTF8': '1'}
    return subprocess.run([sys.executable, '-m', 'evals.training.train02.cli', *map(str, args)],
                          cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)


def test_cli_check_and_local_outputs_and_blocked_export(tmp_path):
    result = run_cli('check')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['count'] == 120
    for command in ['inputs', 'review-queue']:
        output = tmp_path / (command + '.jsonl')
        result = run_cli(command, '--output', output)
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(output.read_text(encoding='utf-8').splitlines()) == 120
        assert run_cli(command, '--output', output).returncode == 2
    output = tmp_path / 'export.jsonl'
    result = run_cli('export', '--split', 'train', '--output', output)
    assert result.returncode == 2 and not output.exists()


def test_cli_human_review_new_directory_and_stale_batch(tmp_path, case):
    data = tmp_path / 'fixture'
    data.mkdir()
    (data / 'cases.json').write_text(json.dumps([case]), encoding='utf-8')
    (data / 'manifest.json').write_text(json.dumps(core.manifest_for([case])), encoding='utf-8')
    spec = [{'id': case['id'], 'expected_sha256': case['content_sha256'], 'action': 'approve',
             'reason': 'Fictional fixture', 'checklist': dict.fromkeys(core.CHECKLIST, True),
             'training_approved': False, 'export_approved': False}]
    decisions = tmp_path / 'decisions.json'
    decisions.write_text(json.dumps(spec), encoding='utf-8')
    output = tmp_path / 'reviewed'
    args = ('review', '--data', data, '--decisions', decisions, '--reviewer', 'Fixture reviewer', '--output', output)
    assert run_cli(*args).returncode == 2 and not output.exists()
    assert run_cli(*args, '--human-attestation').returncode == 0
    reviewed = core.load_dataset(output)
    assert core.effective_review(reviewed[0]) == ('approved', False, False)
    assert core.load_dataset(data)[0]['review_status'] == 'pending_human'
    spec[0]['expected_sha256'] = 'b' * 64
    decisions.write_text(json.dumps(spec), encoding='utf-8')
    stale = tmp_path / 'stale-output'
    assert run_cli(*args[:-1], stale, '--human-attestation').returncode == 2
    assert not stale.exists()


def test_unaccepted_split_module_never_executes(case, monkeypatch, tmp_path):
    from types import SimpleNamespace
    def unexpected(_):
        pytest.fail('An unaccepted split auditor must not execute')
    module_file = tmp_path / 'unaccepted.py'
    module_file.write_text('# unaccepted fixture', encoding='utf-8')
    monkeypatch.setitem(sys.modules, 'evals.training.split_audit',
                        SimpleNamespace(audit_splits=unexpected, __file__=str(module_file)))
    assert core.split_audit([case])['status'] == 'blocked_unreviewed_dependency_46'
    monkeypatch.setattr(core, 'SPLIT_AUDIT_APPROVED_SHA256', 'a' * 64)
    assert core.split_audit([case])['status'] == 'blocked_unreviewed_dependency_46'


def test_provenance_requires_boolean_false(case):
    case['provenance']['real_documents_used'] = 0
    with pytest.raises(ValueError): core.refresh(case)


def test_multi_source_checks_before_and_after_draft():
    c = next(c for c in core.load_dataset() if c['category'] == 'multi_source')
    steps = c['reference']['steps']
    assert [s['worker_id'] for s in steps] == ['extract', 'verify', 'draft', 'verify']
    assert steps[2]['input_refs'] == [
        {'step_id': 's1', 'output_schema_id': 'facts-v1'},
        {'step_id': 's2', 'output_schema_id': 'review-v1'}]
