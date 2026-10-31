import importlib, sys
from fastapi.testclient import TestClient
import httpx

def test_stats_uses_executor_ledger(tmp_path, monkeypatch):
 monkeypatch.setenv('SENTRY_DATA',str(tmp_path))
 monkeypatch.setattr(sys,'argv',['service.py','coordinator'])
 service=importlib.import_module('service')
 class MockClient:
  def __init__(self,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def get(self,url):
   return httpx.Response(200,json={'dialogs':0,'effects':7,'uncertain':0},request=httpx.Request('GET',url))
 monkeypatch.setattr(service.httpx,'Client',MockClient)
 r=TestClient(service.app).get('/stats')
 assert r.status_code==200
 assert r.json()['effects']==7
 assert r.json()['effects_source']=='executor'

def test_stats_does_not_misreport_outage_as_zero(tmp_path,monkeypatch):
 monkeypatch.setenv('SENTRY_DATA',str(tmp_path))
 monkeypatch.setattr(sys,'argv',['service.py','coordinator'])
 import service
 class DownClient:
  def __init__(self,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def get(self,url):raise httpx.ConnectError('offline')
 monkeypatch.setattr(service.httpx,'Client',DownClient)
 r=TestClient(service.app).get('/stats')
 assert r.json()['effects'] is None
 assert r.json()['effects_available'] is False
