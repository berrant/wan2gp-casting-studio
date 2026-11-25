"""Reconstructed MOAB probes; no live GPU or user data."""
from types import SimpleNamespace as NS
import io,pytest,httpx
from PIL import Image
from test_native_plugin import installation
from test_rc2_jackhammer import API,server
from test_beta523_portraits import setup,upload
from test_rc11_faults import batch

@pytest.mark.parametrize('metadata',[{'task_index':2,'status':'Prompt 1/3'}, {'task_index':1,'status':'Prompt 1/99'}, {'task_index':1,'task_count':99}, {'task_index':'bogus','status':'Prompt 1/3'}])
def test_preview_conflict(installation,metadata):
    _,p,*_=installation;b=p.queue_bridge
    b._jobs['p']={'id':'p','state':'running','batch':True,'task_index':1,'total_tasks':3}
    b._store_preview('p',NS(image=Image.new('RGB',(20,20)),**metadata))
    assert b.preview('p') is None

def test_preview_valid(installation):
    _,p,*_=installation;b=p.queue_bridge
    b._jobs['p']={'id':'p','state':'running','batch':True,'task_index':1,'total_tasks':3}
    b._store_preview('p',NS(image=Image.new('RGB',(20,20)),task_index=1,task_count=3,status='Prompt 1/3'))
    assert b.preview('p')[1]=='image/jpeg'

@pytest.mark.parametrize('field,value',[('checked','corrupt'),('url',b'bad bytes'),('url','javascript:bad')])
def test_damaged_artwork(installation,monkeypatch,field,value):
    c,*_=installation;s=server()
    with s.connect() as db:
        db.execute('INSERT INTO production_artwork VALUES (?,?,?)',('sample','https://example.com/poster.png',int(s.time.time())))
        db.execute('UPDATE production_artwork SET '+field+'=?',(value,))
    monkeypatch.setattr(s.httpx,'Client',lambda **kw: (_ for _ in ()).throw(httpx.ConnectError('offline fixture')))
    r=c.get(API+'/productions/artwork',params={'name':'Sample'})
    assert r.status_code==200 and r.json()['image']==''

@pytest.mark.parametrize('endpoint',['/enrichment/start','/enrichment/retry-errors','/prefetch/start','/photos/archive-existing'])
def test_worker_start_failure(installation,monkeypatch,endpoint):
    c,*_=installation;s=server()
    class Broken:
        def __init__(self,*a,**kw):pass
        def start(self):raise RuntimeError('injected thread limit')
        def is_alive(self):return False
    monkeypatch.setattr(s,'threading',NS(Thread=Broken))
    for _ in range(2):
        r=c.post(API+endpoint,json={'scope':'all'})
        assert r.status_code==503,r.text
    assert not s.ENRICH_STATE['running'] and not s.prefetch_state['running']

def test_portrait_upload_sqlite_failure(installation):
    c,p,session,base,body,data,out=setup(installation);s=server();old=upload(c,base)
    before=set(s.PERSONAL_PORTRAITS.iterdir())
    with s.connect() as db:db.execute("CREATE TRIGGER reject_portrait BEFORE UPDATE OF portrait ON personal_profiles BEGIN SELECT RAISE(ABORT,'injected'); END")
    buf=io.BytesIO();Image.new('RGB',(160,160),'green').save(buf,format='PNG')
    r=c.post(base+'/portrait',content=buf.getvalue(),headers={'Content-Type':'image/png'})
    assert r.status_code==503 and set(s.PERSONAL_PORTRAITS.iterdir())==before
    assert c.get(API+'/personal').json()[0]['portrait_url']==old

def test_batch_oversized_status(installation,monkeypatch):
    def submit(chunk,callbacks):
        callbacks.on_status('Prompt '+'9'*5000+'/250')
        return NS(result=lambda:NS(success=True,generated_files=[],errors=[],cancelled=False))
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert b.status('batch')['state']=='completed',b.status('batch')

def test_credit_start_failure(installation,monkeypatch):
    c,*_=installation;s=server()
    class Broken:
        def __init__(self,*a,**kw):pass
        def start(self):raise RuntimeError('injected')
    monkeypatch.setattr(s,'threading',NS(Thread=Broken))
    for _ in range(2):
        with pytest.raises(s.HTTPException) as e:s.launch_credit_sync(['Example Person'])
        assert e.value.status_code==503 and not s.CREDIT_STATE['running'] and not s.CREDIT_PENDING

@pytest.mark.parametrize('metadata',[{'task_index':1,'task_count':99},{'task_index':'bad','task_count':250},{'task_index':1,'task_count':250,'status':'Prompt 1/99'}])
def test_chunk_preview_invalid_native_metadata(installation,monkeypatch,metadata):
    def submit(chunk,callbacks):
        if len(chunk)==250:
            callbacks.on_preview(NS(image=Image.new('RGB',(20,20)),**metadata))
            assert b.preview('batch') is None
        return NS(result=lambda:NS(success=True,generated_files=[],errors=[],cancelled=False))
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert b.status('batch')['state']=='completed'
