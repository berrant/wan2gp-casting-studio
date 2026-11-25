"""Model-family switching should never carry unsupported saved RefMods into the queue."""
import json
from test_native_plugin import installation
API='/casting-studio/api'

def _srv():
    from importlib import import_module
    return import_module('cb_under_test.app.server')

def _insert(srv,person,refmod,character):
    item={'person':person,'character':character,'production':'Sample Show',
          'refmod':refmod,'personal_id':''}
    item['key']=srv.canonical_role_key(person,character,item['production'])
    with srv.connect() as db:
        db.execute('INSERT OR REPLACE INTO choices VALUES (?,?)',(item['key'],json.dumps(item)))
    return item

def test_switch_prunes_missing_family_but_preserves_compatible_choices(installation, monkeypatch):
    client,_,root,_=installation
    srv=_srv()
    mods=[{'name':'Ada Test','path':'Ada_Test_H3.safetensors','family':'minimax_h3'},
          {'name':'Ada Test','path':'Ada_Test_Flux.safetensors','family':'flux2'},
          {'name':'Bob Test','path':'Bob_H3.safetensors','family':'minimax_h3'}]
    monkeypatch.setattr(srv,'scan',lambda:mods)
    _insert(srv,'Ada Test','Ada_Test_H3.safetensors','Protagonist')
    _insert(srv,'Bob Test','Bob_H3.safetensors','Friend')
    r=client.post(API+'/choices/reconcile',json={'family':'flux2'})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['remaining']==1 and len(data['removed'])==1 and len(data['switched'])==1
    assert data['choices'][0]['refmod']=='Ada_Test_Flux.safetensors'
    assert len(client.get(API+'/choices').json())==1
    back=client.post(API+'/choices/reconcile',json={'family':'minimax_h3'})
    assert back.status_code==200 and back.json()['choices'][0]['refmod']=='Ada_Test_H3.safetensors'
    assert back.json()['remaining']==1 # Deleted Bob is not reselected automatically.

def test_missing_file_never_falls_back_to_alternate_same_family(installation,monkeypatch):
    client,_,root,_=installation
    srv=_srv()
    monkeypatch.setattr(srv,'scan',lambda:[
        {'name':'Ada Test','path':'Other_H3.safetensors','family':'minimax_h3'},
        {'name':'Ada Test','path':'Ada_Flux.safetensors','family':'flux2'}])
    _insert(srv,'Ada Test','Deleted_H3.safetensors','Protagonist')
    r=client.post(API+'/choices/reconcile',json={'family':'minimax_h3'})
    assert r.status_code==200 and r.json()['remaining']==0
    assert len(r.json()['removed'])==1
    assert client.post(API+'/choices/reconcile',json={'family':'invalid'}).status_code==400

def test_ambiguous_cross_family_is_not_silently_replaced(installation,monkeypatch):
    client,_,root,_=installation
    srv=_srv()
    monkeypatch.setattr(srv,'scan',lambda:[
        {'name':'Ada Test','path':'Ada_H3.safetensors','family':'minimax_h3'},
        {'name':'Ada Test','path':'Ada_Flux_A.safetensors','family':'flux2'},
        {'name':'Ada Test','path':'Ada_Flux_B.safetensors','family':'flux2'}])
    _insert(srv,'Ada Test','Ada_H3.safetensors','Protagonist')
    r=client.post(API+'/choices/reconcile',json={'family':'flux2'})
    assert r.status_code==200 and r.json()['remaining']==0
    assert 'More than one' in r.json()['removed'][0]['reason']
