"""No background work merely from opening Performers or restarting WanGP."""
from pathlib import Path
import importlib
from test_native_plugin import installation

API='/casting-studio/api'

def test_maintenance_status_read_only_and_idle(installation):
    client,plugin,root,_=installation
    response=client.get(API+'/maintenance/activity')
    assert response.status_code==200,response.text
    assert response.json()=={'running':False,'count':0,'jobs':[]}
    srv=importlib.import_module('cb_under_test.app.server')
    with srv.CREDIT_LOCK:
        srv.CREDIT_STATE.update(running=True,done=24,total=387,last='Example Person')
    response=client.get(API+'/maintenance/activity')
    assert response.status_code==200
    assert response.json()['jobs'][0]=={'id':'credits','label':'Screen-role synchronization','done':24,'total':387,'detail':'Example Person'}
    with srv.CREDIT_LOCK:srv.CREDIT_STATE.update(running=False)
    assert client.get(API+'/maintenance/activity').json()['running'] is False

def test_no_auto_launch_on_server_startup(installation,monkeypatch):
    client,plugin,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(srv,'launch_credit_sync', lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('Automatic role sync')))
    srv.startup()  # should only migrate and initialize metadata
    assert srv.CREDIT_STATE['running'] is False

def test_no_network_research_implicit_in_performers_tab(installation):
    client,plugin,root,_=installation
    html=client.get('/casting-studio/').text
    assert 'if(!force)return;const visible=' in html
    assert 'function watchPhotos(){/* Manual only:' in html
    assert 'id="maintenanceBanner"' in html
    assert 'pollMaintenanceActivity' in html
    assert 'researchVisibleCards()' in html
    assert 'None of these jobs starts when WanGP launches or you open Performers' in html
