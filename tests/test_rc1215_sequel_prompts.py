"""Public fictional portrayal continuity and efficient default rendering."""
import importlib
import re
from test_native_plugin import installation, _create_public_selection, _mock_fork, FakeWanSession

API='/casting-studio/api'


def test_character_invariants_and_six_video_sections(installation):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    item={'person':'Ada Test','character':'Pilot','production':'Example Series','year':2025,'refmod':'Ada_Test_H3.safetensors'}
    traits='Blue skin on every exposed surface, silver irises, two biological cranial horns.'
    assert c.put(API+'/characters/identity',json={**{k:item[k] for k in ('person','character','production','year')},'traits':traits}).status_code==200
    tpl={**s.SAMPLE_TEMPLATE,'video_count':4,'wardrobe':'Custom jacket.','video2_action':'Walk across the new station.'}
    out=s.prompt_for_selection(item,tpl).split('\n\n')
    assert len(out)==4
    for part in out:
        sections=re.findall(r'^([a-z_]+):$',part,re.M)
        assert sections==['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
        assert part.count(traits)==1 and part.count('<Subject 1> is')==1
        assert 'partially_preserved' in part and 'all images provided' in part
        assert 'facial identity only' in part and 'any in-character references' in part and 'exposed skin surfaces' in part
        assert 'Pilot as seen in Example Series (2025)' in part
        assert 'following Video' not in part and 'at the end of Video' not in part
        assert '<Picture ' not in part and '<Subject 2>' not in part
        assert 'Custom jacket.' in part.split('wardrobe_description:',1)[1]
        assert 'Custom jacket.' not in part.split('wardrobe_description:',1)[0]
        assert 'bottom caption' not in part and 'non_diegetic_music:\nN/A' in part
    assert 'Walk across the new station.' in out[1]
    assert 'bottom caption' in s.prompt_for_selection(item,{**tpl,'include_caption':True})


def test_still_protocols_and_caption_roundtrip(installation):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    item={'person':'Ada Test','character':'Pilot','production':'Example Series','year':2025,'refmod':'Ada_Test_H3.safetensors'}
    traits='Blue epidermis and silver irises.'
    c.put(API+'/characters/identity',json={**{k:item[k] for k in ('person','character','production','year')},'traits':traits})
    for model in [x['id'] for x in s.MODEL_OPTIONS if x['kind']=='image']:
        payload={'image_count':1,'shots':[{'action':'Open the door.','wardrobe':'Custom coat.','setting':'New starship.'}],'include_caption':True}
        assert c.put(API+'/prompts/image-template',params={'model':model},json=payload).status_code==200
        t=c.get(API+'/prompts/image-template',params={'model':model}).json();assert t['include_caption'] is True
        text=s.image_prompts_for_selection(item,model,t,s.SAMPLE_TEMPLATE,{})
        assert text.count(traits)==1 and 'Open the door.' in text and 'New starship.' in text
        assert 'wardrobe_description: Custom coat.' in text
        assert 'Bottom caption: "Ada Test - Pilot - Example Series (2025)".' in text
        body=text.split('\n',1)[1]
        assert not re.search(r'<(?:Picture |ref_image_)\d+>|\bimage [1-9]\d*\b',body,re.I)
        assert body.startswith('subject_definitions:\n') == (model=='p_h3_image')
        assert ('Reference roles:' in text)==(s.MODEL_BY_ID[model]['family']=='minimax_h3')
        assert c.post(API+'/prompts/image-template/reset',params={'model':model}).json()['include_caption'] is False
    old={k:v for k,v in s.SAMPLE_TEMPLATE.items() if k!='include_caption'}
    assert c.put(API+'/prompts/template',json=old).status_code==200
    assert c.get(API+'/prompts/template').json()['include_caption'] is False
    assert c.put(API+'/prompts/template',json={**old,'include_caption':True}).status_code==200
    assert c.get(API+'/prompts/template').json()['include_caption'] is True


def test_preview_excludes_export_heading_and_custom_final_survives(installation):
    c,p,root,_=installation
    _mock_fork(root);p.queue_bridge.api_session=FakeWanSession()
    key=_create_public_selection(c)
    s=importlib.import_module('cb_under_test.app.server')
    task={'choice_key':key,'model':'h3_image','model_type':'h3_image','scene':1}
    req=s.CastTask(**task)
    text,_,_=s.build_live_cast_prompt(req)
    assert not text.startswith('### Image') and 'RefMod:' not in text
    custom='My original production scene. Keep every word of this custom prompt.'
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':custom}).status_code==200
    assert s.build_live_cast_prompt(req)[0]==custom
