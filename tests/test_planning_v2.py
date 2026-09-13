from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from evals.planning_v2 import cli
from evals.planning_v2.schema import Proposal
from evals.planning_v2.score import score_raw, validate_proposal


@pytest.fixture
def case():
    return copy.deepcopy(cli.load_cases()[0])


def test_all_36_references_have_valid_structure_but_are_not_training_approved():
    cases = cli.load_cases()
    assert len(cases) == 36
    assert {c['category'] for c in cases} == {'clear', 'missing', 'dependency', 'deadline', 'terminal', 'adversarial'}
    for c in cases:
        result = score_raw(json.dumps(c['reference']), c['input'])
        assert result['structural_pass'], c['id']
        assert result['status'] == 'needs_human_review'
        assert result['execution_authorized'] is False
        assert c['training_approved'] is False and c['export_approved'] is False


@pytest.mark.parametrize('field,value', [('state','approved'), ('attempts',0), ('budget',1),
                                        ('grant','yes'), ('cloud_eligible',True), ('shell','ls')])
def test_model_cannot_add_authority_fields(case, field, value):
    case['reference'][field] = value
    result = validate_proposal(case['reference'], case['input'])
    assert result['schema_valid'] is False
    assert result['execution_authorized'] is False


@pytest.mark.parametrize('change', ['cycle','duplicate','parallel','output','worker','forward',
                                  'ref_without_dependency','extra_step_field','empty_checks','too_many'])
def test_invalid_execution_graph_or_worker_is_rejected(case, change):
    p = case['reference']
    if change == 'cycle':
        p['steps'][0]['depends_on'] = ['s3']
    elif change == 'duplicate':
        p['steps'][1]['id'] = 's1'
    elif change == 'parallel':
        p['steps'][2]['depends_on'] = ['s1']
        p['steps'][2]['input_refs'] = []
    elif change == 'output':
        p['steps'][1]['input_refs'][0]['output_schema_id'] = 'draft-v1'
    elif change == 'worker':
        p['steps'][0]['worker_id'] = 'send_cloud'
    elif change == 'forward':
        p['steps'][0]['input_refs'] = [{'step_id':'s3','output_schema_id':'review-v1'}]
    elif change == 'ref_without_dependency':
        p['steps'][2]['input_refs'] = [{'step_id':'s1','output_schema_id':'facts-v1'}]
    elif change == 'extra_step_field':
        p['steps'][0]['attempts'] = 99
    elif change == 'empty_checks':
        p['steps'][0]['completion_checks'] = []
    else:
        p['steps'] *= 3
    assert not validate_proposal(p, case['input'])['schema_valid']


@pytest.mark.parametrize('version', [True, 1.0, '1', 0, -1])
def test_source_version_requires_positive_integer_without_coercion(case, version):
    case['reference']['evidence_quotes'][0]['version'] = version
    assert not validate_proposal(case['reference'], case['input'])['schema_valid']


@pytest.mark.parametrize('change,code', [('version','unknown_source_or_version'),
    ('quote','quote_not_found'), ('block','unknown_step_source'), ('uncited','uncited_step_source'),
    ('empty','missing_evidence')])
def test_citation_and_step_sources_are_bound_to_input(case, change, code):
    p = case['reference']
    if change == 'version':
        p['evidence_quotes'][0]['version'] += 1
    elif change == 'quote':
        p['evidence_quotes'][0]['quote'] = 'Dữ kiện không có trong nguồn.'
    elif change == 'block':
        p['steps'][0]['source_refs'][0]['block_id'] = 'missing'
    elif change == 'uncited':
        p['evidence_quotes'] = []
    else:
        p['evidence_quotes'] = []
        for s in p['steps']:
            s['source_refs'] = []
    result = validate_proposal(p, case['input'])
    assert result['schema_valid'] and not result['references_valid']
    assert code in {e['code'] for e in result['issues']}


def test_ask_stops_before_speculative_work_and_terminal_has_no_steps(case):
    p = case['reference']
    p['decision'] = 'ask'
    p['missing_information'] = ['Ngày họp']
    assert not validate_proposal(p, case['input'])['schema_valid']
    p['steps'] = [dict(p['steps'][0], worker_id='ask_user', output_schema_id='question-v1')]
    assert validate_proposal(p, case['input'])['structural_pass']
    p['decision'] = 'no_action'
    assert not validate_proposal(p, case['input'])['schema_valid']
    p['steps'] = []
    p['missing_information'] = []
    assert validate_proposal(p, case['input'])['structural_pass']


@pytest.mark.parametrize('raw', ['```json\n{}\n```', '{} trailing', '{"x":1,"x":2}',
    '{"x":{"y":1,"y":2}}', '{"x":NaN}', '{"x":Infinity}', '', '['*1100,
    ' '*65537, None, '\ud800'], ids=[
        'fence', 'trailing-text', 'duplicate-key', 'nested-duplicate', 'nan', 'infinity',
        'empty', 'too-deep', 'oversized', 'not-text', 'invalid-unicode'])
