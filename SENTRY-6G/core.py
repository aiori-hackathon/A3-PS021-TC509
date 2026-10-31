"""SENTRY-6G experimental coordination and executor simulator. No real router actions."""
import sqlite3, json, uuid, time, threading
from pathlib import Path

TRANSITIONS={'CREATED':{'DISPATCHED'},'DISPATCHED':{'UNCERTAIN','COMPLETED'},'UNCERTAIN':{'COMPLETED','ESCALATED'},'COMPLETED':set(),'ESCALATED':set()}
class Store:
 def __init__(self,path='sentry.db'):
  self.path=str(path); self.lock=threading.RLock()
  self.db=sqlite3.connect(self.path,check_same_thread=False,isolation_level=None,timeout=20)
  self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA busy_timeout=20000')
  self.db.executescript('''CREATE TABLE IF NOT EXISTS dialogs(id TEXT PRIMARY KEY,a_id TEXT UNIQUE,b_id TEXT UNIQUE,op_id TEXT UNIQUE,command TEXT,state TEXT,version INTEGER,result TEXT,created REAL);CREATE TABLE IF NOT EXISTS effects(op_id TEXT PRIMARY KEY,command TEXT,result TEXT,at REAL);CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,dialog_id TEXT,kind TEXT,detail TEXT,at REAL);''')
 def log(self,d,kind,detail=''):
  self.db.execute('INSERT INTO events(dialog_id,kind,detail,at) VALUES(?,?,?,?)',(d,kind,detail,time.time()))
 def create(self,a_id,command):
  with self.lock:
   row=self.db.execute('SELECT id,command FROM dialogs WHERE a_id=?',(a_id,)).fetchone()
   if row:
    if row[1]!=command:raise ValueError('Request identity reused with different payload')
    return self.get(row[0])
   d='D-'+uuid.uuid4().hex[:12];b='B-'+uuid.uuid4().hex[:12];op='OP-'+uuid.uuid4().hex[:12]
   self.db.execute('INSERT INTO dialogs VALUES(?,?,?,?,?,?,?,?,?)',(d,a_id,b,op,command,'CREATED',0,None,time.time()))
   self.log(d,'CREATED','Global and local IDs assigned');return self.get(d)
 def get(self,d):
  r=self.db.execute('SELECT id,a_id,b_id,op_id,command,state,version,result,created FROM dialogs WHERE id=?',(d,)).fetchone()
  if not r:raise KeyError(d)
  x=dict(zip(('dialog_id','a_id','b_id','op_id','command','state','version','result','created'),r));x['result']=json.loads(x['result']) if x['result'] else None;return x
 def transition(self,d,to):
  with self.lock:
   current=self.get(d)['state']
   if to not in TRANSITIONS[current]:raise ValueError(f'Invalid transition {current} -> {to}')
   self.db.execute('UPDATE dialogs SET state=?,version=version+1 WHERE id=? AND state=?',(to,d,current));self.log(d,to)
 def execute(self,op,command):
  with self.lock:
   self.db.execute('BEGIN IMMEDIATE')
   try:
    row=self.db.execute('SELECT command,result FROM effects WHERE op_id=?',(op,)).fetchone()
    if row:
     if row[0]!=command:raise ValueError('Idempotency-key payload mismatch')
     result=json.loads(row[1]);duplicate=True
    else:
     result={'op_id':op,'applied_setting':command,'status':'applied'}
     self.db.execute('INSERT INTO effects VALUES(?,?,?,?)',(op,command,json.dumps(result),time.time()));duplicate=False
    self.db.execute('COMMIT');return {'result':result,'duplicate':duplicate}
   except BaseException:
    self.db.execute('ROLLBACK');raise
 def evidence(self,op):
  with self.lock:
   row=self.db.execute('SELECT result FROM effects WHERE op_id=?',(op,)).fetchone()
   return {'classification':'VERIFIED_DONE','result':json.loads(row[0])} if row else {'classification':'VERIFIED_NOT_EXECUTED','result':None}
 def resolve(self,d,evidence):
  with self.lock:
   x=self.get(d);kind=evidence['classification'];self.log(d,'EVIDENCE',kind)
   if kind=='VERIFIED_DONE':
    if x['state'] in ('DISPATCHED','UNCERTAIN'):self.transition(d,'COMPLETED')
    self.db.execute('UPDATE dialogs SET result=? WHERE id=?',(json.dumps(evidence['result']),d))
   elif kind=='UNKNOWN' and x['state']=='DISPATCHED':self.transition(d,'UNCERTAIN')
   return self.get(d)
 def dialogs(self):
  with self.lock:
   ids=self.db.execute('SELECT id FROM dialogs ORDER BY created DESC').fetchall();return [self.get(x[0]) for x in ids]
 def events(self,limit=120):
  with self.lock:
   rows=self.db.execute('SELECT seq,dialog_id,kind,detail,at FROM events ORDER BY seq DESC LIMIT ?', (limit,)).fetchall()
   return [dict(zip(('seq','dialog_id','kind','detail','at'),r)) for r in rows]
 def stats(self):
  with self.lock:
   return {'dialogs':self.db.execute('SELECT COUNT(*) FROM dialogs').fetchone()[0],'effects':self.db.execute('SELECT COUNT(*) FROM effects').fetchone()[0],'uncertain':self.db.execute("SELECT COUNT(*) FROM dialogs WHERE state='UNCERTAIN'").fetchone()[0]}
 def close(self):self.db.close()
