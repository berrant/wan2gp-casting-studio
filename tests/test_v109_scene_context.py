"""Production-specific scene defaults, strict adaptation matching and review safety."""
import importlib
import json
from contextlib import contextmanager
from test_native_plugin import installation
from test_rc1213_appearance import app, run
from test_persona_power import tab
API='/casting-studio/api'

def test_source_scope_and_descriptive_clauses(installation):
    mod=importlib.import_module('cb_under_test.app.scene_context')
    raw=('Example (2023) is a 2023 television series.\n'
         'Captain Mira wears a charcoal flight jacket with bronze buckles and dark trousers.\n'
         'Captain Mira is stationed aboard a weathered starship with steel corridors and amber console lights.\n'
         'The series is set in a desert city with sandstone buildings.\n'
         'Filming took place in a modern town.\n'
         'Other Person wears a red dress.')
    def fake(_client,params):
        assert 'Example (2023 TV series)' in params['titles']
        return {'query':{'pages':[{'title':'Example (2023 TV series)','extract':raw},{'title':'Example (2011 film)','extract':raw}]}}
    result=mod.research_scene(None,fake,'Captain Mira','Example',2023)
    assert 'charcoal flight jacket' in result['wardrobe']
    assert 'weathered starship' in result['setting'] and 'amber console lights' in result['setting']
    assert 'modern town' not in result['setting'] and 'red dress' not in result['wardrobe']
    assert '2023_TV_series' in result['source']
    assert not mod.research_scene(None,lambda *_:{'query':{'pages':[{'title':'Example (2011 film)','extract':raw}]}},'Captain Mira','Example',2023)['setting']
    assert not mod.extract_scene('The actress wears a red coat. The series was filmed in a city.','Captain Mira','Example')['wardrobe']

def test_automatic_profiles_override_precedence_and_backup(installation,monkeypatch):
    c,*_=installation;s=importlib.import_module('cb_under_test.app.server')
    item={'key':'','person':'Ada Test','character':'Captain Mira','production':'Example Series','year':2023,'refmod':'Ada_Test_H3.safetensors'}
    assert c.put(API+'/choices',json=item).status_code==200
    item=next(x for x in c.get(API+'/choices').json() if x['character']=='Captain Mira');key=item['key']
    calls=[]
    def research(*args):
        calls.append(args[-1]);return {'wardrobe':'Charcoal flight jacket, bronze buckles and black trousers.','setting':'A weathered starship bridge with amber consoles and exposed metal beams.','source':'https://en.wikipedia.org/wiki/Example_Series'}
    monkeypatch.setattr(s,'research_scene',research)
    params={'choice_key':key,'auto':True}
    result=c.get(API+'/characters/scene',params=params);assert result.status_code==200,result.text
    assert result.json()['setting'].startswith('A weathered starship')
    assert c.get(API+'/characters/scene',params=params).status_code==200 and calls==[2023]
    for opt in s.MODEL_OPTIONS:
        if opt['kind']=='video':text=s.prompt_for_selection(item,s.SAMPLE_TEMPLATE)
        else:text=s.image_prompts_for_selection(item,opt['id'],{},s.SAMPLE_TEMPLATE,{})
        assert 'Charcoal flight jacket' in text and 'amber consoles' in text
        assert 'A cinematic setting appropriate' not in text
    custom=s.prompt_for_selection(item,{**s.SAMPLE_TEMPLATE,'wardrobe':'My custom coat.','setting':'My custom room.'})
    assert 'My custom coat.' in custom and 'My custom room.' in custom and 'amber consoles' not in custom
    still=s.image_prompts_for_selection(item,'flux2_dev',{'image_count':1,'shots':[{'wardrobe':'My custom coat.','setting':'My custom room.'}]},s.SAMPLE_TEMPLATE,{})
    assert 'My custom coat.' in still and 'My custom room.' in still and 'amber consoles' not in still
    assert not s.scene_profile({**item,'year':2011})
    assert 'amber consoles' not in s.prompt_for_selection({**item,'year':2011},s.SAMPLE_TEMPLATE)
    revision=result.json()['revision']
    assert c.put(API+'/characters/scene',json={'choice_key':key,'wardrobe':'Reviewed jacket.','setting':'Reviewed bridge.','expected_revision':revision}).status_code==200
    assert c.put(API+'/characters/scene',json={'choice_key':key,'wardrobe':'Stale jacket.','setting':'Stale bridge.','expected_revision':revision}).status_code==409
    assert c.get(API+'/characters/scene',params={**params,'refresh':True}).json()['setting']=='Reviewed bridge.' and calls==[2023]
    backup=c.get(API+'/settings/prompt-backup').json();assert len(backup['portrayal_scenes'])==1
    assert c.post(API+'/settings/prompt-backup',json=backup).status_code==200
    backup['portrayal_scenes']={'invalid':{}};assert c.post(API+'/settings/prompt-backup',json=backup).status_code==422
    assert c.get(API+'/characters/scene',params={'choice_key':'missing'}).status_code==400
    assert c.delete(API+'/characters/scene',params={'choice_key':key}).status_code==200
    assert 'Reviewed bridge.' not in s.prompt_for_selection(item,s.SAMPLE_TEMPLATE)
    assert calls==[2023]

