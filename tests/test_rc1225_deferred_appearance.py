"""Deferred native vision handoff, contention, cancellation and independent queue UI."""
import importlib
import threading
import time
from contextlib import contextmanager
from test_rc1213_appearance import app, stage, run, approve
from test_native_plugin import installation
from test_dev55_browser import page


def wait_for(predicate):
    deadline=time.monotonic()+5
    while not predicate():
        assert time.monotonic()<deadline, 'Timed out waiting for vision job'
        time.sleep(.01)


def launch(a, job):
    worker=threading.Thread(target=run,args=(a,job),daemon=True)
    worker.start()
    return worker


def install_contention(a):
    c,p,s,b,n,r=a
    mod=importlib.import_module('cb_under_test.vision_bridge')
    busy=threading.Event();busy.set();session=n.session;attempts=[]
    @contextmanager
    def wrapped(state,engine,stop):
        attempts.append(engine)
        if busy.is_set():raise mod.VisionBusy('WanGP has queued work')
        with session(state,engine,stop) as analyze:yield analyze
    n.session=wrapped
    return busy,attempts


def test_waiting_batch_visible_and_executes_once_after_idle(app):
    c,p,s,b,n,r=app;busy,attempts=install_contention(app)
    job=stage(app).json()['id'];worker=launch(app,job)
    try:
        wait_for(lambda:b.status(job)['state']=='waiting')
        status=c.get(p+'/maintenance/activity').json()['appearance']
        assert status['state']=='waiting' and status['total']==2 and status['done']==0
        assert n.loads==0 and stage(app).status_code==409
        assert b.run(job,{},s.resolve_appearance_images)=='No pending appearance analysis'
        busy.clear();worker.join(5);assert not worker.is_alive()
        assert b.status(job)['state']=='completed' and n.loads==n.releases==1 and len(n.calls)==2
        assert b.summary()['review']==2 and b.summary()['done']==2
        assert approve(app,job).status_code==200 and b.summary()['review']==1
    finally:
        busy.clear();b.cancel(job);worker.join(5)


def test_cancel_waiting_and_reject_stale_callback(app):
    c,p,s,b,n,r=app;busy,attempts=install_contention(app)
    job=stage(app).json()['id'];worker=launch(app,job)
    try:
        wait_for(lambda:b.status(job)['state']=='waiting')
        assert c.post(p+'/appearance/batch/'+job+'/cancel').status_code==200
        worker.join(5);assert not worker.is_alive()
        assert b.status(job)['state']=='cancelled' and n.loads==0
        busy.clear();new=stage(app).json()['id']
        assert b.run(job,{},s.resolve_appearance_images)=='No pending appearance analysis'
        assert c.post(p+'/appearance/batch/'+job+'/cancel').status_code==404
        assert run(app,new)['state']=='completed' and n.loads==1
    finally:
        busy.clear();b.cancel(job);worker.join(5)


def test_changed_engine_while_waiting_fails_without_loading(app):
    c,p,s,b,n,r=app;busy,attempts=install_contention(app)
    job=stage(app).json()['id'];worker=launch(app,job)
    try:
        wait_for(lambda:b.status(job)['state']=='waiting')
        n.options=lambda:[{'id':'3','backend':'changed'}]
        busy.clear();worker.join(5);assert not worker.is_alive()
        assert b.status(job)['state']=='failed' and 'format changed' in b.status(job)['message'] and n.loads==0
    finally:
        busy.clear();b.cancel(job);worker.join(5)


def test_permanent_failure_not_retried(app):
    c,p,s,b,n,r=app;mod=importlib.import_module('cb_under_test.vision_bridge');attempts=[]
    @contextmanager
    def failed(*args):
        attempts.append(1);raise mod.VisionUnavailable('Missing model assets');yield
    n.session=failed;job=stage(app).json()['id']
    assert run(app,job)['state']=='failed' and attempts==[1]


