"""Development gate: native prompt review is bound to the exact staged batch."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from test_native_plugin import installation
from test_dev56 import _init_128

API='/casting-studio/api'

def request_fixture(installation):
    c,p,session,body=_init_128(installation)
    body['choice_keys']=[x['key'] for x in c.get(API+'/choices').json()][:3]
    return c,p,session,body

def review(c,body):
    r=c.post(API+'/generator/batch/preview',json=body)
    assert r.status_code==200,r.text
    data=r.json();assert len(data['tasks'])==data['count']==3
    assert data['review_token']
    return data

def test_review_matches_native_and_concurrent_replay_is_idempotent(installation):
    c,p,session,body=request_fixture(installation)
    data=review(c,body);req={**body,'review_token':data['review_token']}
    with ThreadPoolExecutor(max_workers=2) as workers:
        replies=list(workers.map(lambda _:c.post(API+'/generator/batch/submit',json=req),range(2)))
    assert all(r.status_code==200 for r in replies),[r.text for r in replies]
    assert replies[0].json()==replies[1].json()
    assert len(p.queue_bridge._pending)==1
    p.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests)==1
    assert [s['prompt'] for s in session.manifests[0]]==[t['prompt'] for t in data['tasks']]
    assert c.post(API+'/generator/batch/submit',json=req).json()==replies[0].json()
    assert len(p.queue_bridge._pending)==0
    s=import_module('cb_under_test.app.server');s.casting_reviews.clear()
    assert c.post(API+'/generator/batch/submit',json=req).json()==replies[0].json()
    assert len(session.manifests)==1

def test_concurrent_prompt_edit_invalidates_entire_review(installation):
    c,p,session,body=request_fixture(installation)
    data=review(c,body);req={**body,'review_token':data['review_token']}
    task={**body['task'],'choice_key':body['choice_keys'][1]}
    r=c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':'A completely different saved prompt from another tab.'})
    assert r.status_code==200,r.text
    r=c.post(API+'/generator/batch/submit',json=req)
    assert r.status_code==409,r.text
    assert not p.queue_bridge._pending and not session.manifests
    new=review(c,body)
    assert new['tasks'][1]['prompt']=='A completely different saved prompt from another tab.'
    r=c.post(API+'/generator/batch/submit',json={**body,'review_token':new['review_token']})
    assert r.status_code==200,r.text
    p.queue_bridge.process_pending_in_gradio(session)
    assert [s['prompt'] for s in session.manifests[0]]==[t['prompt'] for t in new['tasks']]

def test_review_does_not_allow_changed_settings_or_scope(installation):
    c,p,session,body=request_fixture(installation)
    data=review(c,body);req={**body,'review_token':data['review_token']}
    for changed in ({**req,'task':{**req['task'],'seed':42}},{**req,'choice_keys':req['choice_keys'][::-1]}):
        r=c.post(API+'/generator/batch/submit',json=changed)
        assert r.status_code==409,r.text
    assert not p.queue_bridge._pending and not session.manifests

def test_independent_reviews_overlap_and_deliberate_repeat(installation):
    c,p,session,body=request_fixture(installation)
    single={**body['task'],'choice_key':body['choice_keys'][0]}
    data=review(c,body)
    assert c.post(API+'/generator/submit',json=single).status_code==409
    first=c.post(API+'/generator/preview',json=single).json()
    r=c.post(API+'/generator/submit',json={**single,'review_token':first['review_token']});assert r.status_code==200,r.text
    r=c.post(API+'/generator/batch/submit',json={**body,'review_token':data['review_token']});assert r.status_code==409,r.text
    assert len(p.queue_bridge._pending)==1
    gate=c.post(API+'/generator/batch/preflight',json=body).json();assert gate['blocked']==1 and gate['ready']==2
    p.queue_bridge.process_pending_in_gradio(session)
    single['queue_pass']='deliberate-new-pass'
    second=c.post(API+'/generator/preview',json=single).json()
    r=c.post(API+'/generator/submit',json={**single,'review_token':second['review_token']});assert r.status_code==200,r.text
    assert len(p.queue_bridge._pending)==1

def test_image_set_individual_reviews_bind_every_native_prompt(installation):
    from test_dev512_image_sets import _image_session,_set_image_template
    from test_native_plugin import _mock_fork,_create_public_selection
    c,p,root,_=installation;_mock_fork(root)
    session=_image_session();p.queue_bridge.api_session=session;p.queue_bridge.dispatch_mode='gradio'
    key=_create_public_selection(c);_set_image_template(c,count=3)
    task={'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint','scene':1}
    rows=[c.post(API+'/generator/preview',json={**task,'scene':i}).json() for i in range(1,4)]
    tokens=[r['review_token'] for r in rows]
    req={'task':task,'scope':'selection:'+key,'scene_mode':'all','review_tokens':tokens}
    assert c.post(API+'/generator/batch/submit',json={**req,'review_tokens':tokens[::-1]}).status_code==409
    r=c.post(API+'/generator/batch/submit',json=req);assert r.status_code==200,r.text
    p.queue_bridge.process_pending_in_gradio(session)
    assert [s['prompt'] for s in session.manifests[0]]==[r['prompt'] for r in rows]

def test_video_defaults_cannot_duplicate_native_tasks(installation):
    c,p,session,body=request_fixture(installation)
    original=session.merge_settings_with_defaults
    session.merge_settings_with_defaults=lambda data:{**original(data),'batch_size':7,'repeat_generation':9}
    data=review(c,body)
    r=c.post(API+'/generator/batch/submit',json={**body,'review_token':data['review_token']});assert r.status_code==200,r.text
    p.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests[0])==3
    assert all(x['batch_size']==x['repeat_generation']==1 for x in session.manifests[0])

def test_additive_upgrade_preserves_existing_tables_and_artifacts(installation):
    c,p,session,body=request_fixture(installation)
    s=import_module('cb_under_test.app.server')
    from pathlib import Path
    import sqlite3,hashlib
    root=installation[2];dbpath=root/'user_data'/'casting.sqlite3'
    with sqlite3.connect(dbpath) as db:
        for table in ('casting_review_receipts','casting_review_tasks'):db.execute('DROP TABLE '+table)
        before={name:(schema,db.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall()) for name,schema in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
    assert len(before)==31
    files={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file() and f!=dbpath}
    with s.connect() as db:
        after={name:(schema,db.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall()) for name,schema in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
    assert set(after)-set(before)=={'casting_review_receipts','casting_review_tasks'}
    assert all(after[k]==v for k,v in before.items())
    assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==digest for f,digest in files.items())