def test_non_json_duplicate_keys_and_oversized_outputs_fail_without_crashing(case, raw):
    result = score_raw(raw, case['input'])
    assert not result['json_valid'] and not result['structural_pass']


@pytest.mark.parametrize('change', ['duplicate','version_conflict','wrong_date','unknown_field'])
def test_bad_input_fails_closed(case, change):
    data = case['input']
    if change in ('duplicate', 'version_conflict'):
        data['sources'].append(copy.deepcopy(data['sources'][0]))
        if change == 'version_conflict':
            data['sources'][1]['version'] += 1
    elif change == 'wrong_date':
        data['as_of'] = '2026-02-30T12:00:00+07:00'
    else:
        data['grant'] = 'approved'
    assert validate_proposal(case['reference'], data)['issues'] == [{'code':'invalid_input'}]


def test_valid_structure_is_not_semantic_correctness_or_cloud_permission(case):
    case['input']['sources'][0]['classification'] = 'restricted'
    case['reference']['requested_product'] = 'Một sản phẩm sai nghiệp vụ nhưng đúng kiểu chuỗi'
    result = validate_proposal(case['reference'], case['input'])
    assert result['structural_pass']
    assert result['semantic_status'] == 'needs_human_review'
    assert result['execution_authorized'] is False


def test_zero_source_request_can_ask_without_fabricating_citations(case):
    p = case['reference']
    p.update(decision='ask', missing_information=['Văn bản đầu vào'], evidence_quotes=[])
    p['steps'] = [dict(p['steps'][0], worker_id='ask_user', output_schema_id='question-v1', source_refs=[])]
    case['input']['sources'] = []
    assert validate_proposal(p, case['input'])['structural_pass']


def test_inference_export_cannot_leak_gold_or_rubric(case):
    case['reference'] = {'private_answer':'GOLD_CANARY'}
    case['rubric'] = {'hidden':'RUBRIC_CANARY'}
    payload = cli.build_input(case)
    assert set(payload) == {'id','input','output_schema','instruction'}
    assert 'CANARY' not in json.dumps(payload)
    assert payload['input'] == case['input']


def test_missing_predictions_count_as_failures_not_dropped(case):
    cases = cli.load_cases()
    result = cli.score_batch(cases, [{'id':cases[0]['id'], 'raw_output':json.dumps(cases[0]['reference'])}])
    assert result['total'] == 36 and result['submitted'] == 1
    assert result['structural_pass_count'] == 1
    assert sum(r['missing_prediction'] for r in result['results']) == 35
    assert result['semantic_status'] == 'not_scored_pending_human_review'


@pytest.mark.parametrize('rows', [[{'id':'unknown','raw_output':'{}'}],
    [{'id':'p2-01','raw_output':'{}'}]*2, [{'id':'p2-01','raw_output':{}}]])
def test_prediction_ids_and_raw_text_are_strict(rows):
    with pytest.raises(ValueError):
        cli.score_batch(cli.load_cases(), rows)


def test_exported_schema_matches_python_contract():
    assert json.loads((cli.ROOT/'proposal.schema.json').read_text(encoding='utf-8')) == Proposal.model_json_schema()


def test_cli_end_to_end_and_clean_error(tmp_path):
    root = Path(__file__).parents[1]
    predictions = tmp_path/'predictions.jsonl'
    c = cli.load_cases()[0]
    predictions.write_text(json.dumps({'id':c['id'],'raw_output':json.dumps(c['reference'])})+'\n',encoding='utf-8')
    run = subprocess.run([sys.executable,'-m','evals.planning_v2.cli','score','--predictions',str(predictions)],
                         cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)['structural_pass_count'] == 1
    predictions.write_text('{"id":"p2-01","id":"p2-02"}', encoding='utf-8')
    run = subprocess.run([sys.executable,'-m','evals.planning_v2.cli','score','--predictions',str(predictions)],
                         cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == 2 and 'duplicate JSON key' in run.stderr


@pytest.mark.parametrize('change', ['hash','count','source_family','template_family','duplicate_text','approval'])
def test_dataset_manifest_and_split_integrity(tmp_path, monkeypatch, change):
    cases = cli.load_cases()
    manifest = json.loads((cli.ROOT/'manifest.json').read_text(encoding='utf-8'))
    if change == 'hash':
        cases[0]['rubric']['critical_checks'] = ['changed without manifest update']
    elif change == 'count':
        manifest['count'] += 1
    elif change in ('source_family','template_family'):
        field = change+'_id'
        cases[4][field] = cases[0][field]
    elif change == 'duplicate_text':
        cases[4]['input']['sources'][0]['text'] = cases[0]['input']['sources'][0]['text']
    else:
        cases[0]['training_approved'] = True
    if change != 'hash':
        manifest['cases_sha256'] = cli.digest(cases)
    (tmp_path/'cases.json').write_text(json.dumps({'cases':cases}),encoding='utf-8')
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    with pytest.raises(ValueError):
        cli.load_cases()
