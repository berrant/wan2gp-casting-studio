"""Factory scenarios, independent customization and neutral Personal defaults."""
import importlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import pytest
from test_native_plugin import installation, _create_public_selection, _mock_fork, FakeWanSession

API='/casting-studio/api'
ROOT=Path(__file__).resolve().parents[1]
OLD=('wardrobe transformation','transformation shimmer','both turns')

def no_old(text):
    assert not any(word in text.lower() for word in OLD),text

def test_all_models_factory_scenarios(installation):
    c,*_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    item={'person':'Ada Test','character':'Captain','production':'Example Show (2025)','refmod':'Ada_Test_H3.safetensors'}
    v=c.get(API+'/prompts/template').json()
    assert v['video_count']==2 and not v['include_non_diegetic_music']
    full=srv.prompt_for_selection(item,{**v,'video_count':4})
    segments=full.split('\n\n');assert len(segments)==4
    for segment,expected in zip(segments,('three-quarter profile','begins walking','expressive gesture','closing portrait')):
        assert expected in segment and 'all images provided' in segment
        assert 'Captain as portrayed by Ada Test in Example Show (2025)' in segment
        assert 'non_diegetic_music:\nN/A' in segment
        no_old(segment)
    models=[x['id'] for x in srv.MODEL_OPTIONS if x['kind']=='image'];assert len(models)==8
    for model in models:
        t=c.get(API+'/prompts/image-template',params={'model':model}).json()
        assert t['image_count']==5 and len(t['shots'])==5
        prompts=srv.image_prompts_for_selection(item,model,t,v,{}).split('\n\n')
        assert len(prompts)==5
        for prompt,expected in zip(prompts,('character portrait','full-body character showcase','environmental portrait','natural action pose','dramatic close-up')):
            assert expected.lower() in prompt.lower()
            assert 'all images provided' in prompt
            assert srv.IMAGE_REFERENCE_LABEL[model] not in prompt
            assert 'Bottom caption:' not in prompt
            assert 'Captain as portrayed by Ada Test in Example Show (2025)' in prompt
            no_old(prompt)
            assert 'wardrobe_description:' in prompt

def test_personal_defaults_are_neutral(installation):
    c,*_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    item={'person':'Private Test','relationship':'Friend','refmod':'Private_Test_H3.safetensors'}
    template={**srv.SAMPLE_TEMPLATE,'video_count':4,'include_caption':True}
    prompts=srv.prompt_for_selection(item,template,personal=True)
    assert prompts.count(srv.PERSONAL_STUDIO)==4
    assert 'appropriate everyday clothing' in prompts and 'camera tracks' not in prompts
    assert 'Private Test - Friend' in prompts
    no_old(prompts)
    for option in srv.MODEL_OPTIONS:
        if option['kind']!='image':continue
        model=option['id'];t=srv.image_template_for_model(model)
        prompts=srv.image_prompts_for_selection(item,model,t,template,{},personal=True)
        assert prompts.count(srv.PERSONAL_STUDIO)==5
        assert 'production-authentic' not in prompts.lower()
        assert 'appropriate everyday clothing' in prompts
        no_old(prompts)
        assert 'neutral gray studio background' in srv.portrait_prompt(model)

def test_saved_templates_and_final_edits_survive_until_explicit_reset(installation):
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    _mock_fork(root);p.queue_bridge.api_session=FakeWanSession()
    key=_create_public_selection(c)
    saved={**srv.SAMPLE_TEMPLATE,'wardrobe':'My custom wardrobe.','video1_action':'My independent scene.'}
    assert c.put(API+'/prompts/template',json=saved).status_code==200
    assert c.get(API+'/prompts/template').json()==saved
    for model in ('flux2_dev','h3_image'):
        payload={'image_count':1,'shots':[{'action':'Custom still action','wardrobe':'Custom still wardrobe'}]}
        assert c.put(API+'/prompts/image-template',params={'model':model},json=payload).status_code==200
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','scene':1}
    original='A custom finished scene with original direction.'
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':original}).status_code==200
    assert c.post(API+'/prompts/template/reset').json()==srv.SAMPLE_TEMPLATE
    assert c.post(API+'/generator/preview',json=task).json()['prompt']==original
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':None}).status_code==200
    fresh=c.post(API+'/generator/preview',json=task).json()['prompt'];assert 'three-quarter profile' in fresh;no_old(fresh)
    assert c.post(API+'/prompts/image-template/reset',params={'model':'flux2_dev'}).json()['image_count']==5
    assert c.get(API+'/prompts/image-template',params={'model':'h3_image'}).json()['shots'][0]['action']=='Custom still action'
    # The actual prompt builder must honor a completely different user scenario.
    custom={**srv.SAMPLE_TEMPLATE,'wardrobe':'Custom clothing.','video1_action':'Read a book at a desk.'}
    prompt=srv.prompt_for_selection({'person':'Ada Test','refmod':'Ada_Test_H3.safetensors'},custom).split('\n\n')[0]
    assert 'Read a book at a desk.' in prompt and 'three-quarter profile' not in prompt
    no_old(prompt)

@pytest.mark.skipif(not shutil.which('node'),reason='Node unavailable')
def test_browser_additional_slots_match_server_defaults(installation):
    c,*_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    html=(ROOT/'app/index.html').read_text()
    source=re.search(r'function defaultImageShot\(index\)\{.*?\n\}',html,re.S).group()
    shots=json.loads(subprocess.check_output(['node','-e',source+'\nconsole.log(JSON.stringify(Array.from({length:10},(_,i)=>defaultImageShot(i+1))))'],text=True))
    assert shots==srv.image_template_normalized({'image_count':10})['shots']
    no_old(json.dumps(shots))
