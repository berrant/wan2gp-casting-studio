"""Pinned acknowledgements and clear native Workshop labels."""
import json
from test_dev55_browser import page
from test_native_plugin import installation, FakeWanSession


def visible_in_panel(tab, selector, panel):
    return tab.evaluate('''([selector,panel])=>{const a=document.querySelector(selector).getBoundingClientRect(), b=document.querySelector(panel).getBoundingClientRect();return a.height>0&&a.top>=b.top-1&&a.bottom<=b.bottom+1&&a.bottom<=innerHeight}''',[selector,panel])


def test_queue_confirmation_pinned_and_survives_next_selection(page):
    tab,errors=page
    tab.evaluate('''()=>{const m=$('generatorModal');m.classList.add('open');const p=m.querySelector('.panel');p.querySelector('.generator-action-bar').insertAdjacentHTML('beforebegin','<div style="height:2400px"></div>');$('generatorStatus').textContent='Preparing';setGeneratorReceipt('first-job','Last submission first-job · queued');}''')
    assert tab.locator('#generatorModal .modal-pinned-close').count()==1
    assert tab.locator('#generatorModal').get_by_role('button',name='Close',exact=True).count()==0
    for width in (1400,520):
        tab.set_viewport_size({'width':width,'height':850})
        for scroll in (0,750,100000):
            tab.evaluate('(n)=>{$("generatorModal").querySelector(".panel").scrollTop=n}',scroll)
            assert visible_in_panel(tab,'#generatorReceipt','#generatorModal .panel'),(width,scroll)
            assert visible_in_panel(tab,'#generatorSubmitNext','#generatorModal .panel'),(width,scroll)
        tab.evaluate("$('generatorStatus').textContent='Loaded next selection model defaults'")
        assert 'first-job · queued' in tab.locator('#generatorReceipt').inner_text()
    assert not errors,errors


def test_collection_feedback_pinned_reset_on_new_target(page):
    tab,errors=page
    tab.evaluate('''()=>{window.restartPhotoSearch=()=>{};window.showReferenceCollection=async()=>{};openPhoto('Synthetic One',null,'actress',true);$('photos').innerHTML='<div style="height:2600px"></div>';$('manualPhotoStatus').textContent='3 images added';$('bulkPhotoStatus').textContent='2 saved';}''')
    assert tab.locator('#modal .modal-pinned-close').count()==1
    assert tab.locator('#modal').get_by_role('button',name='Close',exact=True).count()==0
    for width in (1400,520):
        tab.set_viewport_size({'width':width,'height':850})
        for scroll in (0,800,100000):
            tab.evaluate('(n)=>{$("modal").querySelector(".panel").scrollTop=n}',scroll)
            assert visible_in_panel(tab,'#manualPhotoStatus','#modal .panel'),(width,scroll)
            assert visible_in_panel(tab,'#bulkPhotoStatus','#modal .panel'),(width,scroll)
    tab.evaluate("openPhoto('Synthetic Two',null,'actress',true)")
    assert not tab.locator('#manualPhotoStatus').inner_text()
    assert not tab.locator('#bulkPhotoStatus').inner_text()
    assert not errors,errors


def test_workshop_does_not_inherit_generation_prompt(installation):
    from importlib import import_module
    _,plugin,root,_=installation
    wk=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.workshop_bridge')
    class Session(FakeWanSession):
        def merge_settings_with_defaults(self,settings):
            return {**super().merge_settings_with_defaults(settings),'prompt':'unrelated previous prompt'}
    for op,family,model,field,wrapper,label in [
        ('extract_flux','flux2','flux2_dev','flux_refmod_state','__flux_refmod_extract__','Creating FLUX RefMod'),
        ('extract','minimax_h3','h3_ref2va_pruned_checkpoint','h3_refmod_state','__h3refmod_extract__','Creating H3 RefMod'),
        ('decompile','minimax_h3','h3_ref2va_pruned_checkpoint','h3_refmod_state','__h3refmod_extract__','Decompiling H3 RefMod')]:
        task=wk.WorkshopTask(op,model,'celebs/Synthetic',{'name':'celebs/Synthetic'},root/'test.safetensors',family=family)
        settings=wk.extract_job_settings(Session(),task)
        assert settings['prompt']==label
        assert json.loads(settings['custom_settings'][field])[wrapper]==task.spec


