"""Fault injection with isolated fixtures and simulated native jobs."""
import io
import json
from types import SimpleNamespace as NS
from PIL import Image
from test_native_plugin import installation, FakeTaskHandle
from test_rc2_jackhammer import server, API


def batch_fixture(installation, monkeypatch, after_first):
    c,p,root,_=installation;b=p.queue_bridge;s=server()
    tasks=[NS(index=i) for i in range(251)]
    b._jobs['batch']={'id':'batch','state':'queued','batch':True,'total_tasks':251,'files':[],'error':''}
    calls=[]
    def prepare(task,validate):
        validate(task)
        return {'settings':{'index':task.index}}
    def submit(chunk,callbacks):
        calls.append(chunk)
        if len(calls)==1:
            after_first(c,s)
            return FakeTaskHandle(NS(success=True,generated_files=['first-chunk.mp4'],errors=[],cancelled=False))
        raise RuntimeError('Injected second-chunk native failure')
    monkeypatch.setattr(b,'prepare',prepare)
    b.api_session=NS(submit_manifest=submit)
    return b,tasks,calls


def test_privacy_transition_between_chunks(installation,monkeypatch):
    def change(c,s):
        assert c.post(API+'/personal',json={'name':'Example Person','consent':True}).status_code==200
    b,tasks,calls=batch_fixture(installation,monkeypatch,change)
    def validate(task):server().assert_public_name('Example Person' if task.index==250 else 'Other Person')
    b._run_batch('batch',tasks,validate)
    state=b.status('batch')
    assert len(calls)==1 and state['state']=='failed'
    assert state['files']==['first-chunk.mp4']


def test_native_failure_retains_completed_chunk_results(installation,monkeypatch):
    b,tasks,calls=batch_fixture(installation,monkeypatch,lambda *_:None)
    b._run_batch('batch',tasks,lambda _:None)
    assert len(calls)==2 and b.status('batch')['state']=='failed'
    assert b.status('batch')['files']==['first-chunk.mp4']


def test_native_preview_invalid_telemetry_does_not_break_status(installation):
    c,p,*_=installation;b=p.queue_bridge
    b._jobs['sample']={'id':'sample','state':'running','progress':33}
    for v in [float('nan'),float('inf'),'not numeric']:
        b._store_preview('sample',NS(image=Image.new('RGB',(100,100)),progress=v,current_step=v,total_steps=v))
        r=c.get(API+'/generator/jobs/sample')
        assert r.status_code==200 and r.json()['progress']==33
        assert c.get(API+'/generator/jobs/sample/preview?task=1').status_code==200


def test_reference_write_failure_is_controlled_and_preserves_existing(installation,monkeypatch):
    c,_,_,_=installation;s=server()
    monkeypatch.setattr(s,'analyze_reference_image',lambda im:{'width':800,'height':800,'sharpness':100,'face_count':1,'fingerprint':'0000000000000000','hard_reasons':[],'review_reasons':[]})
    buf=io.BytesIO();Image.new('RGB',(800,800),'blue').save(buf,format='PNG')
    def upload(person):return c.post(API+'/reference-images/upload',params={'person':person},content=buf.getvalue(),headers={'content-type':'image/png'})
    assert upload('Example Person').status_code==200
    before={p.name:p.read_bytes() for p in s.REFERENCE_DIR.iterdir()}
    with s.connect() as db:db.execute("CREATE TRIGGER reject_reference BEFORE INSERT ON reference_images BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    r=upload('Other Person')
    assert r.status_code==503
    assert {p.name:p.read_bytes() for p in s.REFERENCE_DIR.iterdir()}==before
    assert len(c.get(API+'/reference-images',params={'person':'Example Person'}).json())==1
    with s.connect() as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)


def test_batch_preview_does_not_replace_overall_progress(installation):
    c,p,*_=installation;b=p.queue_bridge
    b._jobs['sample']={'id':'sample','state':'running','batch':True,'progress':62,'task_index':2,'total_tasks':3}
    b._store_preview('sample',NS(image=Image.new('RGB',(100,100)),progress=10,current_step=1,total_steps=10,task_index=2))
    assert c.get(API+'/generator/jobs/sample').json()['progress']==62
    assert c.get(API+'/generator/jobs/sample/preview?task=2').status_code==200
    b._change('sample',progress=float('inf'),current_step=float('nan'),total_steps='bad')
    state=c.get(API+'/generator/jobs/sample').json()
    assert state['progress']==62 and state['current_step'] is None and state['total_steps'] is None


def test_delayed_native_callbacks_cannot_change_terminal_job(installation):
    c,p,*_=installation;b=p.queue_bridge
    b._jobs['finished']={'id':'finished','state':'running','batch':True,'task_index':1,'total_tasks':3}
    b._change('finished',state='completed',progress=100,message='Finished')
    before=b.status('finished')
    b._change('finished',progress=1,message='Late status',error='Late error')
    b._observe_batch_status('finished','Prompt 3/3 - Encoding')
    assert b.status('finished')==before


def test_parallel_bad_telemetry_and_status_polling(installation):
    from concurrent.futures import ThreadPoolExecutor
    c,p,*_=installation;b=p.queue_bridge
    b._jobs['sample']={'id':'sample','state':'running','progress':47}
    def attack(i):
        if i%2:
            bad=[float('nan'),float('inf'),'not numeric'][i%3]
            b._store_preview('sample',NS(image=Image.new('RGB',(30,30)),progress=bad,current_step=bad,total_steps=bad))
        r=c.get(API+'/generator/jobs/sample')
        return r.status_code,r.json()['progress']
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(attack,range(120)))==[(200,47)]*120


def test_concurrent_conversion_apply_is_one_shot(installation,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from test_dev58_conversion import _setup
    c,p,*_=_setup(installation,monkeypatch)
    plan=c.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json()
    p.queue_bridge.process_pending_in_gradio(p.queue_bridge.api_session)
    def apply(_):return c.post(API+'/choices/conversion/apply',json={'job_id':plan['id']}).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(apply,range(16)))
    assert results.count(200)==1 and results.count(409)==15,results
    assert c.get(API+'/choices').json()[0]['refmod']=='flux2/celebs/Ada_Test_H3.safetensors'
