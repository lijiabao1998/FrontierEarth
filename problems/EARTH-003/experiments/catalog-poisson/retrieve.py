"""Bounded, public, unauthenticated USGS historical catalog download; no live feeds."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[4]
ROUND=ROOT/'runs/20261009T105820460779Z-gpt-EARTH-003'
OUT=ROOT/'problems/EARTH-003/results/catalog-poisson'
spec=json.loads((ROUND/'frozen-spec.json').read_text())
record=json.loads((ROUND/'round.json').read_text())
assert record['state'] in ('ADMITTED','RUNNING','FINISHED') and record.get('admitted_at'), 'admit before download'
params=spec['query']
base='https://earthquake.usgs.gov/fdsnws/event/1/'
log={'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'parameters':params,'requests':[]}
OUT.mkdir(parents=True,exist_ok=True)
try:
 for method,name in [('query','catalog.csv'),('count','count.txt')]:
  p=params.copy()
  if method=='count': p.pop('format');p.pop('orderby');p.pop('limit')
  url=base+method+'?'+urllib.parse.urlencode(p)
  req=urllib.request.Request(url,headers={'User-Agent':'FrontierEarth-historical-reproduction/1.0'})
  with urllib.request.urlopen(req,timeout=25) as response:
   data=response.read(2_000_001)
   if len(data)>2_000_000: raise ValueError('Response larger than fixed 2 MB bound')
   item={'url':url,'http_status':response.status,'content_type':response.headers.get('Content-Type'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'saved_as':name}
  (OUT/name).write_bytes(data);log['requests'].append(item)
except Exception as exc:
 log['error']=repr(exc)
 raise
finally:
 (OUT/'retrieval.json').write_text(json.dumps(log,indent=2)+'\n')
 print(json.dumps(log,indent=2))