def test_reference_single_save_blocks_overlapping_upload_and_review_retry(page):
    tab,errors=page
    tab.evaluate('''()=>{window.restartPhotoSearch=()=>{};window.showReferenceCollection=async()=>{};openPhoto('Synthetic One',null,'actress',true);window.confirm=()=>true;const old=fetch;window.refWrites=[];window.fetch=async(u,o={})=>{if(u!=='api/reference-images'||o.method!=='POST')return old(u,o);refWrites.push(JSON.parse(o.body));return new Promise(resolve=>window.finishRef=resolve)};collectImage('https://example.com/one.png');collectImage('https://example.com/one.png');}''')
    assert tab.evaluate('refWrites.length')==1
    assert tab.locator('#localImageUploadButton').is_disabled()
    assert tab.locator('#bulkPhotoCollect').is_disabled()
    tab.evaluate("finishRef({ok:false,status:409,json:async()=>({detail:{status:'review',reasons:['inspect']}})})")
    tab.wait_for_function('refWrites.length===2')
    assert tab.evaluate('refWrites[1].accept_review') is True
    tab.evaluate("finishRef({ok:false,status:409,json:async()=>({detail:{status:'review',reasons:['still rejected']}})})")
    tab.wait_for_function('photoSavePending.size===0')
    assert tab.evaluate('refWrites.length')==2
    assert tab.locator('#localImageUploadButton').is_enabled()
    assert 'Not saved' in tab.locator('#imageStatus').inner_text()
    assert not errors,errors


def test_reference_mutation_failure_never_overwrites_new_collection(page):
    tab,errors=page
    tab.evaluate('''()=>{window.restartPhotoSearch=()=>{};window.showReferenceCollection=async()=>{};window.confirm=()=>true;openPhoto('Synthetic One',null,'actress',true);const old=fetch;window.fetch=async(u,o={})=>String(u).startsWith('api/reference-images/old')?new Promise((resolve,reject)=>window.failOld=reject):old(u,o);removeReference('old');}''')
    tab.wait_for_function('typeof failOld==="function"')
    tab.evaluate("openPhoto('Synthetic Two',null,'actress',true);$('auditStatus').textContent='New collection ready';failOld(Error('old request failed'))")
    tab.wait_for_timeout(100)
    assert tab.locator('#auditStatus').inner_text()=='New collection ready'
    assert not errors,errors


def test_failed_encoder_discovery_clears_old_family(page):
    tab,errors=page
    tab.evaluate('''()=>{const old=fetch;window.fetch=async(u,o={})=>{const x=String(u);if(x.startsWith('api/workshop/models'))return {ok:false,json:async()=>({detail:'Offline'})};if(x.startsWith('api/workshop/sources'))return {ok:true,json:async()=>({sources:[]})};if(x==='api/workshop/mods')return {ok:true,json:async()=>({mods:[]})};return old(u,o)};$('workshopModel').innerHTML='<option value="old-h3">Old H3</option>';$('workshopModel').dataset.family='minimax_h3';$('workshopFamily').value='flux2';loadWorkshop()}''')
    tab.wait_for_function("$('workshopModelStatus').textContent.includes('Offline')")
    assert tab.locator('#workshopModel').is_disabled()
    assert tab.locator('#workshopModel option').count()==0
    tab.evaluate('startWorkshopCreate()')
    assert 'Choose a compatible encoder' in tab.locator('#workshopCreateStatus').inner_text()
    assert not errors,errors


def test_workshop_poll_failure_does_not_enable_duplicate_submission(page):
    tab,errors=page
    tab.evaluate('''()=>{const old=fetch;window.fetch=async(u,o={})=>{if(String(u).startsWith('api/workshop/jobs/'))throw Error('Temporary connection loss');return old(u,o)};setWorkshopBusy(true);workshopPollJob('synthetic-job','extract','Example')}''')
    tab.wait_for_function("$('workshopCreateStatus').textContent.includes('status unavailable')")
    assert tab.evaluate('workshopBusy') is True
    assert tab.locator('button[onclick="startWorkshopCreate()"]').is_disabled()
    assert 'Do not submit again' in tab.locator('#workshopCreateStatus').inner_text()
    tab.evaluate('clearTimeout(workshopPoll)')
    assert not errors,errors
