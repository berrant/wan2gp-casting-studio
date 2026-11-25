"""Completed output vs live preview, exact task abort, and browser preferences."""
from pathlib import Path
from types import SimpleNamespace as NS
import shutil
import pytest
from test_native_plugin import installation, _mock_fork, _create_public_selection
from test_dev512_image_sets import _image_session, _set_image_template
from PIL import Image

API='/casting-studio/api'
HTML=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()

def test_completed_output_uses_native_path_not_inference_or_user_path(installation):
    c,p,root,_=installation;b=p.queue_bridge
    jid='job-one';b._jobs[jid]={'id':jid,'state':'running','batch':True,'task_index':1,'total_tasks':3}
    png=root/'completed.png';Image.new('RGB',(120,100),'red').save(png)
    png2=root/'next.png';Image.new('RGB',(120,100),'green').save(png2)
    b._remember_native_task(jid,NS(task_index=1,task_id='client1',phase='inference'))
    b._store_preview(jid,NS(image=Image.new('RGB',(30,30),'blue'),task_index=1,current_step=6,total_steps=8,phase='inference'))
    assert b.status(jid)['preview_step']==6 and b.status(jid)['preview_total_steps']==8 and 'last_result' not in b.status(jid)
    b._observe_native_output(jid,{'client_id':'unrelated','path':str(png)})
    assert 'last_result' not in b.status(jid)
    b._observe_native_output(jid,{'client_id':'client1','path':str(png)})
    token=b.status(jid)['last_result']['id'];url=API+'/generator/monitor-output/'+token
    assert c.get(url).content==png.read_bytes()
    assert c.get(API+'/generator/monitor-output/not-an-output').status_code==404
    b._advance_batch_task(jid,2,3)
    assert b.status(jid)['preview_total_steps'] is None
    assert b.preview(jid,1) is None and b.status(jid)['last_result']['id']==token
    b._remember_native_task(jid,NS(task_index=2,task_id='client2',phase='inference'))
    b._observe_native_output(jid,{'client_id':'client2','path':str(png2)})
    newer=b.status(jid)['last_result'];assert newer['task_index']==2 and newer['id']!=token
    b._observe_native_output(jid,{'client_id':'client1','path':str(png)})
    assert b.status(jid)['last_result']==newer
    b.set_preview_interest(jid,False)
    assert b.status(jid)['last_result']==newer
    b._jobs['job-two']={'id':'job-two','state':'queued'}
    assert b.status('job-two')['last_result']==newer
    png.write_bytes(b'changed');assert c.get(url).status_code==404

def test_abort_exact_batch_task_and_stale_rejection(installation):
    c,p,_,_=installation;b=p.queue_bridge;jid='batch';calls=[]
    handle=NS(cancel=lambda:calls.append('WHOLE BATCH'))
    b._jobs[jid]={'id':jid,'state':'running','batch':True,'task_index':2,'total_tasks':3}
    b._handles[jid]=handle
    b._remember_native_task(jid,NS(task_index=2,task_id='client2',phase='inference'))
    queue=[{'client_id':'client2','queue_id':'native2','status':'running'}, {'client_id':'client3','queue_id':'native3','status':'queued'}]
    b._jobs[jid]['_monitor_queue_ops']=(lambda:{'tasks':queue},lambda key:calls.append(key))
    url=API+'/generator/jobs/'+jid+'/abort-current?task='
    assert c.post(url+'1').status_code==409
    assert c.post(url+'2').status_code==200
    assert calls==['native2'] and b.status(jid)['abort_requested']
    assert c.post(url+'2').status_code==409
    b._advance_batch_task(jid,3,3)
    assert c.post(url+'2').status_code==409
    assert not b.status(jid)['abort_requested']
    # Fail closed if the active native queue task cannot be matched.
    b._remember_native_task(jid,NS(task_index=3,task_id='client3',phase='inference'))
    assert c.post(url+'3').status_code==409 and calls==['native2']
    queue[1]['status']='running';b._jobs[jid]['_monitor_queue_ops']=(None,None)
    assert c.post(url+'3').status_code==409 and calls==['native2']

def test_abort_single_native_handle(installation):
    c,p,_,_=installation;b=p.queue_bridge;calls=[]
    b._jobs['single']={'id':'single','state':'running'};b._handles['single']=NS(cancel=lambda:calls.append('cancel'))
    assert c.post(API+'/generator/jobs/single/abort-current?task=1').status_code==200
    assert calls==['cancel'];assert b.status('single')['abort_requested']
    b._change('single',state='cancelled')
    assert c.post(API+'/generator/jobs/single/abort-current?task=1').status_code==409

