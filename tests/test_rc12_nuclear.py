"""Isolated fault injection: native operations are simulated; no GPU or live library."""
import io
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
import httpx
from PIL import Image
from test_native_plugin import installation
from test_rc2_jackhammer import API, server
from test_dev58_conversion import _setup


def single(b):
    b._jobs['single']={'id':'single','state':'queued','files':[]}
    return NS(portrait_completion=None)


def test_single_cancel_during_native_submit(installation,monkeypatch):
    c,p,*_=installation;b=p.queue_bridge;task=single(b);calls=[]
    monkeypatch.setattr(b,'prepare',lambda *a:{'settings':{},'refmod':'test'})
    def submit(*a,**kw):
        assert c.post(API+'/generator/jobs/single/cancel').status_code==200
        return NS(cancel=lambda:calls.append('cancel'),result=lambda:NS(success=True,generated_files=['example.png']))
    b.api_session=NS(submit_task=submit)
    b._run('single',task,lambda _:None)
    assert calls==['cancel'] and b.status('single')['state']=='cancelled'


def test_cancel_during_prepare(installation,monkeypatch):
    c,p,*_=installation;b=p.queue_bridge;task=single(b)
    def prepare(*a):
        assert c.post(API+'/generator/jobs/single/cancel').status_code==200
        return {'settings':{},'refmod':'test'}
    monkeypatch.setattr(b,'prepare',prepare)
    b.api_session=NS(submit_task=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('unexpected native submission')))
    b._run('single',task,lambda _:None)
    assert b.status('single')['state']=='cancelled'


def test_cancel_conversion_after_decode(installation,monkeypatch):
    c,p,root,_=_setup(installation,monkeypatch);b=p.queue_bridge
    original=b.api_session.submit_task;calls=[]
    plan=c.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json();jid=plan['id']
    def submit(settings,callbacks):
        calls.append(settings['model_type']);h=original(settings,callbacks)
        def result():
            assert c.post(API+'/generator/jobs/'+jid+'/cancel').status_code==200
            return NS(success=False,errors=[],generated_files=[])
        return NS(result=result,cancel=lambda:None)
    b.api_session.submit_task=submit
    b.process_pending_in_gradio(b.api_session)
    assert calls==['h3-pruned'] and b.status(jid)['state']=='cancelled'
    assert not list((root/'refmods/flux2').rglob('*.safetensors'))


def test_terminal_history_bounded_by_completion_order(installation):
    _,p,*_=installation;b=p.queue_bridge
    b._jobs['slow']={'id':'slow','state':'running'}
    for i in range(160):
        key=str(i);b._jobs[key]={'id':key,'state':'running','batch':True}
        b._change(key,state='completed')
    assert len(b._jobs)==101 and b.status('slow')['state']=='running'
    b._change('slow',state='completed')
    assert len(b._jobs)==100 and b.status('slow')['state']=='completed'
    assert b.status('0') is None


def photo_transport(s,monkeypatch,handler=None):
    buf=io.BytesIO();Image.new('RGB',(180,220),'blue').save(buf,format='PNG');raw=buf.getvalue()
    cls=httpx.Client
    monkeypatch.setattr(s,'validate_public_url',lambda _:None)
    monkeypatch.setattr(s.httpx,'Client',lambda **kw:cls(transport=httpx.MockTransport(handler or (lambda _:httpx.Response(200,headers={'Content-Type':'image/png'},content=raw))),**kw))


def test_photo_cache_database_failure_no_orphan(installation,monkeypatch):
    s=server();photo_transport(s,monkeypatch)
    with s.connect() as db:db.execute("CREATE TRIGGER reject_cache BEFORE INSERT ON photo_files BEGIN SELECT RAISE(ABORT,'injected'); END")
    assert s.download_image('https://example.com/photo.png')==''
    assert not list(s.PHOTO_DIR.iterdir())


def test_photo_cache_concurrent_same_url(installation,monkeypatch):
    s=server();photo_transport(s,monkeypatch)
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(s.download_image,['https://example.com/photo.png']*32))
    assert len(set(results))==1 and results[0].startswith('api/photos/')
    assert len(list(s.PHOTO_DIR.iterdir()))==1
    with s.connect() as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)


def test_photo_cache_disk_failure_no_temp(installation,monkeypatch):
    import errno
    s=server();photo_transport(s,monkeypatch)
    original=Image.Image.save
    def fail(self,fp,*a,**kw):
        if hasattr(fp,'write'):fp.write(b'partial')
        else:
            with open(fp,'wb') as f:f.write(b'partial')
        raise OSError(errno.ENOSPC,'injected disk full')
    monkeypatch.setattr(Image.Image,'save',fail)
    assert s.download_image('https://example.com/photo.png')==''
    assert not list(s.PHOTO_DIR.iterdir())


def test_photo_cache_interrupted_stream(installation,monkeypatch):
    s=server()
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield b'partial';raise httpx.ReadError('injected interruption')
    photo_transport(s,monkeypatch,lambda _:httpx.Response(200,headers={'Content-Type':'image/png'},stream=Broken()))
    assert s.download_image('https://example.com/photo.png')==''
    assert not list(s.PHOTO_DIR.iterdir())


def test_batch_cancel_during_prepare(installation,monkeypatch):
    c,p,*_=installation;b=p.queue_bridge;calls=[]
    b._jobs['batch']={'id':'batch','state':'queued','batch':True}
    def prepare(task,validate):
        calls.append(task)
        assert c.post(API+'/generator/jobs/batch/cancel').status_code==200
        return {'settings':{}}
    monkeypatch.setattr(b,'prepare',prepare)
    b._run_batch('batch',list(range(10)),lambda _:None)
    assert calls==[0] and b.status('batch')['state']=='cancelled'


def test_conversion_session_disappears(installation,monkeypatch):
    c,p,*_=_setup(installation,monkeypatch);b=p.queue_bridge
    plan=c.post(API+'/choices/conversion/prepare',json={'target_model':'flux3_klein'}).json()
    b.process_pending_in_gradio(None)
    assert b.status(plan['id'])['state']=='failed'
    assert 'initialization' in b.status(plan['id'])['message']


def test_photo_cache_preserves_untracked_collision(installation,monkeypatch):
    import hashlib
    s=server();photo_transport(s,monkeypatch);url='https://example.com/photo.png'
    old=s.PHOTO_DIR/(hashlib.sha256(url.encode()).hexdigest()+'.jpg');old.write_bytes(b'sentinel')
    assert s.download_image(url).startswith('api/photos/')
    assert old.read_bytes()==b'sentinel'
    with s.connect() as db:
        filename=db.execute('SELECT filename FROM photo_files WHERE url=?',(url,)).fetchone()[0]
    assert filename!=old.name
    with Image.open(s.PHOTO_DIR/filename) as im:im.verify()


def test_cancel_workshop_during_submit(installation,monkeypatch):
    from cb_under_test import queue_bridge as qb
    c,p,root,_=installation;b=p.queue_bridge;calls=[]
    task=NS(op='extract_flux',expected=root/'unused.safetensors')
    b._jobs['workshop']={'id':'workshop','state':'queued'}
    monkeypatch.setattr(qb,'extract_job_settings',lambda *a:{})
    def submit(*a,**kw):
        assert c.post(API+'/generator/jobs/workshop/cancel').status_code==200
        return NS(cancel=lambda:calls.append('cancel'),result=lambda:NS(cancelled=True,errors=[]))
    b.api_session=NS(submit_task=submit)
    b._run_workshop('workshop',task,lambda _:None)
    assert calls==['cancel'] and b.status('workshop')['state']=='cancelled'
