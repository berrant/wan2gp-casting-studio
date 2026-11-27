"""Prompt formats, explicit wardrobe policies and native review parity."""
import importlib,re
import pytest
from test_native_plugin import installation,_mock_fork,FakeWanSession,_await_job
from test_dev55_browser import page
API='/casting-studio/api'

def role(c):
    item={'person':'Ada Test','character':'Captain Mira','production':'Example Series','year':2023,'refmod':'Ada_Test_H3.safetensors'}
    assert c.put(API+'/choices',json={'key':'',**item}).status_code==200
    key=next(x['key'] for x in c.get(API+'/choices').json() if x['character']==item['character'])
    return item,key

def test_wardrobe_modes_for_every_model_and_legacy_override(installation):
    c,*_=installation;s=importlib.import_module('cb_under_test.app.server');item,key=role(c)
    t={**s.SAMPLE_TEMPLATE,'video_count':1,'wardrobe_mode':'canon'}
    with pytest.raises(ValueError,match='Prepare and approve'):s.prompt_for_selection(item,t)
    assert c.put(API+'/characters/scene',json={'choice_key':key,'wardrobe':'Reviewed blue uniform.','setting':'A starship bridge.'}).status_code==200
    for mode,text in [('canon','Stale text.'),('transform','Gold flight jacket.'),('custom','Black raincoat.')]:
        for m in s.MODEL_OPTIONS:
            opts={'wardrobe_mode':mode,'wardrobe':text}
            video=m['kind']=='video'
            body=(s.prompt_for_selection(item,{**t,**opts}) if video else s.image_prompts_for_selection(item,m['id'],{'image_count':1,'shots':[opts]},t,{})).split('\n',1)[1]
            wardrobe=body.split('wardrobe_description:',1)[1]
            if mode=='canon':assert 'Reviewed blue uniform.' in wardrobe and text not in body
            if mode=='transform':
                assert text in wardrobe
                assert ('Reviewed blue uniform.' in wardrobe)==video
                assert ('By the end' in wardrobe)==video
            if mode=='custom':assert text in wardrobe and 'Reviewed blue uniform.' not in body
            assert 'all images provided' in body
            assert text not in body.split('wardrobe_description:',1)[0]
            if not video:assert '\n' not in body and 'subject_definitions:' not in body
    assert s.merge_video_template(t,{'wardrobe':'Legacy saved outfit.'})['wardrobe_mode'] is None
    with pytest.raises(ValueError,match='destination outfit'):s.prompt_for_selection(item,{**t,'wardrobe_mode':'transform','wardrobe':''})
    with pytest.raises(ValueError,match='custom outfit'):s.prompt_for_selection(item,{**t,'wardrobe_mode':'custom','wardrobe':''})
    assert c.put(API+'/prompts/template',json={**t,'wardrobe_mode':'typo'}).status_code==422

