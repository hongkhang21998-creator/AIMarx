"""Local check, inputs, review-queue, review and guarded export. No training/upload."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from evals.planning_v2.cli import load_cases as baseline_cases
from .core import (ROOT, ERROR, Blocked, SPLIT_COUNTS, export_rows, inference_input,
                   load_dataset, manifest_for, near_duplicates, effective_review, read_json, review_case,
                   review_queue, split_audit)


def write_new(path, text):
    # Validation finishes before opening. Exclusive create never truncates an existing file.
    with Path(path).open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def lines(rows):
    return ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows)


def apply_reviews(cases, decisions, reviewer, human_attestation):
    if type(decisions) is not list or not decisions:
        raise ValueError(ERROR)
    known = {c['id']: c for c in cases}
    updated = {}
    fields = {'id', 'expected_sha256', 'action', 'reason', 'checklist', 'training_approved', 'export_approved'}
    for decision in decisions:
        if (type(decision) is not dict or set(decision) != fields
                or type(decision['id']) is not str or decision['id'] not in known
                or decision['id'] in updated):
            raise ValueError(ERROR)
        updated[decision['id']] = review_case(known[decision['id']], reviewer=reviewer,
                                             human_attestation=human_attestation,
                                             **{k: v for k, v in decision.items() if k != 'id'})
    return [updated.get(c['id'], c) for c in cases]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'inputs', 'review-queue', 'review', 'export'])
    parser.add_argument('--data', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--decisions', type=Path, help='JSON array of explicit per-case review decisions')
    parser.add_argument('--reviewer')
    parser.add_argument('--human-attestation', action='store_true', help='The named human actually reviewed these hashes')
    parser.add_argument('--split', choices=['train', 'validation'])
    args = parser.parse_args()
    try:
        cases = load_dataset(args.data)
        if args.command == 'check':
            audit = split_audit(cases)
            near = near_duplicates(cases, baseline_cases())
            ready = {}
            for split in ('train', 'validation'):
                chosen = [c for c in cases if c['split'] == split]
                ready[split] = (bool(chosen) and audit['status'] == 'ok'
                                and not any(f['cross_split'] for f in near)
                                and all(effective_review(c) == ('approved', True, True) for c in chosen))
            summary = {'count': len(cases), 'split_counts': manifest_for(cases)['split_counts'],
                       'full_smoke_counts': manifest_for(cases)['split_counts'] == SPLIT_COUNTS,
                       'pending_human': sum(c['review_status'] == 'pending_human' for c in cases),
                       'approved': sum(c['review_status'] == 'approved' for c in cases),
                       'structural_checks': 'ok', 'split_audit': audit, 'near_duplicates': near,
                       'export_ready': all(ready.values()), 'export_ready_by_split': ready,
                       'notice': 'Local export readiness only. No cloud permission, training job or model quality claim; export rechecks all gates.'}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            if audit['status'] == 'findings' or any(f['cross_split'] for f in near):
                return 2
            return 0
        if args.output is None:
            raise ValueError('Cần --output local; không gửi nội dung ra stdout')
        if args.command == 'review':
            if not args.decisions or not args.reviewer or not args.human_attestation:
                raise ValueError('Cần decisions, reviewer và human-attestation; AI không tự duyệt')
            updated = apply_reviews(cases, read_json(args.decisions), args.reviewer, args.human_attestation)
            # A new dataset directory, never mutate the reviewed source or official draft.
            args.output.mkdir(parents=True, exist_ok=False)
            write_new(args.output / 'cases.json', json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
            write_new(args.output / 'manifest.json', json.dumps(manifest_for(updated), ensure_ascii=False, indent=2) + '\n')
        elif args.command == 'inputs':
            write_new(args.output, lines([inference_input(c) for c in cases]))
        elif args.command == 'review-queue':
            write_new(args.output, lines(list(review_queue(cases))))
        else:
            write_new(args.output, lines(export_rows(cases, args.split, baseline_cases())))
        print(json.dumps({'status': 'written_local', 'command': args.command}, ensure_ascii=False))
        return 0
    except Blocked as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc)}, ensure_ascii=False))
        return 2
    except (ValueError, OSError, TypeError, KeyError, RecursionError):
        # Do not echo Pydantic input values, filesystem paths or document content.
        print(json.dumps({'status': 'blocked', 'reason': ERROR,
                          'help': 'Kiểm quyền/hash/schema; export cần #46, không nhận smoke-test. Không ghi đè output.'}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
