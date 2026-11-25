"""Caption ownership for generated prompts; stored drafts remain verbatim."""
import importlib
import pytest
from test_native_plugin import installation, _create_public_selection, _mock_fork, FakeWanSession, _await_job

API='/casting-studio/api'
PLACEHOLDER='A crisp, fixed bottom caption reads: "[Performer Name] - [Character Name] - [Production Title]".'
DUPLICATE='Bottom caption: “Stale identity”.'
UNCLOSED=PLACEHOLDER[:-2]  # exact screenshot: no closing quote or period


def test_video_caption_toggle_all_subject_types(installation,monkeypatch):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(s,'is_broadcast_credit',lambda item:item.get('person')=='Broadcast Test')
    monkeypatch.setattr(s,'is_video_game_character',lambda name:name=='Game Test')
    base={'person':'Ada Test','refmod':'Ada_Test_H3.safetensors'}
    for item,personal,label in [
        (base,False,'Ada Test'),
        ({**base,'character':'Pilot','production':'Example Series','year':2025},False,'Ada Test - Pilot - Example Series (2025)'),
        ({**base,'person':'Broadcast Test','character':'Host','production':'Example Series','year':2025},False,'Broadcast Test - Host - Example Series (2025)'),
        ({**base,'person':'Game Test','production':'Example Game'},False,'Game Test - Example Game'),
        ({**base,'person':'Private Test','relationship':'Friend'},True,'Private Test - Friend')]:
        for enabled in (True,False,True,False):
            template={**s.SAMPLE_TEMPLATE,'video_count':4,'include_caption':enabled,
                      **{f'video{i}_action':'Walk forward. '+PLACEHOLDER+'\n'+UNCLOSED+'\n'+DUPLICATE+'\nHold pose.' for i in range(1,5)}}
            for part in s.prompt_for_selection(item,template,personal=personal).split('\n\n'):
                assert part.lower().count('bottom caption')==int(enabled)
                assert ('A crisp, fixed bottom caption reads: "'+label+'".') in part if enabled else 'bottom caption' not in part.lower()
                assert '[Performer Name]' not in part and 'Stale identity' not in part
                assert 'Walk forward.' in part and 'Hold pose.' in part
            assert PLACEHOLDER in template['video1_action']


def test_still_caption_toggle_every_model_and_subject_type(installation,monkeypatch):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    monkeypatch.setattr(s,'is_broadcast_credit',lambda item:item.get('person')=='Broadcast Test')
    monkeypatch.setattr(s,'is_video_game_character',lambda name:name=='Game Test')
    for model in [x['id'] for x in s.MODEL_OPTIONS if x['kind']=='image']:
        for item,personal in [({'person':'Ada Test'},False),({'person':'Ada Test','character':'Pilot','production':'Example Series','year':2025},False),({'person':'Broadcast Test','character':'Host','production':'Example Series','year':2025},False),({'person':'Game Test','production':'Example Game'},False),({'person':'Private Test','relationship':'Friend'},True)]:
            for enabled in (False,True):
                t={'image_count':2,'include_caption':enabled,'visual_style':'Studio light. '+DUPLICATE,
                   'shots':[{'action':'Stand.\n'+PLACEHOLDER+'\nLook up.','wardrobe':'Blue coat.'}]*2}
                parts=s.image_prompts_for_selection(item,model,t,s.SAMPLE_TEMPLATE,{},personal=personal).split('\n\n')
                assert len(parts)==2
                for part in parts:
                    assert part.lower().count('bottom caption')==int(enabled)
                    assert ('Bottom caption: "'+item['person']) in part if enabled else 'bottom caption' not in part.lower()
                    assert 'Stale identity' not in part and '[Performer Name]' not in part
                    assert 'Stand.' in part and 'Look up.' in part and 'Blue coat.' in part


def test_saved_template_preview_export_queue_and_manual_override(installation):
    c,p,root,_=installation
    _mock_fork(root);p.queue_bridge.api_session=FakeWanSession()
    key=_create_public_selection(c)
    s=importlib.import_module('cb_under_test.app.server')
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','scene':1}
    template={**s.SAMPLE_TEMPLATE,'video_count':1,'video1_action':'Stand.\n'+PLACEHOLDER+'\n'+DUPLICATE}
    for enabled in (True,False,True):
        template['include_caption']=enabled
        assert c.put(API+'/prompts/template',json=template).status_code==200
        assert c.get(API+'/prompts/template').json()==template
        preview=c.post(API+'/generator/preview',json=task)
        assert preview.status_code==200,preview.text
        for text in (preview.json()['prompt'],c.get(API+'/prompts/export?model=h3_video').text):
            assert text.lower().count('bottom caption')==int(enabled)
            assert '[Performer Name]' not in text
    r=c.post(API+'/generator/submit',json=task);assert r.status_code==200,r.text
    assert _await_job(c,r.json()['id'])['state']=='completed'
    assert p.queue_bridge.api_session.submitted[-1]['prompt'].lower().count('bottom caption')==1
    custom='My deliberate final edit.\n'+PLACEHOLDER+'\n'+DUPLICATE
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':custom}).status_code==200
    assert c.put(API+'/prompts/template',json={**template,'include_caption':False}).status_code==200
    assert s.build_live_cast_prompt(s.CastTask(**task))[0]==custom


def test_caption_normalization_preserves_unrelated_scene_text(installation):
    s=importlib.import_module('cb_under_test.app.server')
    text='A sign reads "Open". '+PLACEHOLDER+' The subject smiles.\nAn unrelated subtitle reads "Hello".'
    assert s.generated_caption_parts([text],False,'Ada Test')==['A sign reads "Open". The subject smiles.\nAn unrelated subtitle reads "Hello".']
