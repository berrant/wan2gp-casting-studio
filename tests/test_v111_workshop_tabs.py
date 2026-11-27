"""Explicit workshop navigation must not open a collection or RefMod by inference."""
from test_persona_power import tab

MOCK='''() => {window.wsCalls=[];const old=fetch;window.fetch=async(u,o)=>{const path=String(u).split('?')[0];if(!path.startsWith('api/workshop/'))return old(u,o);wsCalls.push(String(u));const data={
'api/workshop/sources':{sources:[{person:'Example One',production:'Example Show',character:'Captain',count:1},{person:'Example Two',production:'Other Show',character:'Doctor',count:1}]},
'api/workshop/models':{models:[{ready:true,model_type:'encoder',name:'Encoder'}]},
'api/workshop/photos':{photos:[{id:'photo',url:'data:image/png;base64,',width:100,height:100,quality:'good',quality_rank:1}]},
'api/workshop/mods':{mods:[{name:'celebs/Example',filename:'Example.safetensors',bytes:100,metadata:{kind:'identity'}}]},
'api/workshop/scan-status':{running:false,total:1,checked:1,valid:1,invalid:0}}[path];return {ok:true,json:async()=>data}}}'''

def test_direct_entry_and_tab_switching_never_auto_select(tab):
    tab.evaluate(MOCK)
    tab.locator('#workshopTab').click()
    tab.wait_for_function("$('workshopCollection').options.length===3")
    assert tab.locator('#workshopMakePane').is_visible()
    assert not tab.locator('#workshopDecompilePane').is_visible()
    assert tab.locator('#workshopCollection').input_value()==''
    assert tab.locator('#workshopName').input_value()==''
    assert not tab.evaluate("wsCalls.some(x=>x.startsWith('api/workshop/photos')||x.startsWith('api/workshop/mods'))")
    tab.locator('#workshopCollection').select_option('1')
    tab.wait_for_function("$('workshopPhotos').querySelectorAll('.workshopPhotoCheck').length===1")
    tab.locator('.workshopPhotoCheck').uncheck()
    tab.locator('#workshopName').fill('Custom_Draft')
    tab.locator('#workshopDecompileTab').click()
    tab.wait_for_function("$('workshopMod').options.length===2")
    assert not tab.locator('#workshopMakePane').is_visible()
    assert tab.locator('#workshopDecompilePane').is_visible()
    assert tab.locator('#workshopMod').input_value()==''
    assert tab.locator('#workshopMetadata').inner_text()=='Select a RefMod.'
    assert not tab.locator('#workshopResults').is_visible()
    tab.locator('#workshopMod').select_option('0')
    assert 'identity' in tab.locator('#workshopMetadata').inner_text()
    tab.locator('#workshopMakeTab').click()
    assert tab.locator('#workshopCollection').input_value()=='1'
    assert tab.locator('#workshopName').input_value()=='Custom_Draft'
    assert not tab.locator('.workshopPhotoCheck').is_checked()
    tab.locator('#productionsTab').click()
    tab.locator('#workshopTab').click()
    tab.wait_for_function("$('workshopCollection').options.length===3")
    assert tab.locator('#workshopCollection').input_value()==''
    assert not tab.locator('#workshopPhotos .workshopPhotoCheck').count()
    assert tab.locator('#workshopName').input_value()==''

def test_explicit_links_and_missing_collection(tab):
    tab.evaluate(MOCK)
    tab.evaluate("openRoleWorkshop('Example Two','Other Show','Doctor')")
    tab.wait_for_function("$('workshopCollection').value==='1' && workshopPhotos.length===1")
    assert tab.locator('#workshopMakePane').is_visible()
    assert tab.evaluate("wsCalls.some(x=>x.includes('character=Doctor'))")
    tab.evaluate("openRoleWorkshop('Example One','Example Show','Unknown role')")
    tab.wait_for_function("$('workshopCollection').options.length===2")
    assert tab.locator('#workshopCollection').input_value()==''
    assert not tab.evaluate("wsCalls.some(x=>x.includes('character=Captain'))")
    assert not tab.locator('#workshopPhotos .workshopPhotoCheck').count()
