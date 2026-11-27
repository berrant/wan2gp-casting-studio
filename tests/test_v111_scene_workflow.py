"""Scene drafting, approval, and queue-pass recovery without generation submission."""
import json
from contextlib import contextmanager
from test_rc1213_appearance import app, run
from test_native_plugin import installation
from test_persona_power import tab


def test_text_only_scene_drafts_require_review_and_preserve_identity(app):
    c,p,s,b,n,roles=app
    selected=[{**r,'image_ids':[]} for r in roles]
    assert c.post(p+'/appearance/batch',json={'engine':'3','selections':selected}).status_code==422
    key=selected[0]['choice_key']
    assert c.put(p+'/characters/scene',json={'choice_key':key,'wardrobe':'Earlier reviewed coat','setting':'Earlier bridge'}).status_code==200
    calls=[]
    @contextmanager
    def session(state,engine,stop):
        def analyze(label,images):
            assert not images
            calls.append(label)
            return json.dumps({'wardrobe':'New coat with brass buckles.','setting':'Named starship bridge with amber lights.'})
        yield analyze
    n.session=session
    response=c.post(p+'/appearance/batch',json={'engine':'3','mode':'scene','selections':selected});assert response.status_code==200,response.text
    job=response.json()['id'];drafts=run(app,job)['results'];assert len(drafts)==2 and all(r['state']=='review' for r in drafts)
    assert 'Earlier reviewed coat' in calls[0] and 'Saved descriptive clues' in calls[0]
    assert b.summary()['mode']=='scene'
    assert c.get(p+'/characters/scene',params={'choice_key':key}).json()['wardrobe']=='Earlier reviewed coat'
    assert s.exact_identity_snapshot(drafts[0]['profile_key']) is None
    assert c.post(p+'/appearance/batch/'+job+'/approve-scene',json={'index':0,'wardrobe':drafts[0]['wardrobe'],'setting':drafts[0]['setting']}).status_code==200
    profile=c.get(p+'/characters/scene',params={'choice_key':key}).json()
    assert 'production knowledge, no photos' in profile['source'] and 'amber lights' in profile['setting']
    item=next(x for x in c.get(p+'/choices').json() if x['key']==key)
    assert 'amber lights' in s.prompt_for_selection(item,s.SAMPLE_TEMPLATE)
    assert 'amber lights' in s.image_prompts_for_selection(item,'flux2_dev',{},s.SAMPLE_TEMPLATE,{})
    assert s.exact_identity_snapshot(drafts[0]['profile_key']) is None
    second=selected[1]['choice_key']
    assert c.put(p+'/characters/scene',json={'choice_key':second,'wardrobe':'New manual edit','setting':'Other location'}).status_code==200
    assert c.post(p+'/appearance/batch/'+job+'/approve-scene',json={'index':1,'wardrobe':'Stale AI coat','setting':'Stale AI location'}).status_code==409
    assert c.get(p+'/characters/scene',params={'choice_key':second}).json()['wardrobe']=='New manual edit'


def test_scene_browser_drafts_without_photos_and_protects_reviewed_profiles(tab):
    tab.evaluate('''()=>{const orig=fetch;const rows=[{key:'a',person:'Ada',character:'Mira',production:'Example',year:2023},{key:'b',person:'Bea',character:'Nova',production:'Example',year:2024}];window.posts=[];window.fetch=async(u,o={})=>{let d;const url=String(u);if(o.method==='POST')posts.push(url);if(url==='api/appearance/options')d={ready:true,default:'3',models:[{id:'3',label:'Local AI',backend:'quanto_int8'}]};else if(url==='api/choices')d=rows;else if(url.startsWith('api/appearance/references?')){const k=new URLSearchParams(url.split('?')[1]).get('choice_key');d={role:{...rows.find(r=>r.key===k),choice_key:k,label:k},photos:[],scene:k==='b'?{custom:true,wardrobe:'Reviewed coat',setting:'Reviewed bridge'}:{}};}else return orig(u,o);return {ok:true,json:async()=>d,text:async()=>JSON.stringify(d)};};openAppearance({scope:'batch',sceneContext:true,choiceKeys:['a','b'],label:'Scenes'});}''')
    tab.wait_for_function("appearanceLoaded.length===2&&!appearanceBusy")
    assert tab.locator('#appearanceStart').is_enabled()
    assert tab.locator('#appearanceStart').inner_text()=='Draft 1 portrayal scene with AI (0 reference photos)'
    assert tab.evaluate('appearanceLoaded.map(r=>r.enabled.checked)')==[True,False]
    assert tab.evaluate('posts')==[]
    tab.evaluate("appearanceLoaded[1].enabled.checked=true;appearanceControls()")
    assert 'Draft 2 portrayal scenes' in tab.locator('#appearanceStart').inner_text()


def test_bulk_approval_partial_failure_keeps_draft_and_refreshes_once(tab):
    tab.evaluate('''()=>{window.saved=[];window.previewed=[];window.posts=[];window.refreshSceneConsumers=async()=>{};window.refreshScenePromptPreview=async k=>previewed.push(k);const orig=fetch;window.fetch=async(u,o={})=>{if(String(u).endsWith('/approve-scene')){const data=JSON.parse(o.body);posts.push(data);if(data.index===1)return {ok:false,status:409,text:async()=> 'Conflict',json:async()=>({detail:'Conflict'})};saved.push(data.index);return {ok:true,json:async()=>({saved:true})};}return orig(u,o)};appearanceJob='testjob';appearanceCurrentState='completed';$('appearanceModal').classList.add('open');renderAppearanceResults({id:'testjob',results:['a','b','c'].map((k,i)=>({index:i,state:'review',mode:'scene',choice_key:k,label:k,wardrobe:'Coat '+k,setting:'Bridge '+k,image_ids:[]}))});}''')
    tab.locator('#appearanceResults textarea').nth(3).fill('Edited B location')
    tab.once('dialog',lambda d:d.accept());tab.get_by_role('button',name='Approve & save all reviewed scenes').click()
    tab.wait_for_function("$('appearanceStatus').textContent.includes('2/3 scenes saved')")
    assert tab.evaluate('saved')==[0,2] and tab.evaluate('previewed')==[['a','c']]
    assert tab.locator('#appearanceResults textarea').nth(3).input_value()=='Edited B location'
    assert tab.locator('#appearanceResults textarea').nth(3).is_enabled()
    assert tab.locator('#appearanceResults textarea').nth(0).is_disabled()
    assert tab.evaluate('posts.length')==3


