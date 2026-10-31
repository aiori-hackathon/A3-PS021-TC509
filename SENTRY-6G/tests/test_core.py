import sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from core import Store
@pytest.fixture
def s(tmp_path):
 x=Store(tmp_path/'db.sqlite');yield x;x.close()
def test_id_correlation(s):
 a=s.create('A1','QoS=high');b=s.create('A1','QoS=high');assert a['dialog_id']==b['dialog_id'];assert a['b_id']==b['b_id']
def test_conflicting_request(s):
 s.create('A1','x')
 with pytest.raises(ValueError):s.create('A1','y')
def test_atomic_dedup(s):
 d=s.create('A1','x');x=s.execute(d['op_id'],'x');y=s.execute(d['op_id'],'x');assert not x['duplicate'] and y['duplicate'] and s.stats()['effects']==1
def test_conflicting_effect(s):
 d=s.create('A1','x');s.execute(d['op_id'],'x')
 with pytest.raises(ValueError):s.execute(d['op_id'],'y')
def test_lost_ack_and_recovery(s):
 d=s.create('A1','x');s.transition(d['dialog_id'],'DISPATCHED');s.execute(d['op_id'],'x');s.resolve(d['dialog_id'],{'classification':'UNKNOWN','result':None});assert s.get(d['dialog_id'])['state']=='UNCERTAIN';s.resolve(d['dialog_id'],s.evidence(d['op_id']));assert s.get(d['dialog_id'])['state']=='COMPLETED'
def test_restart(tmp_path):
 p=tmp_path/'restart.db';s=Store(p);d=s.create('A1','x');s.transition(d['dialog_id'],'DISPATCHED');s.execute(d['op_id'],'x');s.close();s2=Store(p);assert s2.get(d['dialog_id'])['op_id']==d['op_id'];assert s2.evidence(d['op_id'])['classification']=='VERIFIED_DONE';s2.close()
def test_invalid_transition(s):
 d=s.create('A1','x')
 with pytest.raises(ValueError):s.transition(d['dialog_id'],'COMPLETED')
def test_not_executed_evidence(s):
 d=s.create('A1','x');assert s.evidence(d['op_id'])['classification']=='VERIFIED_NOT_EXECUTED'
def test_concurrent_duplicates(s):
 d=s.create('A1','x');out=[]
 def work():out.append(s.execute(d['op_id'],'x'))
 threads=[threading.Thread(target=work) for _ in range(12)]
 for t in threads:t.start()
 for t in threads:t.join()
 assert len(out)==12 and sum(not x['duplicate'] for x in out)==1 and s.stats()['effects']==1
