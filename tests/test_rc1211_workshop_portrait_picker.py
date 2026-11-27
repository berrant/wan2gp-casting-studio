"""Explicit Workshop test-image model selection, including stale discovery."""
from test_native_plugin import installation
from test_persona_power import tab
API='/casting-studio/api'

def test_portrait_model_listing_family_and_readiness(installation,monkeypatch):
    c,p,*_=installation
    monkeypatch.setattr(p.queue_bridge,'models',lambda board:[{'model_type':board+'-good','name':board,'ready':True},{'model_type':board+'-bad','name':'Not ready','ready':False}])
    for family in ('minimax_h3','flux2'):
        r=c.get(API+'/workshop/portrait-models',params={'family':family});assert r.status_code==200
        models=r.json()['models'];assert models and all(m['model']!='h3_video' and m['model_type'].endswith('-good') for m in models)
        assert all(m['model'].startswith(('h3_','p_h3'))==(family=='minimax_h3') for m in models)
    assert c.get(API+'/workshop/portrait-models?family=invalid').status_code==400

def test_explicit_portrait_picker_submission(tab):
    tab.evaluate('''() => {window.sent=null;workshopSources=[{person:'Ada Test',production:'Show',character:'Captain'}];$('workshopCollection').innerHTML='<option value="0">Ada</option>';$('workshopModel').innerHTML='<option value="encoder">Encoder</option>';$('workshopName').value='Ada_H3';$('workshopPhotos').innerHTML='<input class="workshopPhotoCheck" type="checkbox" checked value="ref">';const old=fetch;window.fetch=async(u,o)=>String(u).startsWith('api/workshop/portrait-models')?{ok:true,json:async()=>({models:[{model:'h3_image',model_type:'first',name:'First',prompt:'First full portrait prompt'},{model:'h3_image_pruned',model_type:'chosen',name:'Second',prompt:'Second full portrait prompt'}]})}:old(u,o);workshopRun=async(op,payload)=>{window.sent=payload};$('workshopTestPortrait').checked=true;refreshWorkshopPortraitModels()}''')
    tab.wait_for_function("!$('workshopPortraitModel').disabled")
    tab.evaluate('startWorkshopCreate()');assert tab.evaluate('window.sent') is None
    assert 'Choose a compatible' in tab.locator('#workshopCreateStatus').text_content()
    tab.locator('#workshopPortraitModel').evaluate("e=>{e.value=JSON.stringify(['h3_image_pruned','chosen']);e.dispatchEvent(new Event('change'))}")
    tab.evaluate('startWorkshopCreate()')
    assert tab.evaluate('window.sent.test_portrait_model_type')=='chosen'
    assert tab.evaluate('window.sent.test_portrait_prompt')==tab.locator('#workshopPortraitPrompt').text_content()=='Second full portrait prompt'
    assert tab.evaluate('window.sent.test_portrait_model')=='h3_image_pruned'
    assert tab.evaluate('window.sent.model_type')=='encoder'
    tab.evaluate("$('workshopTestPortrait').checked=false;refreshWorkshopPortraitModels();startWorkshopCreate()")
    assert tab.evaluate('window.sent.test_portrait') is False
    assert tab.evaluate("!('test_portrait_model' in window.sent)")

def test_portrait_picker_rejects_stale_family_discovery(tab):
    tab.evaluate('''() => {const old=fetch;window.fetch=(u,o)=>{if(!String(u).startsWith('api/workshop/portrait-models'))return old(u,o);const isH3=String(u).includes('minimax_h3');return new Promise(resolve=>setTimeout(()=>resolve({ok:true,json:async()=>({models:[{model:isH3?'h3_image':'flux2_dev',model_type:isH3?'h3':'flux',name:isH3?'H3':'Flux'}]})}),isH3?200:10))};$('workshopTestPortrait').checked=true;$('workshopFamily').value='minimax_h3';refreshWorkshopPortraitModels();$('workshopFamily').value='flux2';refreshWorkshopPortraitModels()}''')
    tab.wait_for_function("$('workshopPortraitModel').options.length===2")
    tab.wait_for_timeout(250)
    assert tab.locator('#workshopPortraitModel option').all_text_contents()==['Choose an installed image model…','Flux · flux']