def test_scene_vision_drafts_are_separate_and_reviewed(app):
    c,p,s,b,n,roles=app
    @contextmanager
    def session(state,engine,stop):
        def analyze(label,images):
            assert label.startswith('[Casting Studio scene context] ')
            return json.dumps({'wardrobe':'Blue flight jacket and black boots.','setting':'A hangar with metal rafters and yellow floor stripes.'})
        yield analyze
    n.session=session
    response=c.post(p+'/appearance/batch',json={'engine':'3','mode':'scene','selections':roles[:1]});assert response.status_code==200,response.text
    job=response.json()['id'];result=run(app,job)['results'][0];assert result['state']=='review' and result['mode']=='scene'
    assert s.exact_identity_snapshot(result['profile_key']) is None
    assert c.post(p+'/appearance/batch/'+job+'/approve',json={'index':0,'traits':'Should not save'}).status_code==409
    r=c.post(p+'/appearance/batch/'+job+'/approve-scene',json={'index':0,'wardrobe':result['wardrobe'],'setting':result['setting']});assert r.status_code==200,r.text
    assert s.exact_identity_snapshot(result['profile_key']) is None
    assert c.get(p+'/characters/scene',params={'choice_key':roles[0]['choice_key']}).json()['setting'].startswith('A hangar')
    assert c.post(p+'/appearance/batch/'+job+'/approve-scene',json={'index':0,'wardrobe':'Other'}).status_code==409

def test_editor_displays_automatic_context_and_keeps_global_marker(tab):
    tab.evaluate('''()=>{choices=[{key:'a',person:'Ada Test',character:'Captain Mira',production:'Example Series',year:2023}];const old=fetch;window.sceneWrites=[];window.fetch=async(u,o={})=>{if(String(u).startsWith('api/characters/scene')){if(o.method==='PUT')sceneWrites.push(JSON.parse(o.body));return {ok:true,json:async()=>({role:{character:'Captain Mira',year:2023},wardrobe:'Charcoal jacket.',setting:'Starship bridge with amber consoles.',source:'https://en.wikipedia.org/wiki/Example'})}}return old(u,o)};loadSceneContext('videoSceneContext','a');$('editorModal').classList.add('open');}''')
    tab.wait_for_function("$('videoSceneContext').textContent.includes('Captain Mira')")
    assert tab.locator('#videoSceneContext textarea').nth(0).input_value()=='Charcoal jacket.'
    assert tab.locator('#videoSceneContext textarea').nth(1).input_value()=='Starship bridge with amber consoles.'
    tab.evaluate("fillEditor({wardrobe:autoWardrobeText,setting:autoSettingText,video_count:2})")
    assert 'Automatic' in tab.locator('#tpl_wardrobe').input_value()
    assert tab.evaluate('currentTemplate().wardrobe===autoWardrobeText')
    assert tab.evaluate('currentTemplate().setting===autoSettingText')
