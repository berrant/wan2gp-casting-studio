"""Character-first Option D across actual prompt renderers and saved overrides."""
import importlib
from test_native_plugin import installation, _create_public_selection, _mock_fork, FakeWanSession
API='/casting-studio/api'

def test_character_first_for_all_models(installation):
    c,*_=installation
    s=importlib.import_module('cb_under_test.app.server')
    for item, traits in [
        ({'person':'Mary Elizabeth Winstead','character':'Hera Syndulla','production':'Ahsoka','year':2023,'refmod':'Hera.safetensors'}, 'Green pigmentation across all exposed skin, aquamarine irises, two biological Twi’lek lekku integrated into the scalp.'),
        ({'person':'Rosario Dawson','character':'Ahsoka Tano','production':'Ahsoka','year':2023,'refmod':'Ahsoka.safetensors'}, 'Orange pigmentation, white facial markings, blue-and-white biological montrals and lekku forming the complete head silhouette.')]:
        assert c.put(API+'/characters/identity',json={**{k:item[k] for k in ('person','character','production','year')},'traits':traits}).status_code==200
        for opt in s.MODEL_OPTIONS:
            if opt['kind']=='video':
                outputs=s.prompt_for_selection(item,{**s.SAMPLE_TEMPLATE,'video_count':4,'wardrobe':'Custom jacket.'})
            else:
                tpl=s.image_template_normalized({'image_count':2,'shots':[{'action':'Stand in the cockpit.','wardrobe':'Custom jacket.'}]*2,'visual_style':s.LEGACY_IMAGE_VISUAL_STYLE})
                outputs=s.image_prompts_for_selection(item,opt['id'],tpl,s.SAMPLE_TEMPLATE,{})
            for scene in outputs.split('\n\n'):
                body=scene.split('\n',1)[1]
                assert item['character']+' as seen in Ahsoka (2023)' in body
                assert item['person'] not in body and 'as portrayed by' not in body
                assert 'facial identity only' in body and 'all images provided' in body
                assert traits in body and body.count(traits)==1
                assert '<Subject 2>' not in body and '<Picture ' not in body
                assert 'natural skin texture' not in body
                assert 'Custom jacket.' in body.split('wardrobe_description:',1)[1]
                assert 'Custom jacket.' not in body.split('wardrobe_description:',1)[0]

def test_saved_style_and_final_override_preserved(installation):
    c,p,root,_=installation
    s=importlib.import_module('cb_under_test.app.server')
    _mock_fork(root);p.queue_bridge.api_session=FakeWanSession()
    key=_create_public_selection(c)
    task={'choice_key':key,'model':'h3_image','model_type':'h3_image','scene':1}
    custom='My exact finished prompt, including performer names.'
    assert c.put(API+'/generator/prompt-edit',json={'task':task,'prompt':custom}).status_code==200
    assert s.build_live_cast_prompt(s.CastTask(**task))[0]==custom
    item={'person':'Ada Test','character':'Pilot','production':'Example','year':2025}
    style='My personally selected natural skin texture and lighting.'
    data={'image_count':1,'shots':[{'action':'Read a book.','wardrobe':'My coat.'}],'visual_style':style}
    assert c.put(API+'/prompts/image-template',params={'model':'flux2_klein9'},json=data).status_code==200
    t=c.get(API+'/prompts/image-template',params={'model':'flux2_klein9'}).json()
    assert t['visual_style']==style
    text=s.image_prompts_for_selection(item,'flux2_klein9',t,s.SAMPLE_TEMPLATE,{})
    assert style in text and 'Read a book.' in text and 'My coat.' in text
