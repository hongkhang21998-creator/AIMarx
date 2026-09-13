"""Source mutations in isolated copies; exit 0 only when targeted tests catch all.

Run: python tests/train01_mutations.py /tmp/train01-mutations.json
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('unresolved_conflict_ignored', 'src/tro_ly_van_ban/provider_ledger.py',
     '            if prior_reason != reason:', '            if False:',
     'tests/test_ledger_43a.py::test_unresolved_replay_conflicting_reason_is_rejected_without_mutation'),
    ('authority_fields_ignored', 'evals/planning_v2/schema.py', 'extra="forbid"', 'extra="ignore"',
     'tests/test_planning_v2.py::test_model_cannot_add_authority_fields'),
    ('parallel_steps_allowed', 'evals/planning_v2/schema.py',
     '            if seen and next(reversed(seen)) not in step.depends_on:', '            if False:',
     'tests/test_planning_v2.py::test_invalid_execution_graph_or_worker_is_rejected[parallel]'),
    ('wrong_quote_accepted', 'evals/planning_v2/score.py',
     '        elif quote.quote not in sources[key]:', '        elif False:',
     'tests/test_planning_v2.py::test_citation_and_step_sources_are_bound_to_input[quote-quote_not_found]'),
    ('source_version_ignored', 'evals/planning_v2/schema.py',
     'return self.source_id, self.version, self.block_id', 'return self.source_id, 1, self.block_id',
     'tests/test_planning_v2.py::test_citation_and_step_sources_are_bound_to_input[version-unknown_source_or_version]'),
    ('gold_leaks_to_model', 'evals/planning_v2/cli.py',
     '        "output_schema": Proposal.model_json_schema(),',
     '        "reference": case["reference"],\n        "output_schema": Proposal.model_json_schema(),',
     'tests/test_planning_v2.py::test_inference_export_cannot_leak_gold_or_rubric'),
    ('omitted_predictions_dropped', 'evals/planning_v2/cli.py',
     '        raw = indexed.get(case["id"], "")',
     '        if case["id"] not in indexed:\n            continue\n        raw = indexed.get(case["id"], "")',
     'tests/test_planning_v2.py::test_missing_predictions_count_as_failures_not_dropped'),
]


def main():
    results = []
    for name, file, old, new, test in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix='aimarx-train01-mut-') as folder:
            target = Path(folder)
            for dirname in ('src', 'tests', 'evals'):
                shutil.copytree(ROOT/dirname, target/dirname, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy(ROOT/'pyproject.toml', target/'pyproject.toml')
            path = target/file
            original = path.read_text(encoding='utf-8')
            if original.count(old) != 1:
                raise RuntimeError(f'{name}: expected exactly one mutation site')
            path.write_text(original.replace(old, new), encoding='utf-8')
            proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', test, '--tb=short'],
                                  cwd=target, capture_output=True, text=True, encoding='utf-8', timeout=60,
                                  env={**os.environ, 'PYTHONPATH': str(target/'src'), 'AIMARX_TEST_DATA1000':'0'})
            caught = proc.returncode == 1 and 'FAILED ' in proc.stdout and 'ERROR ' not in proc.stdout
            row = dict(mutation=name, caught=caught, returncode=proc.returncode,
                       test=test, summary=proc.stdout.strip().splitlines()[-1:])
            if not caught:
                row['output'] = proc.stdout[-4000:] + proc.stderr[-1000:]
            print(json.dumps(row), flush=True)
            results.append(row)
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir())/'train01-mutations.json'
    destination.write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0 if all(r['caught'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