def test_queue_pass_history_is_not_live_queue_count(tab):
    tab.evaluate('''()=>{choices=[{key:'a',person:'Ada',character:'Mira',production:'Example'},{key:'b',person:'Bea',character:'Nova',production:'Example'}];$('generatorChoice').replaceChildren(new Option('A','a'),new Option('B','b'));$('generatorScope').value='all';generatorPassSet().add('a');generatorUpdateSubmitEnabled();}''')
    assert '1 previously staged (not live queue count)' in tab.locator('#generatorScopeStatus').inner_text()
    assert tab.evaluate("!$('generatorNextPending').hidden")
    tab.evaluate("window.generatorChoiceChanged=()=>{};selectNextPending()")
    assert tab.locator('#generatorChoice').input_value()=='b'
    assert tab.evaluate('generatorRemainingKeys()')==['b']


def test_ai_can_pause_remaining_public_lookups_without_losing_scope(tab):
    from test_v110_global_scene_scope import SETUP
    tab.evaluate(SETUP)
    tab.evaluate("window.holdKey='b';window.openAppearance=async r=>window.batchSceneRequest=r;openEditor()")
    tab.wait_for_function('!!window.holdScene')
    tab.get_by_role('button',name='Analyze all portrayals with AI').click()
    assert tab.evaluate('typeof window.batchSceneRequest')=='undefined'
    tab.evaluate("window.holdKey=null;window.holdScene()")
    tab.wait_for_function('!!window.batchSceneRequest')
    assert tab.evaluate('batchSceneRequest.choiceKeys')==['a','b','c']
    assert tab.evaluate('sceneCalls')==['a','b']
    assert 'public lookup paused for AI' in tab.locator('#videoSceneContext').inner_text()
    tab.evaluate("refreshSceneConsumers('c')")
    tab.wait_for_function("$('videoSceneContext').querySelectorAll('textarea').length===6")
    assert tab.evaluate('sceneCalls')==['a','b','c'] and tab.evaluate('otherPosts')==[]


def test_scene_reference_eligibility_matches_staging(app):
    c,p,s,b,n,roles=app
    key=roles[0]['choice_key']
    assert c.get(p+'/appearance/references',params={'choice_key':key,'mode':'scene'}).status_code==200
    assert c.put(p+'/profiles/categories',json={'name':'Ada Test','categories':['Video game character']}).status_code==200
    r=c.get(p+'/appearance/references',params={'choice_key':key,'mode':'scene'})
    assert r.status_code==400 and 'Game-world' in r.json()['detail']
    assert c.post(p+'/appearance/batch',json={'engine':'3','mode':'scene','selections':[{'choice_key':key,'image_ids':[]}]}).status_code==400
    assert n.loads==0


def test_scene_approval_reloads_actual_open_generator_preview_without_queue(tab):
    tab.evaluate('''()=>{choices=[{key:'a',person:'Ada',character:'Mira',production:'Example',year:2023,refmod:'Ada.safetensors'}];window.savedScene={wardrobe:'Old coat',setting:'Old location'};window.generationPosts=[];const orig=fetch;const ok=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});window.fetch=async(u,o={})=>{const url=String(u);if(url.startsWith('api/characters/scene?'))return ok({...savedScene,role:choices[0],custom:true,revision:'test'});if(url==='api/generator/preview')return ok({review_token:'test-preview',prompt:savedScene.wardrobe+' / '+savedScene.setting,refmod_filename:'Ada.safetensors'});if(url.endsWith('/approve-scene')){const d=JSON.parse(o.body);savedScene={wardrobe:d.wardrobe,setting:d.setting};return ok({saved:true,...savedScene});}if(url.startsWith('api/generator/')&&o.method==='POST')generationPosts.push(url);return orig(u,o);};openGenerator();}''')
    tab.wait_for_function("$('generatorPreview').value==='Old coat / Old location'&&!$('generatorSubmit').disabled")
    tab.evaluate("appearanceJob='job';appearanceCurrentState='completed';$('appearanceModal').classList.add('open');renderAppearanceResults({id:'job',results:[{index:0,state:'review',mode:'scene',choice_key:'a',label:'Mira',wardrobe:'Reviewed flight jacket',setting:'Weathered bridge with amber lights',image_ids:[]}]})")
    tab.once('dialog',lambda d:d.accept());tab.get_by_role('button',name='Approve & save scene',exact=True).click()
    tab.wait_for_function("$('generatorPreview').value==='Reviewed flight jacket / Weathered bridge with amber lights'&&appearanceApprovalPending===0")
    assert tab.locator('#generatorSceneContext textarea').nth(0).input_value()=='Reviewed flight jacket'
    assert tab.locator('#generatorSceneContext textarea').nth(1).input_value()=='Weathered bridge with amber lights'
    assert tab.evaluate('generationPosts')==[]
