"""Contract tests for #46, including malformed input, identity and isolation."""
import copy
import importlib.util
import itertools
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'evals' / 'training' / 'split_audit.py'
spec = importlib.util.spec_from_file_location('g_test_01_split_audit', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
audit_splits = module.audit_splits
ERROR = 'Metadata chia tập không hợp lệ'


def row(sample_id='a', split='train', **kwargs):
    return dict(sample_id=sample_id, source_family_id='source-' + sample_id.strip(),
                template_family_id='template-' + sample_id.strip(), split=split,
                source_hash=('a' if sample_id.strip() == 'a' else 'b') * 64, **kwargs)


def test_empty_and_valid_unique():
    assert audit_splits([]) == []
    assert audit_splits([row(), row('b', 'test')]) == []


@pytest.mark.parametrize('field,code', [
    ('source_family_id', 'SOURCE_FAMILY_LEAK'),
    ('template_family_id', 'TEMPLATE_FAMILY_LEAK'),
    ('source_hash', 'SOURCE_HASH_LEAK'),
])
def test_each_cross_split_finding(field, code):
    a, b = row(), row('b', 'validation')
    b[field] = a[field]
    assert audit_splits([a, b]) == [dict(code=code, key=a[field], sample_ids=['a', 'b'], splits=['train', 'validation'])]


@pytest.mark.parametrize('split', ['train', 'test'])
def test_duplicate_id_same_or_different_split(split):
    a, b = row(), row('b', split)
    b['sample_id'] = ' a '
    assert audit_splits([a, b]) == [dict(code='DUPLICATE_SAMPLE_ID', key='a', sample_ids=['a'], splits=sorted({'train', split}))]


def test_identical_rows_and_repeated_family_in_same_split():
    a = row()
    assert audit_splits([a, a]) == [dict(code='DUPLICATE_SAMPLE_ID', key='a', sample_ids=['a'], splits=['train'])]
    b = {**a, 'sample_id': 'b'}
    assert audit_splits([a, b]) == []


def test_normalization_sorting_unique_and_permutation():
    a = row(' z ')
    a.update(source_family_id=' X ', template_family_id=' Y ', source_hash='f' * 64)
    b = {**a, 'sample_id': 'a', 'split': 'test', 'source_family_id': 'X', 'template_family_id': 'Y'}
    c = {**a, 'sample_id': 'a', 'split': 'validation'}
    expected = [
        dict(code='DUPLICATE_SAMPLE_ID', key='a', sample_ids=['a'], splits=['test', 'validation']),
        dict(code='SOURCE_FAMILY_LEAK', key='X', sample_ids=['a', 'z'], splits=['test', 'train', 'validation']),
        dict(code='SOURCE_HASH_LEAK', key='f' * 64, sample_ids=['a', 'z'], splits=['test', 'train', 'validation']),
        dict(code='TEMPLATE_FAMILY_LEAK', key='Y', sample_ids=['a', 'z'], splits=['test', 'train', 'validation']),
    ]
    for records in itertools.permutations([a, b, c]):
        assert audit_splits(list(records)) == expected


def test_input_and_output_isolation():
    records = [row(), {**row(), 'sample_id': ' b ', 'split': 'test'}]
    before = copy.deepcopy(records)
    first = audit_splits(records)
    first[0]['sample_ids'].append('foreign')
    first[0]['splits'].clear()
    assert records == before
    second = audit_splits(records)
    assert 'foreign' not in second[0]['sample_ids']
    assert second[0]['splits'] == ['test', 'train']


@pytest.mark.parametrize('records', [None, {}, (), 'text', 1, True, [None], [[]], ['text']],
                         ids=['null','dict','tuple','text','int','bool','null-row','list-row','text-row'])
def test_bad_container(records):
    with pytest.raises(ValueError, match='^' + ERROR + '$'):
        audit_splits(records)


@pytest.mark.parametrize('field', ['sample_id', 'source_family_id', 'template_family_id', 'split', 'source_hash'])
@pytest.mark.parametrize('value', [None, 0, True, [], {}], ids=['null','int','bool','list','dict'])
def test_wrong_field_types(field, value):
    r = row()
    r[field] = value
    with pytest.raises(ValueError, match='^' + ERROR + '$'):
        audit_splits([r])


@pytest.mark.parametrize('field', ['sample_id', 'source_family_id', 'template_family_id'])
@pytest.mark.parametrize('value', ['', ' \t\n'], ids=['empty','whitespace'])
def test_empty_ids(field, value):
    r = row()
    r[field] = value
    with pytest.raises(ValueError, match='^' + ERROR + '$'):
        audit_splits([r])


@pytest.mark.parametrize('value', ['Train', ' train', 'train ', '', 'smoke-test'])
def test_split_not_normalized(value):
    r = row()
    r['split'] = value
    with pytest.raises(ValueError, match='^' + ERROR + '$'):
        audit_splits([r])


@pytest.mark.parametrize('value', ['A' * 64, 'a' * 63, 'a' * 65, 'g' * 64, 'a' * 64 + '\n', ' ' + 'a' * 64],
                         ids=['upper','short','long','nonhex','newline','space'])
def test_hash_exact_lower_hex(value):
    r = row()
    r['source_hash'] = value
    with pytest.raises(ValueError, match='^' + ERROR + '$'):
        audit_splits([r])


@pytest.mark.parametrize('field', ['sample_id', 'source_family_id', 'template_family_id', 'split', 'source_hash', 'extra'])
def test_missing_extra_and_invalid_last_record(field):
    bad = row('secret-sentinel')
    if field == 'extra': bad[field] = 'DO_NOT_LEAK_SENTINEL'
    else: del bad[field]
    with pytest.raises(ValueError) as exc:
        audit_splits([row(), row(), bad])
    assert str(exc.value) == ERROR
    assert 'sentinel' not in str(exc.value).lower()


def test_no_mutable_result_aliases_between_findings():
    a, b = row(), {**row(), 'sample_id': 'b', 'split': 'test'}
    results = audit_splits([a, b])
    assert len(results) == 3
    results[0]['sample_ids'].append('extra')
    assert all('extra' not in item['sample_ids'] for item in results[1:])


# Pairwise oracle and mutation checks: separate algorithm from production groups.
import copy, itertools, json, random
from pathlib import Path
src=MODULE.read_text(encoding='utf-8')

def oracle(rows):
    rows=[{**r, **{k:r[k].strip() for k in ('sample_id','source_family_id','template_family_id')}} for r in rows]
    hit=set()
    names={'sample_id':'DUPLICATE_SAMPLE_ID','source_family_id':'SOURCE_FAMILY_LEAK','template_family_id':'TEMPLATE_FAMILY_LEAK','source_hash':'SOURCE_HASH_LEAK'}
    for a,b in itertools.combinations(rows,2):
        for field,code in names.items():
            if a[field]==b[field] and (field=='sample_id' or a['split']!=b['split']): hit.add((code,field,a[field]))
    return sorted([dict(code=code,key=value,sample_ids=sorted({r['sample_id'] for r in rows if r[field]==value}),splits=sorted({r['split'] for r in rows if r[field]==value})) for code,field,value in hit],key=lambda x:(x['code'],x['key']))
rng=random.Random(490046)
batches=[]
for _ in range(300):
    batches.append([dict(sample_id=rng.choice(['a',' b ','c']),source_family_id=rng.choice(['x',' y ']),template_family_id=rng.choice(['m',' n ']),split=rng.choice(['train','validation','test']),source_hash=rng.choice(['a','b','c'])*64) for _ in range(rng.randrange(9))])
def run(fn):
    for records in batches:
        saved=copy.deepcopy(records)
        assert fn(records)==oracle(records)
        assert records==saved
    for bad in [None,(),[{}],[dict(batches[-1][0],extra='sentinel')] if batches[-1] else [{}]]:
        try: fn(bad)
        except ValueError as exc: assert str(exc)=='Metadata chia tập không hợp lệ'
        else: raise AssertionError('accepted invalid data')
def test_pairwise_oracle_300_batches():
    run(audit_splits)

mutants={
 'ignore-cross-split': ('else len(splits) > 1','else len(splits) > 9'),
 'miss-identical-rows': ('len(members) > 1 if','len({r["sample_id"] for r in members}) > 1 if'),
 'no-strip': ('record[field].strip() for field in _IDS','record[field] for field in _IDS'),
 'no-order': ('return sorted(findings, key=lambda finding: (finding[\'code\'], finding[\'key\']))','return findings'),
 'wrong-code': ("'TEMPLATE_FAMILY_LEAK'","'SOURCE_FAMILY_LEAK'"),
 'drop-hash': ("('source_hash', 'SOURCE_HASH_LEAK'),",''),
 'allow-extra': ('set(record) != _FIELDS','not _FIELDS.issubset(record)'),
}
@pytest.mark.parametrize('name', sorted(mutants))
def test_mutations_are_caught_by_independent_oracle(name):
    old, new = mutants[name]
    assert old in src
    ns = {}
    exec(compile(src.replace(old, new), '<mutation>', 'exec'), ns)
    with pytest.raises((AssertionError, ValueError)):
        run(ns['audit_splits'])