def test_all_video_branches_use_six_sections_and_no_phantom_continuation(installation):
    c,*_=installation;s=importlib.import_module('cb_under_test.app.server')
    item,_=role(c)
    for subject,personal in [(item,False),({'person':'Ada Test','refmod':'Ada_Test_H3.safetensors'},False),({'person':'Private Test','refmod':'Private_Test_H3.safetensors'},True)]:
        for body in s.prompt_for_selection(subject,{**s.SAMPLE_TEMPLATE,'video_count':4},personal=personal).split('\n\n'):
            assert re.findall(r'^([a-z_]+):$',body,re.M)==['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            assert 'following Video' not in body and 'end of Video' not in body
            assert 'wardrobe_description:' in body.split('detailed_description:',1)[1]
    with pytest.raises(ValueError,match='reserved H3'):s.prompt_for_selection(item,{**s.SAMPLE_TEMPLATE,'video1_action':'summary:\nInvalid duplicate.'})

def test_explicit_wardrobe_review_rejects_stale_then_matches_native(installation):
    c,p,root,_=installation;_mock_fork(root)
    session=FakeWanSession();p.queue_bridge.api_session=session
    item,key=role(c)
    s=importlib.import_module('cb_under_test.app.server')
    t={**s.SAMPLE_TEMPLATE,'video_count':1,'wardrobe_mode':'transform','wardrobe':'Gold flight jacket.'}
    assert c.put(API+'/prompts/template',json=t).status_code==200
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','scene':1}
    # The concrete fake model ID is chosen from the real bridge response.
    task['model_type']=next(x['model_type'] for x in p.queue_bridge.models('h3_video') if x['ready'])
    assert c.post(API+'/generator/preview',json=task).status_code==400
    assert c.put(API+'/characters/scene',json={'choice_key':key,'wardrobe':'Reviewed blue uniform.','setting':'A starship bridge.'}).status_code==200
    preview=c.post(API+'/generator/preview',json=task);assert preview.status_code==200,preview.text
    old=preview.json();assert 'Gold flight jacket.' in old['prompt']
    assert c.put(API+'/prompts/template',json={**t,'wardrobe':'Green flight jacket.'}).status_code==200
    assert c.post(API+'/generator/submit',json={**task,'review_token':old['review_token']}).status_code==409
    fresh=c.post(API+'/generator/preview',json=task);assert fresh.status_code==200,fresh.text
    data=fresh.json();assert 'Green flight jacket.' in data['prompt'] and 'Gold flight jacket.' not in data['prompt']
    original=session.merge_settings_with_defaults
    session.merge_settings_with_defaults=lambda d:{**original(d),'prompt_enhancer':'TI'}
    result=c.post(API+'/generator/submit',json={**task,'review_token':data['review_token']});assert result.status_code==200,result.text
    assert _await_job(c,result.json()['id'])['state']=='completed'
    assert session.submitted[0]['prompt']==data['prompt']
    assert session.submitted[0]['prompt_enhancer']==''


def test_wardrobe_radio_mode_and_copy_preserve_independent_shots(page):
    tab,errors=page
    tab.evaluate("document.querySelector('#promptModel').value='flux2_dev';showImageEditorFields({image_count:2,shots:[{wardrobe:autoWardrobeText,action:'Stand'},{wardrobe:'Old coat',action:'Sit'}],visual_style:'Photo'});$('imageEditorModal').classList.add('open')")
    a=tab.locator('#shotWardrobe1');assert not a.is_visible()
    tab.locator('input[name=shotWardrobe1Mode][value=transform]').check();assert a.is_visible()
    a.fill('Green coat');tab.evaluate("imageSetCopy('wardrobe')")
    data=tab.evaluate('readImageEditorDraft()');assert all(x['wardrobe_mode']=='transform' and x['wardrobe']=='Green coat' for x in data['shots'])
    assert data['shots'][1]['action']=='Sit'
    tab.locator('input[name=shotWardrobe1Mode][value=canon]').check();assert not a.is_visible()
    assert tab.evaluate("readImageEditorDraft().shots[0].wardrobe_mode")=='canon'
    assert not errors,errors


def test_once_per_sequence(installation):
 c,p,root,_=installation;_mock_fork(root);session=FakeWanSession();session.defs[0]['sliding_window']=True;p.queue_bridge.api_session=session
 item,key=role(c);s=importlib.import_module('cb_under_test.app.server')
 assert c.put(API+'/characters/scene',json={'choice_key':key,'wardrobe':'Reviewed blue uniform.','setting':'A starship bridge.'}).status_code==200
 t={**s.SAMPLE_TEMPLATE,'video_count':4,'wardrobe_mode':'transform','wardrobe':'Gold flight jacket.','include_caption':True}
 assert c.put(API+'/prompts/template',json=t).status_code==200
 task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':60,'video_script_mode':'sequence','sliding':{'sliding_window_size':362,'sliding_window_overlap':18}}
 pre=c.post(API+'/generator/preview',json=task);assert pre.status_code==200,pre.text
 data=pre.json();prompt=data['prompt'];assert prompt.count('Reviewed blue uniform.')==1;assert prompt.count('Gold flight jacket.')==4;assert prompt.count('A crisp, fixed bottom caption reads:')==4;assert prompt.count('subject_definitions:')==4
 assert c.post(API+'/generator/preview',json={**task,'video_script_mode':'single'}).status_code==400
 result=c.post(API+'/generator/submit',json={**task,'review_token':data['review_token']});assert result.status_code==200,result.text
 assert _await_job(c,result.json()['id'])['state']=='completed';assert len(session.submitted)==1;assert session.submitted[0]['prompt']==prompt
