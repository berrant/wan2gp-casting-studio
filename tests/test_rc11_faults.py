"""Native cancellation and stale telemetry failure injection."""
from types import SimpleNamespace as NS
from test_native_plugin import installation
from test_rc2_jackhammer import API


def batch(installation,monkeypatch,submit):
    c,p,*_=installation;b=p.queue_bridge
    tasks=[NS(index=i) for i in range(251)]
    b._jobs['batch']={'id':'batch','state':'queued','batch':True,'total_tasks':len(tasks),'files':[]}
    monkeypatch.setattr(b,'prepare',lambda task,validate:{'settings':{'index':task.index}})
    b.api_session=NS(submit_manifest=submit)
    return b,tasks


def test_cancel_batch_even_when_native_finishes_successfully(installation,monkeypatch):
    c,p,*_=installation;calls=[];cancels=[]
    def submit(chunk,callbacks):
        calls.append(chunk)
        def result():
            if len(calls)==1:
                assert c.post(API+'/generator/jobs/batch/cancel').status_code==200
            return NS(success=True,generated_files=['output.png'],errors=[],cancelled=False)
        return NS(result=result,cancel=lambda:cancels.append(1))
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert len(calls)==1 and cancels==[1]
    assert b.status('batch')['state']=='cancelled' and b.status('batch')['files']==['output.png']


def test_native_cancelled_flag_is_authoritative(installation,monkeypatch):
    calls=[]
    def submit(chunk,callbacks):
        calls.append(chunk)
        return NS(result=lambda:NS(success=True,generated_files=['output.png'],errors=[],cancelled=True))
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert len(calls)==1 and b.status('batch')['state']=='cancelled'


def test_stale_task_telemetry_does_not_replace_current(installation,monkeypatch):
    def submit(chunk,callbacks):
        def result():
            def progress(i,step,pct):
                callbacks.on_progress(NS(task_index=i,task_count=len(chunk),status=f'Prompt {i}/{len(chunk)}',task_id=f'c{i}',phase='inference',current_step=step,total_steps=8,progress=pct))
            if len(chunk)>1:
                progress(2,6,40)
                before=b.status('batch')
                progress(1,1,2)
                callbacks.on_status('Prompt 1/250 - stale')
                after=b.status('batch')
                assert after['current_step']==before['current_step'] and after['progress']==before['progress'] and after['message']==before['message']
            return NS(success=True,generated_files=[],errors=[],cancelled=False)
        return NS(result=result)
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert b.status('batch')['state']=='completed',b.status('batch')


def test_cancel_failure_is_controlled_and_retryable(installation):
    c,p,*_=installation;b=p.queue_bridge;calls=[]
    def cancel():
        calls.append(1)
        if len(calls)==1:raise RuntimeError('native refusal')
    b._jobs['single']={'id':'single','state':'running'};b._handles['single']=NS(cancel=cancel)
    path=API+'/generator/jobs/single/cancel'
    assert c.post(path).status_code==409
    assert c.post(path).status_code==200
    assert c.post(path).status_code==409
    assert calls==[1,1]


def test_cancel_during_native_handle_creation(installation,monkeypatch):
    c,p,*_=installation;calls=[];cancels=[]
    def submit(chunk,callbacks):
        calls.append(chunk)
        assert c.post(API+'/generator/jobs/batch/cancel').status_code==200
        return NS(result=lambda:NS(success=True,generated_files=[],errors=[],cancelled=False),cancel=lambda:cancels.append(1))
    b,tasks=batch(installation,monkeypatch,submit)
    b._run_batch('batch',tasks,lambda _:None)
    assert b.status('batch')['state']=='cancelled' and len(calls)==1 and cancels==[1]


def test_cancel_between_chunks_does_not_cancel_finished_handle(installation,monkeypatch):
    c,p,*_=installation;calls=[];cancels=[]
    def submit(chunk,callbacks):
        calls.append(chunk)
        return NS(result=lambda:NS(success=True,generated_files=['output.png'],errors=[],cancelled=False),cancel=lambda:cancels.append(1))
    b,tasks=batch(installation,monkeypatch,submit)
    def validate(task):
        if task.index==250:
            assert c.post(API+'/generator/jobs/batch/cancel').status_code==200
    b._run_batch('batch',tasks,validate)
    assert b.status('batch')['state']=='cancelled' and len(calls)==1 and cancels==[]
    assert b.status('batch')['files']==['output.png']
