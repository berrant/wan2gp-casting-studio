"""Acknowledgment is local, explicit and versioned; it does not prove consent."""
import pytest
from importlib import import_module
from test_native_plugin import installation
from test_dev55_browser import page
API='/casting-studio/api'

@pytest.mark.parametrize('installation',[False],indirect=True)
def test_first_use_is_enforced_on_api_and_does_not_block_data_management(installation):
    c,plugin,*_=installation
    policy=c.get(API+'/responsible-use').json()
    assert policy['acknowledged'] is False and len(policy['rules'])==4
    for route in ['/generator/submit','/generator/batch/submit','/appearance/batch','/workshop/create','/workshop/decompile','/prefetch/start','/reference-images','/reference-images/upload','/images/upload','/settings/conversion/start','/choices/conversion/prepare','/generator/jobs/test/retry-failed','/personal/test/portrait-generate','/personal/test/portrait']:
        # An invalid payload may also be rejected first; use valid JSON object.
        r=c.post(API+route,json={})
        assert r.status_code==403, (route,r.status_code,r.text)
    for route in ['/prompts/export','/images/search','/images/auto']:
        assert c.get(API+route).status_code==403
    assert c.get(API+'/personal').status_code==200
    uid=c.post(API+'/personal',json={'name':'Synthetic Person','consent':False}).json()['id']
    assert c.delete(API+'/personal/'+uid).status_code==200
    for value in [False,'true',1,None]:
        assert c.post(API+'/responsible-use',json={'version':policy['version'],'accepted':value}).status_code in (400,422)
    assert c.post(API+'/responsible-use',json={'version':'old','accepted':True}).status_code==409
    assert not c.get(API+'/responsible-use').json()['acknowledged']
    assert c.post(API+'/responsible-use',json={'version':policy['version'],'accepted':True}).json()['acknowledged']
    assert c.get(API+'/prompts/export').status_code==200
    server=import_module(plugin.__class__.__module__.rsplit('.',1)[0]+'.app.server')
    server.startup()
    assert c.get(API+'/responsible-use').json()['acknowledged']
    assert 'responsible_use' not in c.get(API+'/settings/prompt-backup').text
    with server.connect() as db:db.execute("UPDATE responsible_use SET version='previous'")
    assert not c.get(API+'/responsible-use').json()['acknowledged']
    assert c.get(API+'/prompts/export').status_code==403


def test_changed_personal_identity_requires_fresh_explicit_confirmation(installation):
    c,*_=installation
    body={'name':'Synthetic Person','consent':True,'h3_refmod':'personal/Private_Test_H3.safetensors'}
    uid=c.post(API+'/personal',json=body).json()['id'];url=API+'/personal/'+uid
    assert c.put(url,json={**body,'notes':'Updated notes'}).status_code==200
    change={**body,'name':'Different Synthetic Person'}
    assert c.put(url,json=change).status_code==409
    assert c.get(API+'/personal').json()[0]['name']==body['name']
    assert c.put(url,json={**change,'confirm_consent_scope':'true'}).status_code==422
    assert c.put(url,json={**change,'confirm_consent_scope':True}).status_code==200
    assert c.put(url,json={**change,'h3_refmod':''}).status_code==409
    assert c.put(url,json={**change,'h3_refmod':'','consent':False}).status_code==200
    assert not c.get(API+'/personal').json()[0]['consent']


def test_responsible_use_dialog_requires_explicit_check_and_successful_save(page):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.policyWrites=[];window.policyFail=true;
      window.fetch=async(u,o={})=>{if(u==='api/responsible-use'){
        if(o.method==='POST'){policyWrites.push(JSON.parse(o.body));if(policyFail)return {ok:false};}
        return {ok:true,json:async()=>({version:'test-v1',acknowledged:o.method==='POST',rules:['Respect consent and rights.']})};
      }return old(u,o)};}''')
    tab.locator('#responsibleUseOpen').click()
    modal=tab.locator('#responsibleUseModal')
    modal.get_by_text('Respect consent and rights.').wait_for()
    assert modal.get_by_role('button',name='Acknowledge',exact=True).is_disabled()
    modal.get_by_role('checkbox').check()
    modal.get_by_role('button',name='Acknowledge',exact=True).click()
    modal.get_by_text('Acknowledgment not saved.',exact=False).wait_for()
    assert modal.is_visible()
    tab.evaluate('policyFail=false')
    modal.get_by_role('button',name='Acknowledge',exact=True).click()
    modal.wait_for(state='hidden')
    assert tab.evaluate('policyWrites')==[{'version':'test-v1','accepted':True}]*2
    assert not errors,errors
