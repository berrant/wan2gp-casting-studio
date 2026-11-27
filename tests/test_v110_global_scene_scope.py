"""Global scene scope must work on selected roles before generation is queued."""
from test_persona_power import tab

SETUP = '''()=>{
 choices=[{key:'a',person:'Ada',character:'Captain Mira',production:'Example',year:2023},{key:'b',person:'Bea',character:'Pilot Nova',production:'Example',year:2011},{key:'c',person:'Cora',character:'Officer Vega',production:'Other',year:2024},{key:'p',person:'Personal',personal_id:'p',character:'Private',production:'Private'}];
 window.sceneCalls=[];window.sceneWrites=[];window.otherPosts=[];window.holdScene=null;window.protectedKeys=[];
 const old=fetch;window.fetch=async(u,o={})=>{u=String(u);if(u.startsWith('api/characters/scene')){
  const k=new URLSearchParams(u.split('?')[1]).get('choice_key');if(o.method==='PUT'){sceneWrites.push(JSON.parse(o.body));return {ok:true,json:async()=>({revision:'next'})}}
  sceneCalls.push(k);if(window.holdKey===k)await new Promise(r=>window.holdScene=r);
  const c=choices.find(c=>c.key===k);return {ok:true,json:async()=>({role:c,wardrobe:'Coat '+k,setting:'Location '+k,custom:protectedKeys.includes(k),revision:'old'})};
 }if(o.method==='POST')otherPosts.push(u);return old(u,o)};
}'''

def test_global_scope_loads_all_separately_without_queue_and_bulk_actions(tab):
    tab.evaluate(SETUP)
    tab.evaluate('openEditor()')
    tab.wait_for_function("$('videoSceneContext').textContent.includes('3 portrayals checked')")
    assert tab.evaluate('sceneCalls')==['a','b','c']
    assert tab.locator('#videoSceneContext textarea').count()==6
    assert [x.input_value() for x in tab.locator('#videoSceneContext textarea').all()]==['Coat a','Location a','Coat b','Location b','Coat c','Location c']
    assert tab.evaluate('otherPosts')==[]
    tab.locator('#videoSceneContext textarea').nth(0).fill('Reviewed A')
    tab.locator('#videoSceneContext textarea').nth(3).fill('Reviewed B')
    tab.get_by_role('button',name='Save edited portrayal scenes').click()
    tab.wait_for_function("sceneWrites.length===2 && $('videoSceneContext').textContent.includes('2 edited portrayals saved')")
    assert [(x['choice_key'],x['wardrobe'],x['setting']) for x in tab.evaluate('sceneWrites')]==[('a','Reviewed A','Location a'),('b','Coat b','Reviewed B')]
    tab.get_by_role('button',name='Refresh public details for all').click()
    tab.wait_for_function("$('videoSceneContext').textContent.includes('2 protected or edited')")
    assert tab.evaluate('sceneCalls')==['a','b','c','c']
    assert tab.evaluate('otherPosts')==[]
    tab.evaluate('window.openAppearance=async r=>window.batchSceneRequest=r')
    tab.get_by_role('button',name='Analyze all portrayals with AI').click()
    assert tab.evaluate('batchSceneRequest.choiceKeys')==['a','b','c']
    assert tab.evaluate('batchSceneRequest.sceneContext') is True
    assert tab.evaluate('otherPosts')==[]


def test_switch_scope_stops_old_load_and_retains_drafts(tab):
    tab.evaluate(SETUP)
    tab.evaluate("window.holdKey='b';openEditor()")
    tab.wait_for_function('!!window.holdScene')
    tab.locator('#videoSceneContext textarea').first.fill('Unsaved A')
    tab.locator('#editScope').select_option('c')
    tab.wait_for_function("$('videoSceneContext').querySelector('textarea')?.value==='Coat c'")
    tab.evaluate("window.holdKey=null;window.holdScene()")
    assert tab.locator('#videoSceneContext textarea').count()==2
    assert tab.evaluate('sceneCalls')==['a','b','c']
    tab.locator('#editScope').select_option('global')
    tab.wait_for_function("$('videoSceneContext').textContent.includes('3 portrayals checked')")
    assert tab.locator('#videoSceneContext textarea').first.input_value()=='Unsaved A'
    tab.evaluate('closeEditor()')
    tab.evaluate('openEditor()')
    tab.wait_for_function("$('videoSceneContext').textContent.includes('3 portrayals checked')")
    assert tab.locator('#videoSceneContext textarea').first.input_value()=='Unsaved A'
    assert tab.evaluate('otherPosts')==[]