def test_browser_queue_and_review_recovery(page):
    tab,errors=page
    tab.evaluate('''()=>{window.visionSummary={id:'job-one',state:'waiting',message:'Waiting for GPU · WanGP has queued work',total:2,done:0,review:0};window.cancelCalls=[];const old=fetch;window.fetch=async(u,o={})=>{const url=String(u),json=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});if(url==='api/maintenance/activity')return json({running:false,jobs:[],appearance:visionSummary});if(url==='api/appearance/batch/job-one/cancel'){cancelCalls.push(url);visionSummary={...visionSummary,cancelling:true};return json({cancelled:true});}if(url==='api/appearance/batch/job-one')return json({...visionSummary,results:visionSummary.state==='completed'?[{index:0,state:'review',character:'Example',label:'Example portrayal',traits:'Green skin'}]:[]});return old(u,o);};pollMaintenanceActivity();}''')
    tab.wait_for_function("!$('appearanceActivity').hidden")
    assert 'Waiting for GPU' in tab.locator('#appearanceActivity').inner_text()
    tab.locator('#nativeQueuePanel summary').click()
    assert tab.locator('#appearanceQueueRow').is_visible()
    tab.once('dialog',lambda d:d.accept());tab.locator('#appearanceQueueCancel').click()
    tab.wait_for_function('cancelCalls.length===1 && $("appearanceQueueCancel").disabled')
    tab.locator('#appearanceActivity').click()
    tab.wait_for_function("appearanceCurrentState==='waiting'")
    assert tab.locator('#appearanceStart').is_disabled() and tab.locator('#appearanceCancel').is_visible()
    tab.keyboard.press('Escape')
    tab.evaluate("visionSummary={...visionSummary,state:'completed',message:'Review drafts before saving',done:2,review:1,cancelling:false};pollAppearance();pollMaintenanceActivity()")
    tab.wait_for_function("$('appearanceActivity').textContent.includes('Review ready')")
    tab.locator('#appearanceActivity').click()
    assert tab.locator('#appearanceResults textarea').input_value()=='Green skin'
    assert not errors,errors


def test_cancel_running_retains_prior_draft_and_releases_once(app):
    c,p,s,b,n,r=app;started=threading.Event()
    original=n.session
    @contextmanager
    def slow(state,engine,stop):
        with original(state,engine,stop) as analyze:
            def wrapped(label,images):
                if n.calls:
                    started.set()
                    deadline=time.monotonic()+5
                    while not stop():
                        assert time.monotonic()<deadline
                        time.sleep(.01)
                    raise InterruptedError('Cancelled')
                return analyze(label,images)
            yield wrapped
    n.session=slow;job=stage(app).json()['id'];worker=launch(app,job)
    try:
        assert started.wait(5)
        assert b.summary()['done']==1 and b.summary()['state']=='running'
        assert c.post(p+'/appearance/batch/'+job+'/cancel').status_code==200
        worker.join(5);assert not worker.is_alive()
        assert b.status(job)['state']=='cancelled' and n.loads==n.releases==1
        assert b.summary()['review']==1 and approve(app,job).status_code==200
    finally:
        b.cancel(job);worker.join(5)


def test_reference_mutation_while_waiting_never_reuses_changed_pixels(app):
    from PIL import Image
    c,p,s,b,n,r=app;busy,attempts=install_contention(app)
    job=stage(app).json()['id'];worker=launch(app,job)
    try:
        wait_for(lambda:b.status(job)['state']=='waiting')
        Image.new('RGB',(120,160),'red').save(s.REFERENCE_DIR/f'{1:024x}.jpg')
        busy.clear();worker.join(5);assert not worker.is_alive()
        results=b.status(job)['results'];assert [x['state'] for x in results]==['failed','review']
        assert len(n.calls)==1 and 'changed' in results[0]['error']
        assert approve(app,job).status_code==409 and approve(app,job,1).status_code==200
    finally:
        busy.clear();b.cancel(job);worker.join(5)


def test_cleanup_failure_never_replays_analysis(app):
    c,p,s,b,n,r=app;mod=importlib.import_module('cb_under_test.vision_bridge');original=n.session
    @contextmanager
    def broken(state,engine,stop):
        with original(state,engine,stop) as analyze:yield analyze
        raise mod.VisionBusy('synthetic cleanup error')
    n.session=broken;job=stage(app).json()['id']
    assert run(app,job)['state']=='failed'
    assert n.loads==n.releases==1 and len(n.calls)==2 and b.summary()['review']==2
