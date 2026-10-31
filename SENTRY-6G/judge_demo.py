"""Repeatable local PS-021 demo. Requires coordinator :8001 and executor :8002.
Runs against real local services; does not restart processes or claim real network impairment.
"""
import argparse, json, time, uuid, pathlib, datetime, sys
import httpx

COORD='http://127.0.0.1:8001'; EXEC='http://127.0.0.1:8002'

def get(client, url):
 r=client.get(url);r.raise_for_status();return r.json()
def post(client,url,payload=None):
 r=client.post(url,json=payload) if payload is not None else client.post(url)
 r.raise_for_status();return r.json()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',default='reports');a=p.parse_args()
 out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 scenarios=[('lost_ack','QoS=high',0),('duplicate','QoS=medium',0),('partition','QoS=low',0),('delay','QoS=high',350),('restart','QoS=medium',0)]
 results=[]
 with httpx.Client(timeout=12) as client:
  try:
   for base in (COORD,EXEC):
    h=get(client,base+'/health');assert h['ok'],f'{base} not healthy'
   before=get(client,EXEC+'/effects')['effects']
  except Exception as e:
   print('ERROR: Start coordinator and executor before running demo:',e);return 2
  for fault,command,rtt in scenarios:
   request_id='JUDGE-'+uuid.uuid4().hex[:12];start=time.perf_counter();errors=[]
   try:
    submission=post(client,COORD+'/submit',{'a_id':request_id,'command':command,'fault':fault,'rtt_ms':rtt})
    elapsed=round((time.perf_counter()-start)*1000,2)
    d=submission['dialog'];op=d['op_id'];first_state=d['state']
    first_evidence=get(client,EXEC+'/status/'+op)
    recovered=None
    if fault in ('lost_ack','partition','restart'):
     recovered=post(client,COORD+'/recover/'+d['dialog_id']);d=recovered['dialog']
    evidence=get(client,EXEC+'/status/'+op)
    expected_effect=fault!='partition'
    actual_effect=evidence['classification']=='VERIFIED_DONE'
    if actual_effect!=expected_effect:errors.append('Executor evidence disagrees with expected effect')
    if expected_effect and d['state']!='COMPLETED':errors.append('Expected COMPLETED')
    if fault=='partition' and d['state']!='UNCERTAIN':errors.append('Partition must remain UNCERTAIN without executor effect')
    if fault=='duplicate' and submission.get('duplicate_retry') is not True:errors.append('Executor did not flag duplicate retry')
    if fault in ('lost_ack','restart') and first_state!='UNCERTAIN':errors.append('Expected UNCERTAIN before recovery')
    if fault=='partition' and first_evidence['classification']!='VERIFIED_NOT_EXECUTED':errors.append('Expected simulated executor ledger absence')
    results.append({'scenario':fault,'request_id':request_id,'dialog_id':d['dialog_id'],'op_id':op,'initial_state':first_state,'final_state':d['state'],'executor_evidence':evidence['classification'],'submit_elapsed_ms':elapsed,'deduplicated_retry':submission.get('duplicate_retry',False),'pass':not errors,'errors':errors})
   except Exception as e:
    results.append({'scenario':fault,'pass':False,'errors':[str(e)]})
  after=get(client,EXEC+'/effects')['effects']
  # Unique operation IDs + atomic executor ledger contract tested in test_core.py.
  expected_delta=sum(1 for x in results if x.get('executor_evidence')=='VERIFIED_DONE')
  ledger_delta=after-before
  overall=all(x['pass'] for x in results) and ledger_delta==expected_delta
  report={'project':'SENTRY-6G','scope':'mock adapters and simulated effects only','timestamp_utc':stamp,'notes':['restart scenario is lost-ACK simulation; actual coordinator process restart must be demonstrated separately','submit_elapsed_ms is client-observed wall time, not network RTT or full recovery latency','VERIFIED_NOT_EXECUTED is absence from simulated executor ledger at query time'],'baseline_effects':before,'final_effects':after,'new_effects':ledger_delta,'expected_new_effects':expected_delta,'passed':overall,'scenarios':results}
  j=out/('judge-demo-'+stamp+'.json');j.write_text(json.dumps(report,indent=2),encoding='utf-8')
  lines=['# SENTRY-6G — Judge Demo Evidence','',f'UTC: {stamp}',f'**Result: {"PASS" if overall else "FAIL"}**',f'Executor effects before: {before}; after: {after}; delta: {ledger_delta}; expected delta: {expected_delta}','','| Scenario | Initial state | Final state | Executor evidence | Submit ms | Result |','|---|---|---|---|---:|---|']
  for r in results:lines.append('| '+ ' | '.join([r['scenario'],r.get('initial_state','—'),r.get('final_state','—'),r.get('executor_evidence','—'),str(r.get('submit_elapsed_ms','—')),'PASS' if r['pass'] else 'FAIL'])+' |')
  lines+=['','## Important limits','- Mock adapters, simulated QoS effects; no physical 6G network or real router control.','- Restart fault does not restart the coordinator process. Demonstrate real restart manually.','- Submit time is client wall time, not a full recovery benchmark.','- Simulated ledger absence is not a universal guarantee of non-execution.','- No measured comparison against an adaptive scheduler or B2 baseline.']
  m=out/('judge-demo-'+stamp+'.md');m.write_text('\n'.join(lines)+'\n',encoding='utf-8')
  for r in results:print(('PASS' if r['pass'] else 'FAIL'),r['scenario'],r.get('final_state','ERROR'),r.get('executor_evidence',''),'; '.join(r.get('errors',[])))
  print('Ledger delta:',ledger_delta,'expected:',expected_delta,'| Overall:', 'PASS' if overall else 'FAIL')
  print('Reports:',j,m)
  return 0 if overall else 1
if __name__=='__main__':sys.exit(main())
