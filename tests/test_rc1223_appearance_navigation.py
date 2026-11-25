"""A previous review cannot substitute a different requested portrayal."""
from test_dev55_browser import page

MOCK = '''()=>{window.referenceRequests=[];const role=key=>({key,person:'Ada Test',character:key==='a'?'First Alien':'Second Alien',production:'Example',year:2023,profile_key:key+'2023',label:key==='a'?'First Alien (2023)':'Second Alien (2023)'});window.roleForTest=role;choices=[role('a'),role('b')];const orig=fetch;window.fetch=async(u,o={})=>{const url=String(u);const json=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});if(url==='api/appearance/options')return json({ready:true,default:'3',models:[{id:'3',label:'Qwen 4B',backend:'int8'}]});if(url==='api/choices')return json([role('a'),role('b')]);if(url.startsWith('api/appearance/references?')){const key=new URLSearchParams(url.split('?')[1]).get('choice_key');referenceRequests.push(key);return json({role:role(key),photos:[{id:'portrait',label:'Portrait '+key,url:'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',dated:true}]});}if(url.startsWith('api/appearance/batch/old/approve'))return json({saved:true});return orig(u,o);};cardIdentityRole=role('a');cardIdentityKey='a';cardIdentityOriginal='';$('cardIdentityTraits').value='';$('cardIdentityModal').classList.add('open');cardIdentityControls();}'''


def prepare(page,state='review'):
    tab,errors=page
    tab.evaluate(MOCK)
    tab.locator('#cardIdentityAI').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    tab.evaluate('''state=>{appearanceJob='old';appearanceCurrentState='completed';renderAppearanceResults({id:'old',results:[{...roleForTest('a'),choice_key:'a',index:0,state,traits:'First character draft'}]});}''',state)
    tab.keyboard.press('Escape')
    tab.evaluate("cardIdentityRole=roleForTest('b');cardIdentityKey='b';$('cardIdentityTitle').textContent=cardIdentityRole.label;cardIdentityControls()")
    return tab,errors


def test_approved_review_does_not_open_wrong_character(page):
    tab,errors=prepare(page,'approved')
    tab.locator('#cardIdentityAI').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    assert tab.evaluate('appearanceLoaded[0].key')=='b'
    assert not tab.locator('#appearanceRequest').is_visible()
    assert tab.locator('#appearanceResults textarea').count()==0
    assert not errors,errors


def test_pending_review_names_target_and_preserves_exact_requested_role(page):
    tab,errors=prepare(page)
    tab.locator('#cardIdentityAI').click()
    assert tab.locator('#appearanceRequestedLabel').inner_text().endswith('Second Alien (2023)')
    assert tab.locator('#appearanceStart').is_disabled()
    assert tab.locator('#appearanceResults textarea').input_value()=='First character draft'
    tab.once('dialog',lambda d:d.dismiss())
    tab.locator('#appearanceOpenRequested').click()
    assert tab.locator('#appearanceResults textarea').input_value()=='First character draft'
    tab.evaluate("cardIdentityRole=roleForTest('a');cardIdentityKey='a'")
    tab.once('dialog',lambda d:d.accept())
    tab.locator('#appearanceOpenRequested').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    assert tab.evaluate('appearanceLoaded[0].key')=='b'
    assert tab.evaluate('referenceRequests')==['a','b']
    assert not errors,errors


def test_running_review_names_requested_target_and_blocks_switch(page):
    tab,errors=prepare(page)
    tab.evaluate("appearanceCurrentState='running';$('appearanceResults').replaceChildren()")
    tab.locator('#cardIdentityAI').click()
    assert 'Second Alien' in tab.locator('#appearanceRequestedLabel').inner_text()
    assert tab.locator('#appearanceOpenRequested').is_disabled()
    assert tab.locator('#appearanceStart').is_disabled()
    tab.evaluate("appearanceCurrentState='completed';renderAppearanceResults({id:'old',results:[{...roleForTest('a'),choice_key:'a',index:0,state:'approved',traits:'Saved'}]});appearanceControls()")
    tab.locator('#appearanceOpenRequested').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    assert tab.evaluate('appearanceLoaded[0].key')=='b'
    assert not errors,errors


def test_approval_clears_previous_review_blocker(page):
    tab,errors=prepare(page)
    tab.evaluate("cardIdentityRole=roleForTest('a');cardIdentityKey='a';$('appearanceModal').classList.add('open')")
    tab.once('dialog',lambda d:d.accept())
    tab.get_by_role('button',name='Approve & save appearance').click()
    tab.wait_for_function("$('appearanceResults').querySelector('textarea').disabled && appearanceApprovalPending===0")
    tab.keyboard.press('Escape')
    tab.evaluate("cardIdentityRole=roleForTest('b');cardIdentityKey='b';cardIdentityOriginal='';$('cardIdentityTraits').value='';cardIdentityControls()")
    tab.locator('#cardIdentityAI').click()
    tab.wait_for_function('!appearanceBusy && appearanceLoaded.length===1')
    assert tab.evaluate('appearanceLoaded[0].key')=='b'
    assert not tab.locator('#appearanceRequest').is_visible()
    assert not errors,errors


def test_image_and_video_capture_requested_key_before_async_load(page):
    tab,errors=page
    tab.evaluate(MOCK)
    tab.evaluate('''async()=>{for(const [scope,id] of [['image','imageIdentityChoice'],['generator','generatorChoice']]){const select=$(id);select.replaceChildren(new Option('First','a'),new Option('Second','b'));select.value='a';const pending=openAppearance(scope);select.value='b';await pending;if(appearanceLoaded.length!==1||appearanceLoaded[0].key!=='a')throw Error('Wrong role for '+scope);}}''')
    assert tab.evaluate('referenceRequests')==['a','a']
    assert not errors,errors
