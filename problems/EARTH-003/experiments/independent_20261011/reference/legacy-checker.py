"""Independent historical catalog replay. No author imports. Python3.12.
Usage: python verify_earth.py path/to/catalog-poisson > independent-review.json
Reviewer saw original results; not blind. Bootstrap RNG implementation supplied
by author after first result, not fully specified in original frozen plan.
"""
import csv,datetime as dt,hashlib,json,math,random,statistics,sys
from pathlib import Path
from collections import Counter
p=Path(sys.argv[1]);raw=p/'catalog.csv';r=json.loads((p/'results.json').read_text());rows=list(csv.DictReader(raw.open()));gaps=[]
def ck(a,b):
 gap=abs(a-b);gaps.append(gap);assert gap<1e-12,(a,b,gap)
assert hashlib.sha256(raw.read_bytes()).hexdigest()==r['raw_sha256'];assert len(rows)==int((p/'count.txt').read_text())==r['raw_rows'];ids=set();events=Counter();excluded=[]
start=dt.datetime(2017,1,1,tzinfo=dt.timezone.utc);end=dt.datetime(2019,1,1,tzinfo=dt.timezone.utc)
for x in rows:
 assert x['id'] and x['id'] not in ids;ids.add(x['id']);ts=dt.datetime.fromisoformat(x['time'].replace('Z','+00:00'));lat,lon,depth,mag=[float(x[k]) for k in ['latitude','longitude','depth','mag']];assert all(map(math.isfinite,[lat,lon,depth,mag]))
 if start<=ts<end and 32<=lat<=42 and -125<=lon<=-114 and -100<=depth<=1000 and mag>=4 and x['type']=='earthquake':events[ts.date()]+=1
 else:excluded.append(x['id'])
assert excluded==r['excluded_ids'];days=[(start+dt.timedelta(days=i)).date() for i in range(730)];counts=[events[d] for d in days];y=[int(c>0) for c in counts];a=y[:365];b=y[365:];ck(sum(counts),r['retained_events'])
for label,cc,yy in [('calibration',counts[:365],a),('test',counts[365:],b)]:
 out=r[label];ck(sum(cc),out['events']);ck(sum(yy),out['active_days']);ck(sum(c>1 for c in cc),out['multiple_event_days']);ck(statistics.variance(cc)/statistics.mean(cc),out['daily_count_variance_over_mean'])
for m in r['monthly']:
 selected=[i for i,d in enumerate(days) if str(d).startswith(m['month'])];ck(len(selected),m['days']);ck(sum(counts[i] for i in selected),m['events']);ck(sum(y[i] for i in selected),m['active_days'])
rate=sum(b)/365;probs={'poisson':1-math.exp(-sum(counts[:365])/365),'bernoulli_climatology':sum(a)/365,'zero':0.,'half':.5}
rng=random.Random(196003);rates=[]
for _ in range(2000):
 starts=[rng.randrange(365) for _ in range(13)];total=sum(b[(starts[j//30]+j%30)%365] for j in range(365));rates.append(total/365)
def quant(v,q):
 v=sorted(v);u=(len(v)-1)*q;lo=int(u);return v[lo]+(u-lo)*(v[min(lo+1,len(v)-1)]-v[lo])
def interval(v):return [quant(v,.025),quant(v,.975)]
for x,z in zip(interval(rates),r['uncertainty']['base_rate_95']):ck(x,z)
for name,prob in probs.items():
 out=r['models'][name];ck(prob,out['probability']);cl=min(max(prob,1e-12),1-1e-12)
 # Bernoulli affine sufficient-statistic identities, rather than per-row evaluator.
 brier=lambda q:prob**2+q*(1-2*prob)
 loss=lambda q:-math.log1p(-cl)+q*(math.log1p(-cl)-math.log(cl))
 ck(brier(rate),out['brier']);ck(loss(rate),out['log_loss']);ck(rate-prob,out['calibration']['observed_minus_predicted'])
 for metric,fn in [('brier',brier),('log_loss',loss),('calibration_gap',lambda q:q-prob)]:
  for x,z in zip(interval([fn(q) for q in rates]),r['uncertainty']['models'][name][metric]):ck(x,z)
for field,label in [('net','networks'),('magType','magnitude_types'),('status','status')]:assert dict(Counter(x[field] for x in rows))==r['data_audit'][label]
for field,n in r['data_audit']['missing_by_field'].items():ck(sum(not x[field].strip() for x in rows),n)
print(json.dumps({'status':'PASS','raw_sha256':r['raw_sha256'],'raw_rows':len(rows),'days':730,'calibration_events':sum(counts[:365]),'test_events':sum(counts[365:]),'numeric_checks':len(gaps),'maximum_gap':max(gaps),'scope':'Independent raw filtering/calendar/counts/monthly count and source audits; all four scores and 2000 circular bootstrap score intervals via sufficient-statistic algebra','not_verified':['Catalog completeness or original historical vintage','Clinical or disaster utility','Lag autocorrelation estimator','Author negative-control implementation'],'limits':'Historical revised catalog, no novel predictor or prospective guarantee; bootstrap implementation details disclosed after initial result; independent code uses same documented Python RNG.'},indent=2))
