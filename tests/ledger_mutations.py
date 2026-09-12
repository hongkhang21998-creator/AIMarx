"""Mutate actual production source in isolated copies; require assertion failures, not collection errors."""
from pathlib import Path
import json, os, shutil, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[1]
python=sys.executable
ledger='src/tro_ly_van_ban/provider_ledger.py'
snapshot='src/tro_ly_van_ban/provider_snapshot.py'
grants='src/tro_ly_van_ban/provider_grants.py'
mutations=[
 ('reserve_separate_transaction',ledger,'        _event(conn, attempt_id, at_ms=now_ms, from_state=None, to_state="reserved",','        conn.execute("COMMIT")\n        conn.execute("BEGIN IMMEDIATE")\n        _event(conn, attempt_id, at_ms=now_ms, from_state=None, to_state="reserved",','test_real_process_crash_rolls_back_whole_lifecycle'),
 ('settle_early_commit',ledger,'            ps._finish_locked(tx, snapshot_id, outcome=outcome, now_ms=now_ms)','            conn.execute("COMMIT")\n            conn.execute("BEGIN IMMEDIATE")\n            ps._finish_locked(tx, snapshot_id, outcome=outcome, now_ms=now_ms)','test_loi_giua_settle_va_finish_rollback_ca_khoi'),
 ('public_finish_bypass',snapshot,'        if _ledger_pending(conn, snapshot_id):','        if False:','test_finish_cong_khai_khong_di_vong_qua_so'),
 ('forget_unresolved_across_periods',ledger,"WHEN state IN ('reserved','unresolved') THEN reserved_micro_usd","WHEN state IN ('reserved','unresolved') AND started_at_ms < 0 THEN reserved_micro_usd",'test_thieu_usage_thi_unresolved_chu_khong_phai_0'),
 ('clamp_actual',ledger,'                if actual > reserved:','                actual = min(actual, reserved)\n                if actual > reserved:','test_usage_vuot_reserve_ghi_du_va_khoa_dung_provider'),
 ('ignore_replay_outcome',ledger,'fingerprint = _fingerprint({"outcome": outcome, "usage": None if usage is None else','fingerprint = _fingerprint({"outcome": "ignored", "usage": None if usage is None else','test_settlement_replay_checks_full_result'),
 ('reconcile_accept_conflict',ledger,'            if prior != fingerprint:\n                raise _unavailable("RECONCILIATION_CONFLICT")','            if False:\n                raise _unavailable("RECONCILIATION_CONFLICT")','test_reconcile_exact_replay_and_conflict'),
 ('unlock_provider_too_early',ledger,'        if remaining == 0:','        if True:','test_doi_soat_khong_mo_khoa_khi_con_su_co_khac'),
 ('clock_allows_bucket_rollback',ledger,'        if now_ms < high and _bucket(now_ms)[0] != _bucket(high)[0]:','        if False:', 'test_clock_backward_one_millisecond_across_bucket'),
 ('unknown_owner_is_dead',ledger,'            if dead is True:','            if dead is not False:','test_chua_chung_minh_duoc_chet_thi_cho_het_deadline'),
 ('reservation_duck_type',grants,'    if type(reservation) is not Reservation:','    if reservation is None:','test_mutable_reservation_impostor_rejected'),
 ('skip_release_snapshot_close',ledger,'        _close_failed(tx, snapshot_id, now_ms)','        pass # mutation: skip close','test_failure_paths_close_snapshot_atomically'),
 ('round_down',ledger,'    return -(-numerator // denominator)','    return numerator // denominator','test_lam_tron_len_khong_bao_gio_xuong'),
 ('corrupt_state_as_zero',ledger,'    if invalid is not None:', '    if False:', 'test_corrupt_state_cannot_look_like_free_budget'),
 ('context_unchecked',ledger,'        if bound + output_cap > context_limit:','        if False:','test_verified_context_is_part_of_pricing_and_enforced'),
]
results=[]
for name,file,old,new,test in mutations:
 with tempfile.TemporaryDirectory(prefix='aimarx-mutation-') as folder:
  target=Path(folder)
  for dirname in ['src','tests']:
   shutil.copytree(root/dirname,target/dirname,ignore=shutil.ignore_patterns('__pycache__'))
  shutil.copy(root/'pyproject.toml',target/'pyproject.toml')
  p=target/file;s=p.read_text();assert old in s,(name,'missing target')
  p.write_text(s.replace(old,new))
  cmd=[python,'-m','pytest','-q','tests/test_provider_ledger.py','-k',test,'--tb=short']
  proc=subprocess.run(cmd,cwd=target,capture_output=True,text=True,timeout=120,
                      env={**os.environ,'PYTHONPATH':str(target/'src'),'AIMARX_TEST_DATA1000':'0'})
  caught=proc.returncode==1 and 'FAILED ' in proc.stdout and 'ERROR ' not in proc.stdout
  result={'mutation':name,'caught':caught,'returncode':proc.returncode,'test':test,'summary':proc.stdout.strip().splitlines()[-1:]}
  if not caught: result['output']=proc.stdout[-6000:]+proc.stderr[-1000:]
  print(json.dumps(result,ensure_ascii=False),flush=True);results.append(result)
Path(sys.argv[1] if len(sys.argv) > 1 else str(Path(tempfile.gettempdir())/'aimarx-ledger-mutations.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2))
sys.exit(0 if all(r['caught'] for r in results) else 1)
