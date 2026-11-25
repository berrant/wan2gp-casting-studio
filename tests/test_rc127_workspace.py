"""Browser workflows for the eight RC12.7 workspaces."""
from test_persona_power import tab
from test_rc126_image_prompt_review import setup


def test_workspace_tabs_keep_drafts_and_settings(tab):
    setup(tab)
    assert tab.locator('#generatorPreviewPanel').is_visible()
    assert tab.locator('#generatorSessionPanel').is_hidden()
    tab.get_by_role('textbox',name='Image 2 final prompt',exact=True).fill('Keep my image draft')
    tab.locator('button[data-workspace=model]').click()
    assert tab.locator('#generatorSessionPanel').is_visible()
    assert tab.locator('#generatorPreviewPanel').is_hidden()
    tab.locator('button[data-workspace=prompts]').click()
    assert tab.get_by_role('textbox',name='Image 2 final prompt',exact=True).input_value()=='Keep my image draft'
    tab.locator('button[data-workspace=batch]').click()
    assert tab.locator('#generatorBatchPanel').is_visible()


def test_explicit_variant_picker(tab):
    tab.evaluate('''() => {catalog={...catalog,models:[...catalog.models,{name:'Zoie Palmer',path:'Zoie_Palmer__role__Android_H3.safetensors',filename:'Zoie_Palmer__role__Android_H3.safetensors',family:'minimax_h3',role_specific:true}]};showTab('productions');showProductionCast(productionData)}''')
    picker=tab.locator('#productionCast .cast-row').first.locator('select')
    assert picker.locator('option').count()==3
    picker.select_option('Zoie_Palmer__role__Android_H3.safetensors')
    tab.wait_for_function("choices.some(c=>c.refmod==='Zoie_Palmer__role__Android_H3.safetensors')")
    assert tab.evaluate('mockWrites.at(-1).refmod')=='Zoie_Palmer__role__Android_H3.safetensors'
    assert tab.locator('#productionCast .cast-row').first.locator('select').input_value()=='Zoie_Palmer__role__Android_H3.safetensors'


def test_image_editor_shared_identity_and_failed_save(tab):
    tab.evaluate('''() => {const old=fetch;window.identityWrites=[];window.failIdentity=false;const ok=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});window.fetch=(u,o={})=>{if(String(u).startsWith('api/characters/identity')){if(o.method==='PUT'){if(failIdentity)return Promise.resolve({ok:false,text:async()=> 'offline'});identityWrites.push(JSON.parse(o.body));}return Promise.resolve(ok({traits:identityWrites.at(-1)?.traits||'Original traits',source:'custom'}));}return old(u,o)};$('promptModel').value='flux2_dev';$('imageEditorModal').classList.add('open');showImageEditorFields({image_count:2,shots:[]});initImageSetIdentity()}''')
    tab.wait_for_function("$('imageIdentityTraits').value==='Original traits'&&!$('imageIdentitySave').disabled")
    tab.locator('#imageIdentityTraits').fill('Edited fixed character traits')
    tab.evaluate('window.failIdentity=true;saveImageSetIdentity()')
    assert tab.locator('#imageIdentityTraits').input_value()=='Edited fixed character traits'
    assert 'not saved' in tab.locator('#imageIdentityStatus').text_content()
    tab.evaluate('window.failIdentity=false;saveImageSetIdentity()')
    assert tab.evaluate('identityWrites[0].traits')=='Edited fixed character traits'


def test_gallery_navigation_video_is_paused_and_history_filter(tab):
    tab.evaluate('''() => {galleryResults=[{id:'a',kind:'image',task_details:{person:'First',prompt:'Original first prompt'}},{id:'b',kind:'video',task_details:{person:'Second',prompt:'Original second prompt'}}];galleryIndex=0;$('resultGalleryModal').classList.add('open');renderResultGallery()}''')
    assert tab.locator('#galleryIdentity').text_content()=='First'
    tab.locator('#galleryNext').click()
    assert tab.locator('#galleryIdentity').text_content()=='Second'
    assert tab.locator('#galleryMedia video').evaluate('e=>!e.autoplay&&e.paused&&e.controls')
    assert tab.locator('#galleryPrompt').text_content()=='Original second prompt'
    tab.evaluate("closeResultGallery();uxHistoryRecords=[{id:'1',model_type:'H3',state:'completed',tasks:[{person:'Ada',production:'Example Show'}]},{id:'2',model_type:'Flux',state:'failed',tasks:[{person:'Other'}]}];$('uxHistoryModal').classList.add('open');renderUXHistory()")
    tab.locator('#historyFilter').fill('example show');assert tab.locator('#uxHistoryRows .ux-history-row').count()==1
    tab.locator('#historyState').select_option('failed');assert tab.locator('#uxHistoryRows .ux-history-row').count()==0
