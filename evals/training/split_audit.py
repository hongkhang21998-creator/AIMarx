"""G-TEST-01: deterministic, pure metadata audit. No files, network or permissions."""
from __future__ import annotations

import re

_ERROR = 'Metadata chia tập không hợp lệ'
_FIELDS = {'sample_id', 'source_family_id', 'template_family_id', 'split', 'source_hash'}
_IDS = ('sample_id', 'source_family_id', 'template_family_id')


def audit_splits(records: list[dict]) -> list[dict]:
    """Validate the whole input, normalize copied IDs, then report sorted findings."""
    if type(records) is not list:
        raise ValueError(_ERROR)
    normalized = []
    for record in records:
        if type(record) is not dict or set(record) != _FIELDS:
            raise ValueError(_ERROR)
        if any(type(record[field]) is not str or not record[field].strip() for field in _IDS):
            raise ValueError(_ERROR)
        if type(record['split']) is not str or record['split'] not in ('train', 'validation', 'test'):
            raise ValueError(_ERROR)
        if type(record['source_hash']) is not str or re.fullmatch(r'[0-9a-f]{64}', record['source_hash']) is None:
            raise ValueError(_ERROR)
        normalized.append({**record, **{field: record[field].strip() for field in _IDS}})

    findings = []
    for field, code in (
        ('sample_id', 'DUPLICATE_SAMPLE_ID'),
        ('source_family_id', 'SOURCE_FAMILY_LEAK'),
        ('template_family_id', 'TEMPLATE_FAMILY_LEAK'),
        ('source_hash', 'SOURCE_HASH_LEAK'),
    ):
        groups = {}
        for record in normalized:
            groups.setdefault(record[field], []).append(record)
        for key, members in groups.items():
            splits = sorted({record['split'] for record in members})
            if (len(members) > 1 if field == 'sample_id' else len(splits) > 1):
                findings.append({'code': code, 'key': key,
                                 'sample_ids': sorted({record['sample_id'] for record in members}),
                                 'splits': splits})
    return sorted(findings, key=lambda finding: (finding['code'], finding['key']))
