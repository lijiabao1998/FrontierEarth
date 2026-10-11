"""Fail before input evaluation unless admission and public-claim evidence exist."""
import datetime as dt
import hashlib
import json
from pathlib import Path

def require_admission(repo, rid, pid, proposal):
    r=json.loads((Path(repo)/'runs'/rid/'round.json').read_text(encoding='utf-8'))
    if r.get('problem_id')!=pid or r.get('state') not in ('ADMITTED','RUNNING') or not r.get('admitted_at'):
        raise RuntimeError('NOT_RUN: new round is not admitted')
    if r.get('preflight',{}).get('verdict') not in ('NO_RESOLUTION_FOUND','PARTIAL_PROGRESS'):
        raise RuntimeError('NOT_RUN: preflight remains blocked')
    claim=r.get('public_claim',{})
    if claim.get('status')!='POSTED_AND_READ_BACK' or not claim.get('url','').startswith('https://github.com/lijiabao1998/'):
        raise RuntimeError('NOT_RUN: public scope/budget registration missing')
    proof=Path(repo)/claim['readback_path']
    if hashlib.sha256(proof.read_bytes()).hexdigest()!=claim.get('readback_sha256'):
        raise RuntimeError('NOT_RUN: public claim evidence checksum mismatch')
    protocol_digest=hashlib.sha256(Path(proposal).read_bytes()).hexdigest()
    if protocol_digest not in r.get('acceptance',''):
        raise RuntimeError('NOT_RUN: protocol digest mismatch')
    started=dt.datetime.fromisoformat(r['budget'].get('preparation_started_at',r['started_at']))
    if dt.datetime.now(dt.timezone.utc)>started+dt.timedelta(minutes=r['budget']['wall_minutes']):
        raise RuntimeError('NOT_RUN: whole-round budget exhausted; no restart of this round')
    if r['budget'].get('cpu_affinity_count')!=1 or r['budget'].get('usd')!=0:
        raise RuntimeError('NOT_RUN: single CPU/zero-dollar budget contract changed')
    return r