def test_batch_native_output_and_abort_continues_other_tasks(installation):
    c,p,root,_=installation;_mock_fork(root);session=_image_session();b=p.queue_bridge
    b.api_session=session;b.dispatch_mode='gradio';key=_create_public_selection(c);_set_image_template(c,count=3)
    paths=[]
    for i in range(3):
        path=root/f'result{i}.png';Image.new('RGB',(120,120),(i,10,100)).save(path);paths.append(str(path))
    cancelled=[];queue=[{'client_id':f'c{i}','queue_id':f'q{i}','status':'queued'} for i in range(1,4)]
    session.list_queue=lambda:{'tasks':queue};session.cancel_queue_task=lambda q:cancelled.append(q)
    def submit(settings,callbacks=None):
        def result():
            for i in range(1,4):
                queue[i-1]['status']='running';callbacks.on_progress(NS(task_index=i,task_count=3,task_id=f'c{i}',phase='inference',current_step=6,total_steps=8,progress=50,status=f'Prompt {i}/3 - Denoising'))
                if i==2:
                    assert c.post(API+f'/generator/jobs/{jid}/abort-current?task=2').status_code==200
                else:
                    callbacks.on_output({'client_id':f'c{i}','path':paths[i-1]})
                    assert b.status(jid)['last_result']['task_index']==i
                queue[i-1]['status']='done'
            return NS(success=False,generated_files=[paths[0],paths[2]],errors=[NS(cancelled=True,task_index=2,message='Generation was cancelled')],cancelled=False)
        return NS(result=result,cancel=lambda:cancelled.append('all'),webui_client_ids=['c1','c2','c3'])
    session.submit_manifest=submit
    response=c.post(API+'/generator/batch/submit',json={'task':{'choice_key':key,'model':'h3_image_pruned','model_type':'h3_image_pruned_checkpoint'},'scope':'selection:'+key,'scene_mode':'all'})
    assert response.status_code==200,response.text;jid=response.json()['id'];b.process_pending_in_gradio(session)
    state=b.status(jid);assert state['state']=='completed' and '1 aborted' in state['message'] and state['last_result']['task_index']==3
    assert cancelled==['q2'];assert len(state['files'])==2

@pytest.mark.skipif(not shutil.which('chromium'),reason='Chromium unavailable')
def test_browser_handoff_modes_percent_and_abort_click():
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1400,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.evaluate(setup_js)
        page.evaluate("""() => {const prefs={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>prefs[k]??null,setItem:(k,v)=>prefs[k]=String(v),removeItem:k=>delete prefs[k]}})}""")
        page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        out=page.evaluate('''async () => {
          const old={id:'opaque',job_id:'batch',task_index:1,kind:'image'};
          const img=$('monitorLiveImage');const label=$('monitorPreviewStatus');const defaults={...monitorPrefs};
          $('monitorToggle').open=true;showMonitorPrefs();$('monitorHandoffPercent').value='75';saveMonitorPrefs();
          const base={id:'batch',batch:true,state:'running',task_index:2,total_tasks:3,preview_task_index:2,last_result:old,native_task_active:true,abort_available:true,total_steps:8};
          const render=(rev,step)=>renderGenerationMonitor({...base,preview_rev:rev,preview_kind:'image',preview_step:step});
          render(0,null);const previous=img.dataset.version==='result:opaque'&&label.textContent.includes('Previous completed result');
          render(1,1);const holds=img.dataset.version==='result:opaque';render(2,6);const live=img.dataset.version==='batch:2:2'&&label.textContent.includes('step 6');
          const original=window.fetch;let calls=[];window.fetch=async (url,opts)=>{calls.push([url,opts.method]);return {ok:true}};
          await abortMonitorGeneration();const abort=$('monitorAbort').disabled&&calls.length===1&&calls[0][0].endsWith('/abort-current?task=2')&&calls[0][1]==='POST';
          window.fetch=original;
          $('monitorHandoffMode').value='static';saveMonitorPrefs();
          renderGenerationMonitor({...base,task_index:3,preview_rev:0,preview_task_index:null});const placeholder=!img.hasAttribute('src')&&$('monitorPreviewPlaceholder').style.display==='flex';
          renderGenerationMonitor({...base,task_index:3,preview_task_index:3,preview_rev:1,preview_kind:'image',preview_step:1});const staticLive=img.dataset.version==='batch:3:1';
          renderGenerationMonitor({...base,task_index:3,state:'completed',last_result:{...old,id:'new',task_index:3}});const final=img.dataset.version==='result:new'&&label.textContent.includes('Completed result');
          const saved=loadMonitorPrefs();
          $('monitorHandoffMode').value='retain';saveMonitorPrefs();
          const next={...base,last_result:{...old,id:'new',task_index:3},id:'other',task_index:1,preview_task_index:1,total_steps:40,preview_kind:'image'};
          renderGenerationMonitor({...next,preview_rev:1,preview_step:29});const longHolds=img.dataset.version==='result:new';
          renderGenerationMonitor({...next,preview_rev:2,preview_step:30});const longSwitch=img.dataset.version==='other:1:2';
          renderGenerationMonitor({...next,id:'unknown',total_steps:null,preview_rev:1,preview_step:30});const unknownHolds=img.dataset.version==='result:new';
          renderGenerationMonitor({...next,id:'unknown',preview_rev:2,preview_step:29,preview_total_steps:40,current_step:40});const staleHolds=img.dataset.version==='result:new';
          localStorage.removeItem(MONITOR_PREFS_KEY);localStorage.setItem('casting-studio:monitor:v1',JSON.stringify({mode:'static',step:6}));const migration=loadMonitorPrefs().mode==='static'&&loadMonitorPrefs().percent===0;
          const bounds=normalizeMonitorPercent(-12)===0&&normalizeMonitorPercent(200)===100&&normalizeMonitorPercent('garbage')===0;
          $('monitorToggle').open=false;renderGenerationMonitor({...base,state:'completed',last_result:{...old,id:'new',task_index:3}});const collapsed=!img.hasAttribute('src')&&!$('monitorLiveVideo').hasAttribute('src');
          return {defaults,previous,holds,live,abort,placeholder,staticLive,final,saved,collapsed,longHolds,longSwitch,unknownHolds,staleHolds,migration,bounds};
        }''')
        assert out.pop('defaults')=={'mode':'retain','percent':0};assert out.pop('saved')=={'mode':'static','percent':75};assert all(out.values()),out
        assert not errors,errors;browser.close()
