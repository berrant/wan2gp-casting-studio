"""Direct appearance navigation and explicit library conversion contracts."""
from test_native_plugin import installation
from test_dev58_conversion import _setup, write_mod, API
from test_dev55_browser import page


def test_library_conversion_without_choice_and_no_relink(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch)
    choice=c.get(API+'/choices').json()[0]
    assert c.delete(API+'/choices/'+choice['key']).status_code==200
    plan=c.get(API+'/settings/conversion/plan').json()
    assert plan['ready'] and plan['count']==1,plan
    assert not c.get(API+'/choices').json()
    start=c.post(API+'/settings/conversion/start',json={'plan_token':plan['plan_token']})
    assert start.status_code==200,start.text
    job=start.json()['id']
    assert c.post(API+'/settings/conversion/start',json={'plan_token':plan['plan_token']}).status_code==409
    assert c.get(API+'/settings/conversion/status').json()['job']['id']==job
    p.queue_bridge.process_pending_in_gradio(p.queue_bridge.api_session)
    result=c.get(API+'/generator/jobs/'+job).json()
    assert result['state']=='completed',result
    assert result['operation']=='library_convert'
    assert c.post(API+'/choices/conversion/apply',json={'job_id':job}).status_code==404
    assert not c.get(API+'/choices').json()
    assert c.get(API+'/settings/conversion/plan').json()['count']==0
    assert (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').exists()


def test_library_preview_stale_and_existing_formats(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch)
    plan=c.get(API+'/settings/conversion/plan').json();assert plan['count']==1
    dest=root/'refmods/flux2/celebs/Ada_Test_FLUX.safetensors'
    write_mod(dest,'klein9_refmod_meta',{'converted_from':'celebs/Ada_Test_H3'})
    fresh=c.get(API+'/settings/conversion/plan').json()
    assert fresh['count']==0 and fresh['skipped'][0]['reason']=='Existing FLUX counterpart'
    assert c.post(API+'/settings/conversion/start',json={'plan_token':plan['plan_token']}).status_code==409
    assert c.get(API+'/settings/conversion/status').json()['job'] is None


def test_library_video_and_private_exclusions(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch,kind='video')
    write_mod(root/'refmods/minimax_h3/personal/Private_Test_H3.safetensors','refmod_meta',{'kind':'image'})
    plan=c.get(API+'/settings/conversion/plan').json()
    assert plan['count']==0 and all('Private' not in x['source'] for x in plan['skipped'])
    plan=c.get(API+'/settings/conversion/plan?include_personal=true').json()
    assert plan['count']==0 and any('consent' in x['reason'] for x in plan['skipped'])


def test_library_cancellation_before_native_handoff(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch)
    plan=c.get(API+'/settings/conversion/plan').json()
    job=c.post(API+'/settings/conversion/start',json={'plan_token':plan['plan_token']}).json()['id']
    assert c.post(API+'/generator/jobs/'+job+'/cancel').status_code==200
    assert c.get(API+'/generator/jobs/'+job).json()['state']=='cancelled'
    assert not list((root/'refmods/flux2/celebs').glob('*.safetensors'))


def test_character_link_opens_editor_without_selecting(page):
    tab,errors=page
    tab.evaluate('''() => { const original=window.fetch; window.fetch=async(url,opts={})=>{
        const path=String(url);const json=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
        if(path.startsWith('api/appearance/references?')) return json({role:{person:'Zoie Palmer',character:'The Android',production:'Dark Matter',year:2015,label:'The Android — Dark Matter (2015)',profile_key:'example'},photos:[]});
        if(path.startsWith('api/characters/identity?')) return json({traits:'Fixed appearance',source:'manual'});
        return original(url,opts);
    };}''')
    tab.locator('#productionCast').get_by_role('button',name='The Android',exact=True).click()
    tab.wait_for_function("$('cardIdentityTraits').value==='Fixed appearance'")
    assert tab.locator('#cardIdentityModal').is_visible()
    assert tab.evaluate('choices.length')==1
    assert tab.locator('#cardIdentityAI').is_enabled()
    assert not errors,errors


def test_settings_conversion_preview_requires_explicit_start(page):
    tab,errors=page
    tab.evaluate('''() => { const original=window.fetch; window.fetch=async(url,opts={})=>{
      const path=String(url);const json=data=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});
      if(path.startsWith('api/settings/conversion/plan'))return json({count:1,batch_count:1,ready:true,plan_token:'example',items:[{source:'Ada_Test_H3.safetensors'}],skipped:[],h3_model:'h3',flux_model:'flux'});
      if(path==='api/settings/conversion/status')return json({job:null});
      return original(url,opts);
    };}''')
    tab.evaluate("$('settingsModal').classList.add('open');jumpStudioSettings('libraryConversion')")
    assert tab.locator('#bulkConvertStart').is_disabled()
    tab.locator('#bulkConvertPreview').click()
    tab.wait_for_function("!$('bulkConvertStart').disabled")
    assert 'Ada_Test_H3' in tab.locator('#bulkConvertReport').inner_text()
    tab.locator('#bulkConvertPrivate').check()
    assert tab.locator('#bulkConvertStart').is_disabled()
    assert not errors,errors


def test_direct_catalog_portrayal_api_without_selection(installation):
    import json
    c,p,root,_=installation
    role=dict(production='Synthetic Series',actress='Synthetic Performer',character='Alien',year=2024)
    assert c.post(API+'/productions/cast',json=role).status_code==200
    key='catalog:'+json.dumps([role['actress'],role['character'],role['production'],2024])
    reply=c.get(API+'/appearance/references',params={'choice_key':key})
    assert reply.status_code==200,reply.text
    assert reply.json()['role']['year']==2024
    assert c.get(API+'/appearance/references',params={'choice_key':key.replace('2024','2023')}).status_code==400
    assert not c.get(API+'/choices').json()


def test_missing_native_models_preview_is_not_server_error(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch)
    def models(board):
        if board=='h3_video':return [{'model_type':'h3-pruned','ready':True}]
        if board=='flux3_klein':return [{'model_type':'flux3-test','ready':True}]
        raise RuntimeError('unsupported model')
    monkeypatch.setattr(p.queue_bridge,'models',models)
    plan=c.get(API+'/settings/conversion/plan').json()
    assert plan['ready'] and plan['flux_model']=='flux3-test'
    def unavailable(board):raise RuntimeError('unsupported model')
    monkeypatch.setattr(p.queue_bridge,'models',unavailable)
    plan=c.get(API+'/settings/conversion/plan').json()
    assert not plan['ready'] and plan['count']==1


def test_source_mutation_stops_native_conversion(installation,monkeypatch):
    c,p,root,s=_setup(installation,monkeypatch)
    plan=c.get(API+'/settings/conversion/plan').json()
    job=c.post(API+'/settings/conversion/start',json={'plan_token':plan['plan_token']}).json()['id']
    write_mod(root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors','refmod_meta',{'kind':'image','description':'Changed'})
    p.queue_bridge.process_pending_in_gradio(p.queue_bridge.api_session)
    result=c.get(API+'/generator/jobs/'+job).json()
    assert result['state']=='failed' and 'Source changed' in result['error']
    assert not list((root/'refmods/flux2/celebs').glob('*.safetensors'))
