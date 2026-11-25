"""Impatient user and intermittent host regressions."""
from test_dev55_browser import page

MOCK_VISION = '''()=>{const orig=fetch;window.fetch=async(u,o={})=>{const url=String(u);const json=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});if(url==='api/appearance/options')return json({ready:true,default:'3',models:[{id:'4',label:'Qwen 9B',backend:'gguf'}]});if(url==='api/choices')return json([{key:'a',person:'Ada Test',character:'Alien',production:'Example',year:2023}]);if(url.startsWith('api/appearance/references?'))return json({role:{label:'Alien in Example (2023)'},photos:[{id:'1',url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',label:'Reference',dated:true}]});return orig(u,o);};openAppearance('batch');}'''

def test_vision_missing_preferred_engine_requires_clear_selection(page):
    tab,errors=page;tab.evaluate(MOCK_VISION)
    tab.wait_for_function("!appearanceBusy && appearanceLoaded.length===1")
    assert tab.locator('#appearanceEngine').input_value()==''
    assert 'Preferred vision engine unavailable' in tab.locator('#appearanceStatus').inner_text()
    assert tab.locator('#appearanceStart').is_disabled()
    tab.locator('#appearanceEngine').select_option('4')
    assert tab.locator('#appearanceStart').is_enabled()
    assert not errors,errors


def test_vision_empty_selection_cannot_start(page):
    tab,errors=page;tab.evaluate(MOCK_VISION)
    tab.wait_for_function("!appearanceBusy && appearanceLoaded.length===1")
    tab.locator('#appearanceEngine').select_option('4')
    tab.locator('#appearanceRoles input[type=checkbox]').last.uncheck()
    assert tab.locator('#appearanceStart').is_disabled()
    tab.locator('#appearanceRoles input[type=checkbox]').last.check()
    assert tab.locator('#appearanceStart').is_enabled()
    tab.locator('#appearanceRoles input[type=checkbox]').first.uncheck()
    assert tab.locator('#appearanceStart').is_disabled()
    assert not errors,errors


def test_explicit_portrayal_year_never_uses_undated_choice(page):
    tab,errors=page
    val=tab.evaluate('''async()=>{choices=[{key:key('Ada Test',{character:'Alien',production:'Example'}),person:'Ada Test',character:'Alien',production:'Example'}];let seen;const orig=uxRequest;window.uxRequest=async(url,opts)=>{if(url.startsWith('api/appearance/references?')){seen=new URLSearchParams(url.split('?')[1]).get('choice_key');return {role:{person:'Ada Test',character:'Alien',production:'Example',year:2024,label:'Alien'}};}if(url.startsWith('api/characters/identity?'))return {traits:'',source:'none'};return orig(url,opts);};await openCardIdentity('Ada Test',{character:'Alien',production:'Example',year:2024});return seen;}''')
    assert val.startswith('catalog:') and '2024' in val
    assert not errors,errors


def test_generation_monitor_recovers_transient_status_failure(page):
    tab,errors=page
    result=tab.evaluate('''async()=>{const orig=fetch;let calls=0;window.fetch=async(url,o)=>{if(String(url).includes('/jobs/polish-job')){calls++;if(calls===1)throw Error('connection interrupted');return {ok:true,json:async()=>({id:'polish-job',state:'completed',message:'recovered'})};}return orig(url,o);};trackGeneratorJob('polish-job');await pollGenerator();return {scheduled:!!generatorPoll,calls,status:$('generatorStatus').textContent};}''')
    assert result['scheduled'],result
    tab.wait_for_function("$('generatorStatus').textContent.includes('recovered')",timeout=6000)
    assert not errors,errors


def test_previous_appearance_review_is_explicit_when_opened_for_another_role(page):
    tab,errors=page
    result=tab.evaluate('''async()=>{appearanceJob='old';appearanceCurrentState='completed';appearanceOrigin='batch';$('appearanceResults').append(document.createElement('section'));cardIdentityKey='new';cardIdentityRole={character:'New Alien',person:'New Performer',production:'New Series',year:2024};await openAppearance('card');return $('appearanceStatus').textContent;}''')
    assert 'previous' in result.lower() and 'review' in result.lower(),result
    assert tab.locator('#appearanceStart').is_disabled()
    assert not errors,errors


def test_out_of_order_monitor_responses_do_not_resurrect_running_status(page):
    tab,errors=page
    result=tab.evaluate('''async()=>{const orig=fetch;let pending=[];window.fetch=(url,o)=>String(url).includes('/jobs/polish-job')?new Promise(r=>pending.push(r)):orig(url,o);trackGeneratorJob('polish-job');const a=pollGenerator(),b=pollGenerator();pending[1]({ok:true,json:async()=>({id:'polish-job',state:'completed',message:'new result'})});await b;pending[0]({ok:true,json:async()=>({id:'polish-job',state:'running',message:'old result'})});await a;return {status:$('generatorStatus').textContent,timer:!!generatorPoll};}''')
    assert 'new result' in result['status'] and not result['timer'],result
    assert not errors,errors

def test_monitor_stops_retrying_missing_job(page):
    tab,errors=page
    result=tab.evaluate('''async()=>{const orig=fetch;window.fetch=(u,o)=>String(u).includes('/jobs/polish-job')?Promise.resolve({ok:false,status:404,text:async()=>"Missing"}):orig(u,o);trackGeneratorJob('polish-job');await pollGenerator();return {status:$('generatorStatus').textContent,timer:!!generatorPoll};}''')
    assert 'no longer available' in result['status'] and not result['timer'],result
    assert not errors,errors
