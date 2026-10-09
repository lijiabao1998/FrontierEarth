"""One frozen, retrospective catalog occurrence baseline. Standard library only."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from collections import Counter

ROOT=Path(__file__).resolve().parents[4]
ROUND=ROOT/'runs/20261009T105820460779Z-gpt-EARTH-003'
OUT=ROOT/'problems/EARTH-003/results/catalog-poisson'
UTC=dt.timezone.utc
START=dt.datetime(2017,1,1,tzinfo=UTC)
SPLIT=dt.datetime(2018,1,1,tzinfo=UTC)
END=dt.datetime(2019,1,1,tzinfo=UTC)
EPS=1e-12

def timestamp(value):
    t=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('Timezone required')
    return t.astimezone(UTC)

def parse_rows(rows):
    seen=set(); accepted=[]; excluded=[]
    for row in rows:
        eid=row['id']
        if not eid or eid in seen: raise ValueError('Empty or duplicate event ID')
        seen.add(eid)
        t=timestamp(row['time'])
        values={key:float(row[key]) for key in ('latitude','longitude','depth','mag')}
        if not all(math.isfinite(x) for x in values.values()): raise ValueError('Nonfinite required field')
        inside=(START<=t<END and 32<=values['latitude']<=42 and -125<=values['longitude']<=-114
                and -100<=values['depth']<=1000 and values['mag']>=4 and row['type']=='earthquake')
        if inside: accepted.append((t,eid,values,row))
        else: excluded.append(eid)
    return sorted(accepted,key=lambda event:(event[0],event[1])),excluded

def daily(events):
    counts=[0]*((END-START).days)
    for t,*_ in events: counts[(t-START).days]+=1
    return counts

def fit(counts):
    if not counts or sum(counts)==0: raise ValueError('Empty calibration catalog')
    rate=sum(counts)/len(counts)
    return {'lambda_events_per_day':rate,'poisson':-math.expm1(-rate),'bernoulli_climatology':sum(c>0 for c in counts)/len(counts),'zero':0.0,'half':0.5}

def score(ys,p):
    if not ys or not 0<=p<=1 or any(y not in (0,1) for y in ys): raise ValueError('Invalid score input')
    pc=min(1-EPS,max(EPS,p))
    return {'brier':statistics.fmean((p-y)**2 for y in ys),'log_loss':-statistics.fmean(y*math.log(pc)+(1-y)*math.log1p(-pc) for y in ys)}

def quantile(values,q):
    x=sorted(values);position=(len(x)-1)*q;lo=math.floor(position);hi=math.ceil(position)
    return x[lo]+(x[hi]-x[lo])*(position-lo)

def block_indices(n,rng,block=30):
    indices=[]
    while len(indices)<n:
        start=rng.randrange(n)
        indices.extend((start+k)%n for k in range(block))
    return indices[:n]

def bootstrap(ys,probabilities):
    # Resample contiguous daily blocks, never individual earthquakes. Training p stays fixed.
    rng=random.Random(196003);replicates={name:{'brier':[],'log_loss':[],'calibration_gap':[]} for name in probabilities};base_rates=[]
    for _ in range(2000):
        sample=[ys[i] for i in block_indices(len(ys),rng)]
        mean=statistics.fmean(sample);base_rates.append(mean)
        for name,p in probabilities.items():
            scores=score(sample,p)
            for key,value in scores.items():replicates[name][key].append(value)
            replicates[name]['calibration_gap'].append(mean-p)
    interval=lambda values:[quantile(values,.025),quantile(values,.975)]
    return {'method':'fixed-p circular moving-block percentile interval; descriptive, no independent-events claim','block_days':30,'resamples':2000,'seed':196003,'base_rate_95':interval(base_rates),'models':{name:{key:interval(v) for key,v in values.items()} for name,values in replicates.items()}}

def diagnostics(counts):
    ys=[int(c>0) for c in counts];mean=statistics.fmean(counts);ym=statistics.fmean(ys)
    denom=sum((y-ym)**2 for y in ys)
    return {'days':len(counts),'events':sum(counts),'active_days':sum(ys),'active_day_rate':ym,'multiple_event_days':sum(c>1 for c in counts),'maximum_events_per_day':max(counts),'daily_count_variance_over_mean':statistics.variance(counts)/mean if mean else None,'lag1_occurrence_autocorrelation':sum((a-ym)*(b-ym) for a,b in zip(ys[:-1],ys[1:]))/denom if denom else None}

def main():
    r=json.loads((ROUND/'round.json').read_text());assert r.get('admitted_at'),'Admission required'
    raw=(OUT/'catalog.csv').read_bytes();retrieval=json.loads((OUT/'retrieval.json').read_text())
    digest=hashlib.sha256(raw).hexdigest();assert digest==retrieval['requests'][0]['sha256'],'Raw bytes changed'
    rows=list(csv.DictReader(raw.decode('utf-8').splitlines()))
    assert 0<len(rows)<20000 and len(rows)==int((OUT/'count.txt').read_text()),'Incomplete or inconsistent retrieval'
    events,excluded=parse_rows(rows);counts=daily(events);cal=counts[:365];test=counts[365:];ys=[int(c>0) for c in test];fitted=fit(cal)
    probabilities={k:v for k,v in fitted.items() if k!='lambda_events_per_day'}
    scores={name:{'probability':p,**score(ys,p),'calibration':{'n':len(ys),'mean_prediction':p,'observed_frequency':statistics.fmean(ys),'observed_minus_predicted':statistics.fmean(ys)-p},'alarm_diagnostic':{'threshold':.5,'alarm_day_rate':float(p>=.5),'false_positive_rate':float(p>=.5) if 0 in ys else None,'missed_event_day_rate':float(p<.5) if 1 in ys else None,'lead_time':'NOT_APPLICABLE'}} for name,p in probabilities.items()}
    fields=rows[0].keys()
    monthly=[]
    for year in (2017,2018):
        for month in range(1,13):
            monthcounts=[c for i,c in enumerate(counts) if (START+dt.timedelta(days=i)).year==year and (START+dt.timedelta(days=i)).month==month]
            monthly.append({'month':f'{year}-{month:02d}',**diagnostics(monthcounts)})
    result={'kind':'historical public catalog baseline reproduction; NOT a prospective forecast','raw_sha256':digest,'raw_rows':len(rows),'count_endpoint_rows':int((OUT/'count.txt').read_text()),'retained_events':len(events),'excluded_ids':excluded,'calibration':diagnostics(cal),'test':diagnostics(test),'fitted':fitted,'models':scores,'uncertainty':bootstrap(ys,probabilities),'monthly':monthly,'data_audit':{'missing_by_field':{k:sum(not row[k].strip() for row in rows) for k in fields},'networks':dict(Counter(row['net'] for row in rows)),'magnitude_types':dict(Counter(row['magType'] for row in rows)),'status':dict(Counter(row['status'] for row in rows))},'parent_status':'OPEN','novelty':'NONE: first frozen baseline; no performance gain required or claimed','limitations':json.loads((ROUND/'frozen-spec.json').read_text())['caveats']}
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    with (OUT/'daily.csv').open('w',newline='') as fp:
        writer=csv.writer(fp);writer.writerow(['date_utc','split','count','occurrence',*probabilities])
        for i,c in enumerate(counts):writer.writerow([(START+dt.timedelta(days=i)).date().isoformat(),'calibration' if i<365 else 'test',c,int(c>0),*probabilities.values()])
    with (OUT/'monthly.csv').open('w',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(monthly[0]));writer.writeheader();writer.writerows(monthly)
    print(json.dumps({'raw_sha256':digest,'calibration':result['calibration'],'test':result['test'],'models':scores,'uncertainty':result['uncertainty']},indent=2))

if __name__=='__main__':main()
