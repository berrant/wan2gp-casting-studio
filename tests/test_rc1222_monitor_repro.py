from types import SimpleNamespace as NS
from PIL import Image
from test_native_plugin import installation
from test_generator_session_browser import setup_js, HTML
from playwright.sync_api import sync_playwright
import shutil
import pytest

API='/casting-studio/api/generator/jobs/'


def test_follow_active_generation_not_latest_submission(installation,monkeypatch):
    c,p,_,_=installation;b=p.queue_bridge
    import importlib
    clock=[100.0];monkeypatch.setattr(importlib.import_module(b.__class__.__module__),'time',NS(monotonic=lambda:clock[0]))
    for jid,state in [('image','running'),('video','queued'),('conversion','running')]:
        b._jobs[jid]={'id':jid,'state':state,'task_index':1,'_monitor_cast':jid!='conversion'}
    b._remember_native_task('image',NS(task_id='i',phase='inference'))
    clock[0]+=1;b._remember_native_task('conversion',NS(task_id='c',phase='inference'))
    r=c.get(API+'video?follow=true&live_preview=true').json()
    assert r['id']=='image' and r['monitor_followed'] and '_monitor_cast' not in r
    assert b._jobs['image']['_preview_until']>clock[0] and '_preview_until' not in b._jobs['video']
    assert c.get(API+'video').json()['id']=='video'
    b._change('video',state='running')
    b._remember_native_task('video',NS(task_id='v',phase='queued'))
    assert c.get(API+'video?follow=true').json()['id']=='image'
    clock[0]+=1;b._remember_native_task('video',NS(task_id='v',phase='inference'))
    assert c.get(API+'image?follow=true').json()['id']=='video'
    b._change('image',state='cancelled')
    assert c.get(API+'image?follow=true').json()['id']=='video'
    b._change('video',state='completed')
    assert c.get(API+'video?follow=true').json()['state']=='completed'
    assert c.get(API+'missing?follow=true').status_code==404


@pytest.mark.parametrize('first,second',[('image','image'),('image','video'),('video','image'),('video','video')])
def test_preview_revision_and_abort_handoff(installation,first,second):
    c,p,_,_=installation;b=p.queue_bridge;jid='repro';b._jobs[jid]={'id':jid,'state':'running','batch':True,'total_tasks':2,'task_index':1,'_monitor_cast':True}
    def event(kind,task):
        return NS(task_index=task,**({'image':Image.new('RGB',(20,20))} if kind=='image' else {'video':b'fake mp4 payload'}))
    b._store_preview(jid,event(first,1));assert b.status(jid)['preview_kind']==first
    assert c.get(API+jid+'/preview?task=1&rev=1').status_code==200
    b._store_preview(jid,event(second,1));assert b.status(jid)['preview_kind']==second
    assert c.get(API+jid+'/preview?task=1&rev=1').status_code==404
    r=c.get(API+jid+'/preview?task=1&rev=2');assert r.status_code==200 and r.headers['content-type']==('image/jpeg' if second=='image' else 'video/mp4')
    b._jobs[jid]['abort_requested']=True
    b._store_preview(jid,event(first,1));assert b.status(jid)['preview_rev']==2 and b.preview(jid) is None
    assert c.get(API+jid+'/preview?task=1&rev=2').status_code==404
    b._advance_batch_task(jid,2,2)
    b._store_preview(jid,event(first,1));assert b.preview(jid) is None
    b._store_preview(jid,event(second,2));assert b.status(jid)['preview_rev']==1 and not b.status(jid)['abort_requested']
    assert c.get(API+jid+'/preview?task=1&rev=1').status_code==404
    assert c.get(API+jid+'/preview?task=2&rev=1').status_code==200
    b._change(jid,state='cancelled');b._store_preview(jid,event(second,2))
    assert b.preview(jid) is None and c.get(API+jid+'/preview').status_code==404


def test_browser_keeps_active_preview_then_switches_after_abort():
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page();page.evaluate(setup_js);page.set_content(HTML,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        result=page.evaluate('''async () => {
          $('monitorToggle').open=true;monitorPrefs={mode:'static',percent:0};
          const img=$('monitorLiveImage'),vid=$('monitorLiveVideo');vid.play=()=>Promise.resolve();vid.pause=()=>{};vid.load=()=>{};
          trackGeneratorJob('image-job');
          renderGenerationMonitor({id:'image-job',state:'running',preview_kind:'image',preview_rev:1,task_index:1,preview_task_index:1});
          trackGeneratorJob('video-job');
          const retained=generatorJob==='image-job'&&latestMonitorStatus.id==='image-job'&&img.dataset.version==='image-job:1:1';
          const original=fetch;let calls=[];window.fetch=async url=>{calls.push(String(url));return {ok:true,json:async()=>({id:'video-job',monitor_followed:true,state:'running',preview_kind:'video',preview_rev:1,task_index:1,preview_task_index:1})}};
          await pollGenerator();clearTimeout(generatorPoll);
          const moved=generatorJob==='video-job'&&vid.dataset.version==='video-job:1:1'&&!img.hasAttribute('src')&&img.dataset.version==='';
          renderGenerationMonitor({id:'video-job',state:'running',preview_kind:'image',preview_rev:2,task_index:1,preview_task_index:1});
          const reset=img.dataset.version==='video-job:1:2'&&!vid.hasAttribute('src')&&vid.dataset.version===''&&!vid.autoplay;
          window.fetch=original;
          return {retained,moved,reset,follow:calls[0].includes('follow=true')};
        }''')
        b.close();assert all(result.values()),result
