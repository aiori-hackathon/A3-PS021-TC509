"""Launch independent services: python service.py executor|coordinator|requester"""
import os,sys,time,random
from pathlib import Path
import httpx
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core import Store

ROLE=sys.argv[1] if len(sys.argv)>1 and sys.argv[1] in ('executor','coordinator','requester') else os.getenv('SENTRY_ROLE','coordinator')
BASE=Path(__file__).resolve().parent
DB_DIR=Path(os.getenv('SENTRY_DATA',str(BASE/'data')));DB_DIR.mkdir(parents=True,exist_ok=True)
store=Store(DB_DIR/('executor.db' if ROLE=='executor' else 'coordinator.db')) if ROLE!='requester' else None
EXECUTOR=os.getenv('SENTRY_EXECUTOR','http://127.0.0.1:8002');COORDINATOR=os.getenv('SENTRY_COORDINATOR','http://127.0.0.1:8001')
app=FastAPI(title=f'SENTRY-6G {ROLE}',version='0.2.0')
class Request(BaseModel):
 a_id:str;command:str;fault:str='none';rtt_ms:int=0;loss_pct:float=0
class Effect(BaseModel):op_id:str;command:str
class Evidence(BaseModel):classification:str;result:dict|None=None

@app.get('/health')
def health():return {'role':ROLE,'ok':True,'experimental':True}

if ROLE=='executor':
 @app.post('/execute')
 def execute(x:Effect):
  try:return store.execute(x.op_id,x.command)
  except ValueError as e:raise HTTPException(409,str(e))
 @app.get('/status/{op}')
 def status(op:str):return store.evidence(op)
 @app.get('/effects')
 def effects():return store.stats()

if ROLE=='coordinator':
 app.mount('/static',StaticFiles(directory=str(BASE/'web')),name='static')
 @app.get('/')
 def home():return FileResponse(BASE/'web'/'index.html')
 def fetch_status(op,fault='none'):
  if fault=='partition':return {'classification':'UNKNOWN','result':None}
  try:
   with httpx.Client(timeout=2) as client:
    r=client.get(f'{EXECUTOR}/status/{op}');r.raise_for_status();return r.json()
  except (httpx.HTTPError,ValueError):return {'classification':'UNKNOWN','result':None}
 @app.post('/submit')
 def submit(x:Request):
  if x.fault not in ('none','lost_ack','partition','duplicate','delay','restart'):raise HTTPException(422,'Unknown fault')
  if x.rtt_ms<0 or not 0<=x.loss_pct<=100:raise HTTPException(422,'Invalid network parameters')
  try:dialog=store.create(x.a_id,x.command)
  except ValueError as e:raise HTTPException(409,str(e))
  d=dialog['dialog_id'];op=dialog['op_id']
  if dialog['state']=='COMPLETED':return {'dialog':dialog,'evidence':'VERIFIED_DONE','deduplicated':True}
  if dialog['state']=='CREATED':store.transition(d,'DISPATCHED')
  if dialog['state']=='UNCERTAIN':
   ev=fetch_status(op,'partition' if x.fault=='partition' else 'none');return {'dialog':store.resolve(d,ev),'evidence':ev['classification'],'deduplicated':True}
  if x.fault=='delay':time.sleep(min(x.rtt_ms/1000,2))
  # An unreachable executor must never be treated as VERIFIED_NOT_EXECUTED.
  if x.fault=='partition':
   ev={'classification':'UNKNOWN','result':None};store.log(d,'FAULT','Partition before dispatch');return {'dialog':store.resolve(d,ev),'evidence':'UNKNOWN','deduplicated':False}
  try:
   with httpx.Client(timeout=3) as client:
    r=client.post(f'{EXECUTOR}/execute',json={'op_id':op,'command':x.command});r.raise_for_status();payload=r.json()
    if x.fault=='duplicate':
     r2=client.post(f'{EXECUTOR}/execute',json={'op_id':op,'command':x.command});r2.raise_for_status();payload['duplicate_retry']=r2.json()['duplicate']
  except httpx.HTTPError:
   ev={'classification':'UNKNOWN','result':None};store.log(d,'FAULT','Executor unreachable');return {'dialog':store.resolve(d,ev),'evidence':'UNKNOWN','deduplicated':False}
  if x.fault in ('lost_ack','restart'):
   store.log(d,'FAULT','Acknowledgment lost after executor commit');ev={'classification':'UNKNOWN','result':None}
  else:ev={'classification':'VERIFIED_DONE','result':payload['result']}
  return {'dialog':store.resolve(d,ev),'evidence':ev['classification'],'deduplicated':payload['duplicate'],'duplicate_retry':payload.get('duplicate_retry',False)}
 @app.post('/recover/{d}')
 def recover(d:str):
  try:x=store.get(d)
  except KeyError:raise HTTPException(404,'Unknown dialog')
  if x['state']=='COMPLETED':return {'dialog':x,'evidence':'VERIFIED_DONE'}
  ev=fetch_status(x['op_id']);return {'dialog':store.resolve(d,ev),'evidence':ev['classification']}
 @app.get('/dialogs')
 def dialogs():return store.dialogs()
 @app.get('/events')
 def events():return store.events()
 @app.get('/stats')
 def stats():
  local=store.stats()
  try:
   with httpx.Client(timeout=2) as client:
    r=client.get(f'{EXECUTOR}/effects');r.raise_for_status(); remote=r.json()
   local['effects']=remote['effects'];local['effects_source']='executor';local['effects_available']=True
  except (httpx.HTTPError,ValueError,KeyError,TypeError):
   local['effects']=None;local['effects_source']='unavailable';local['effects_available']=False
  return local
 @app.get('/audit/{op}')
 def audit(op:str):
  try:
   with httpx.Client(timeout=2) as client:
    r=client.get(f'{EXECUTOR}/status/{op}');r.raise_for_status()
    return {'op_id':op,'executor_evidence':r.json()}
  except httpx.HTTPError as e:raise HTTPException(503,f'Executor unavailable: {e}')
 @app.get('/executor-health')
 def executor_health():
  try:
   with httpx.Client(timeout=1) as client:
    r=client.get(f'{EXECUTOR}/health');r.raise_for_status();return {'online':True}
  except httpx.HTTPError:return {'online':False}
 @app.get('/network-policy')
 def policy(rtt_ms:float=100,loss_pct:float=0,attempt:int=1):
  # Experimental policy: never changes the safety decision, only timing.
  wait=min(10,(0.25+rtt_ms/1000)*(1+loss_pct/100)*2**max(0,min(attempt,5)-1))
  return {'recommended_wait_seconds':round(wait,3),'permitted_when_unknown':['query','wait','escalate'],'method':'heuristic_not_trained'}

if ROLE=='requester':
 @app.post('/delegate')
 def delegate(x:Request):
  try:
   with httpx.Client(timeout=8) as client:
    r=client.post(f'{COORDINATOR}/submit',json=x.model_dump());r.raise_for_status();return r.json()
  except httpx.HTTPError as e:raise HTTPException(503,str(e))

if __name__=='__main__':
 import uvicorn
 port={'requester':8000,'coordinator':8001,'executor':8002}[ROLE]
 uvicorn.run(app,host='127.0.0.1',port=port)
