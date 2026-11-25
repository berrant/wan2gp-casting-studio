"""Adversarial regression cases using disposable local data only."""
import json
import pytest
from test_native_plugin import installation, _create_public_selection
from test_rc2_jackhammer import server, API, seed_reference
from PIL import Image


def test_corrupted_choices_do_not_break_startup_or_stage_batch(installation):
    c,p,*_=installation;s=server();key=_create_public_selection(c)
    damaged={'bad-json':'{','bad-shape':'null','bad-fields':'{}'}
    with s.connect() as db:
        db.executemany('INSERT INTO choices VALUES (?,?)',damaged.items())
    r=c.get(API+'/choices');assert r.status_code==200
    assert [x['key'] for x in r.json()]==[key]
    assert r.headers.get('x-casting-choice-warning')
    assert c.post(API+'/generator/preview',json={'choice_key':key,'model':'h3_video','scene':1}).status_code==200
    assert c.post(API+'/generator/preview',json={'choice_key':'bad-shape','model':'h3_video','scene':1}).status_code==409
    r=c.post(API+'/generator/batch/preview',json={'task':{'choice_key':key,'model':'h3_video'},'scope':'all'})
    assert r.status_code==409 and not p.queue_bridge._pending
    r=c.post(API+'/choices/reconcile',json={'family':'minimax_h3'});assert r.status_code==200
    assert r.json()['damaged_count']==3
    with s.connect() as db:assert dict(db.execute("SELECT key,payload FROM choices WHERE key LIKE 'bad-%'"))==damaged


def test_personal_removal_ignores_damaged_unrelated_choices(installation):
    c,_,_,_=installation;s=server();pid=c.post(API+'/personal',json={'name':'Synthetic Person'}).json()['id']
    with s.connect() as db:db.execute('INSERT INTO choices VALUES (?,?)',('broken','null'))
    assert c.delete(API+'/personal/'+pid).status_code==200
    assert c.get(API+'/personal').json()==[]
    with s.connect() as db:assert db.execute("SELECT payload FROM choices WHERE key='broken'").fetchone()==('null',)


def test_stale_public_choice_does_not_become_private_generation(installation):
    c,p,*_=installation;key=_create_public_selection(c)
    assert c.post(API+'/personal',json={'name':'Ada Test','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}).status_code==200
    task={'choice_key':key,'model':'h3_video','scene':1}
    assert c.post(API+'/generator/preview',json=task).status_code==403
    assert 'Ada Test' not in c.get(API+'/prompts/export?model=h3_video').text
    assert not p.queue_bridge._pending


def test_alias_cannot_hide_personal_name_from_reference_guard(installation):
    c,_,_,_=installation;s=server();filename='a'*24+'.jpg'
    Image.new('RGB',(800,800)).save(s.REFERENCE_DIR/filename);seed_reference(s,'ref','passed',filename)
    with s.connect() as db:db.execute('INSERT INTO identity_names VALUES (?,?)',(s.token('Example Person'),'Stage Alias'))
    s.refresh_identities()
    assert c.post(API+'/personal',json={'name':'Example Person'}).status_code==200
    assert c.get(API+'/reference-images/file/ref').status_code==403
    assert c.get(API+'/reference-images',params={'person':'Stage Alias','production':'Example Series'}).status_code==403
    assert c.get(API+'/workshop/sources').json()['sources']==[]


def test_corrupt_choices_do_not_prevent_renaming_unselected_personal(installation):
    c,_,_,_=installation;s=server();pid=c.post(API+'/personal',json={'name':'Synthetic Person'}).json()['id']
    with s.connect() as db:db.execute('INSERT INTO choices VALUES (?,?)',('broken','null'))
    assert c.put(API+'/personal/'+pid,json={'name':'Renamed Person'}).status_code==200
    assert c.get(API+'/personal').json()[0]['name']=='Renamed Person'
