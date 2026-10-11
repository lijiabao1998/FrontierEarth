"""Independent catalog/calendar/Fraction lag verification, no fit or bootstrap."""
import argparse,calendar,copy,csv,datetime as dt,hashlib,json,math,sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from admission_guard import require_admission
from common import compare
START=dt.date(2017,1,1);MONTHS=tuple(f'{y}-{m:02d}' for y in (2017,2018) for m in range(1,13))
NULL_MONTHS=('2017-01','2017-04','2017-09','2018-02','2018-06','2018-10')
NUMERIC_SEGMENTS=('calibration','test')+tuple(m for m in MONTHS if m not in NULL_MONTHS)
CONTROL_NAMES=tuple('LAG_PLUS_001_'+x for x in NUMERIC_SEGMENTS)+tuple('NULL_TO_ZERO_'+x for x in NULL_MONTHS)+('DAILY_MARCH23_TO24','MONTHLY_ONLY_MARCH_LAG_PLUS_001')
LAG='lag1_occurrence_autocorrelation'
def write(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def summary(counts):
 n=len(counts);ys=[int(c>0) for c in counts];k=sum(ys);adj=sum(ys[i]*ys[i+1] for i in range(n-1));end=ys[0]+ys[-1]
 numerator=n*n*adj+n*k*end-(n+1)*k*k;denominator=n*k*(n-k)
 rho=float(Fraction(numerator,denominator)) if denominator else None
 total=sum(counts);square=sum(c*c for c in counts)
 variance_over_mean=float(Fraction(n*square-total*total,(n-1)*total)) if total else None
 return {'days':n,'events':total,'active_days':k,'active_day_rate':float(Fraction(k,n)),'multiple_event_days':sum(c>1 for c in counts),'maximum_events_per_day':max(counts),'daily_count_variance_over_mean':variance_over_mean,LAG:rho}, {'N':n,'K':k,'A':adj,'E':end,'numerator':numerator,'denominator':denominator,'lag':rho}
def csv_months(path):
 with path.open(encoding='utf-8',newline='') as f:
  reader=csv.DictReader(f);expected=['month','days','events','active_days','active_day_rate','multiple_event_days','maximum_events_per_day','daily_count_variance_over_mean',LAG]
  if reader.fieldnames!=expected:raise RuntimeError('monthly CSV schema')
  answer=[]
  for r in reader:
   if None in r or any(v is None for v in r.values()):raise RuntimeError('monthly CSV malformed')
   answer.append({k:r[k] if k=='month' else int(r[k]) if k in ('days','events','active_days','multiple_event_days','maximum_events_per_day') else None if r[k]=='' else float(r[k]) for k in expected})
 return answer
def claims_check(expected,r,daily,monthly):
 errors=[];gaps=[]
 try:
  if len(daily)!=730 or len(monthly)!=24 or len(r['monthly'])!=24:raise ValueError('calendar domain')
  observed={'calibration':r['calibration'],'test':r['test'],'monthly':r['monthly']}
  for year in ('calibration','test'):
   projected={k:observed[year][k] for k in expected[year]};q=compare(expected[year],projected,1e-12,year);errors+=q['errors'];gaps.append(q['max_numeric_gap'])
  q=compare(expected['monthly'],r['monthly'],1e-12,'monthly_json');errors+=q['errors'];gaps.append(q['max_numeric_gap'])
  q=compare(expected['monthly'],monthly,1e-12,'monthly_csv');errors+=q['errors'];gaps.append(q['max_numeric_gap'])
  q=compare(r['monthly'],monthly,1e-12,'monthly_crossfile');errors+=q['errors'];gaps.append(q['max_numeric_gap'])
  for i,row in enumerate(daily):
   want=expected['daily'][i]
   q=compare(want,{k:row[k] for k in want},0,'daily.'+str(i));errors+=q['errors']
 except (KeyError,TypeError,ValueError,OverflowError) as exc:errors.append({'path':'domain','reason':str(exc)})
 return {'accepted':not errors,'errors':errors,'max_numeric_gap':max(gaps,default=0.0)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--round',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();here=Path(__file__).resolve().parent
 require_admission(a.repo,a.round,'EARTH-003',here/'PROTOCOL.json');protocol=json.loads((here/'PROTOCOL.json').read_text(encoding='utf-8'))
 if tuple(x['name'] for x in protocol['controls'])!=CONTROL_NAMES or len(CONTROL_NAMES)!=28:raise RuntimeError('fixed 28-control contract changed')
 raw=here/'reference/catalog.csv'
 if hashlib.sha256(raw.read_bytes()).hexdigest()!='57ef5435662f29488ad9fe6cd86bd1bb30ea7a530b5ab1810361c8f36508b386':raise RuntimeError('catalog bytes changed')
 with raw.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 if len(rows)!=27:raise RuntimeError('frozen raw row count')
 seen=set();counts=Counter();events=[]
 for row in rows:
  event=row['id'];time=dt.datetime.fromisoformat(row['time'].replace('Z','+00:00'))
  if time.tzinfo is None or not event or event in seen:raise RuntimeError('catalog identity/time malformed')
  seen.add(event);time=time.astimezone(dt.timezone.utc);values=[float(row[k]) for k in ('latitude','longitude','depth','mag')]
  if not all(math.isfinite(x) for x in values):raise RuntimeError('nonfinite catalog field')
  lat,lon,depth,mag=values
  if not (dt.datetime(2017,1,1,tzinfo=dt.timezone.utc)<=time<dt.datetime(2019,1,1,tzinfo=dt.timezone.utc) and 32<=lat<=42 and -125<=lon<=-114 and -100<=depth<=1000 and mag>=4 and row['type']=='earthquake'):raise RuntimeError('out-of-domain event')
  counts[time.date()]+=1;events.append({'id':event,'date_utc':time.date().isoformat()})
 daily_expected=[];by_month={m:[] for m in MONTHS};all_counts=[]
 for i in range(730):
  day=START+dt.timedelta(days=i);c=counts[day];all_counts.append(c);by_month[day.strftime('%Y-%m')].append(c)
  daily_expected.append({'date_utc':day.isoformat(),'split':'calibration' if i<365 else 'test','count':c,'occurrence':int(c>0)})
 expected={'daily':daily_expected};sufficient={}
 for key,cs in [('calibration',all_counts[:365]),('test',all_counts[365:])]:expected[key],sufficient[key]=summary(cs)
 expected['monthly']=[]
 for month in MONTHS:
  diagnostic,sufficient[month]=summary(by_month[month]);expected['monthly'].append({'month':month,**diagnostic})
 if tuple(x['month'] for x in expected['monthly'] if x[LAG] is None)!=NULL_MONTHS or sum(v['lag'] is not None for v in sufficient.values())!=20:raise RuntimeError('lag numeric/null domain mismatch')
 r=json.loads((here/'reference/author-results.json').read_text(encoding='utf-8'))
 with (here/'reference/daily.csv').open(encoding='utf-8',newline='') as f:
  reader=csv.DictReader(f)
  if reader.fieldnames!=protocol['daily_csv_header']:raise RuntimeError('daily header')
  daily=[{k:int(v) if k in ('count','occurrence') else v for k,v in row.items()} for row in reader]
 monthly=csv_months(here/'reference/monthly.csv');baseline=claims_check(expected,r,daily,monthly)
 out=a.output.parent;write(out/'independent-calendar-lag.json',{'events':events,'daily':daily_expected,'monthly':expected['monthly'],'calibration':expected['calibration'],'test':expected['test'],'sufficient_statistics':sufficient})
 controls=[];directory=out/'controls';directory.mkdir(exist_ok=False)
 for name in CONTROL_NAMES:
  mr=copy.deepcopy(r);md=copy.deepcopy(daily);mm=copy.deepcopy(monthly)
  if name.startswith('LAG_PLUS_001_'):
   segment=name[len('LAG_PLUS_001_'):]
   if segment in ('calibration','test'):mr[segment][LAG]+=.01
   else:
    j=MONTHS.index(segment);mr['monthly'][j][LAG]+=.01;mm[j][LAG]+=.01
  elif name.startswith('NULL_TO_ZERO_'):
   j=MONTHS.index(name[len('NULL_TO_ZERO_'):]);mr['monthly'][j][LAG]=0;mm[j][LAG]=0
  elif name=='DAILY_MARCH23_TO24':
   old=next(x for x in md if x['date_utc']=='2018-03-23');new=next(x for x in md if x['date_utc']=='2018-03-24')
   if (old['count'],old['occurrence'],new['count'],new['occurrence'])!=(1,1,0,0):raise RuntimeError('frozen event shift precondition')
   old.update(count=0,occurrence=0);new.update(count=1,occurrence=1)
   if sum(x['count'] for x in md if x['date_utc'].startswith('2018-03'))!=3:raise RuntimeError('shift changed monthly events')
  elif name=='MONTHLY_ONLY_MARCH_LAG_PLUS_001':mm[MONTHS.index('2018-03')][LAG]+=.01
  else:raise RuntimeError('unknown control')
  case=directory/name;case.mkdir();write(case/'claimed-results.json',mr)
  for filename,rs in [('daily.csv',md),('monthly.csv',mm)]:
   with (case/filename).open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rs[0]));writer.writeheader();writer.writerows(rs)
  loaded_json=json.loads((case/'claimed-results.json').read_text(encoding='utf-8'))
  with (case/'daily.csv').open(encoding='utf-8',newline='') as f:loaded_daily=[{k:int(v) if k in ('count','occurrence') else v for k,v in row.items()} for row in csv.DictReader(f)]
  loaded_monthly=csv_months(case/'monthly.csv')
  check=claims_check(expected,loaded_json,loaded_daily,loaded_monthly);write(case/'semantic-check.json',check)
  controls.append({'name':name,'rejected':check['accepted'] is False,'errors':check['errors'],'directory':case.relative_to(out).as_posix()})
 anchors={'calibration':-.0311585790573485,'test':.01939445382109354,'2018-03':.2584485407066052,'2017-03':-.03670745272525029}
 anchor_check=compare(anchors,{k:sufficient[k]['lag'] for k in anchors},1e-12)
 ok=baseline['accepted'] is True and anchor_check['accepted'] is True and tuple(x['name'] for x in controls)==CONTROL_NAMES and len(controls)==28 and all(x['rejected'] is True for x in controls)
 result={'problem':'EARTH-003','baseline':baseline,'lag_fields':26,'numeric_lag_fields':20,'exact_null_fields':6,'lag_sufficient_statistics':sufficient,'anchor_check':anchor_check,'controls':controls,'control_count':28,'all_criteria_passed':ok,'verdict':'INDEPENDENT_ARCHIVED_CALENDAR_LAG_PASS' if ok else 'FAIL_CLOSED','legacy_checker_executed':False,'limits':protocol['limits']}
 write(a.output,result);print(json.dumps({'verdict':result['verdict'],'lag_fields':26,'numeric':20,'null':6,'max_numeric_gap':baseline['max_numeric_gap'],'controls_rejected':sum(x['rejected'] for x in controls),'all_criteria_pass':ok}));return 0 if ok else 1
if __name__=='__main__':
 try:sys.exit(main())
 except Exception:
  import traceback;traceback.print_exc();sys.exit(2)
