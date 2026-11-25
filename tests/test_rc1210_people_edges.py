"""Adversarial People library integration regressions using synthetic identities."""
from test_native_plugin import installation
from test_rc2_jackhammer import server
from test_dev55_browser import page
API='/casting-studio/api'


def test_explicit_save_survives_removing_installed_model(installation):
    c,_,root,_=installation
    assert c.post(API+'/people/library',json={'name':'Ada Test'}).status_code==200
    (root/'refmods/minimax_h3/celebs/Ada_Test_H3.safetensors').unlink()
    assert c.post(API+'/catalog/rescan').status_code==200
    assert 'Ada Test' in [p['name'] for p in c.get(API+'/people/library').json()['people']]


def test_saved_people_marker_without_refmod(installation):
    c,*_=installation
    assert c.post(API+'/people/library',json={'name':'Synthetic Performer'}).status_code==200
    assert c.put(API+'/profiles/markers',json={'name':'Synthetic Performer','adult':True}).status_code==200
    assert c.get(API+'/profiles/markers').json()['Synthetic Performer'] is True
    assert c.put(API+'/profiles/markers',json={'name':'Synthetic Performer','adult':False}).status_code==200
    assert c.put(API+'/profiles/markers',json={'name':'Unknown Performer','adult':True}).status_code==404


def test_fictional_saved_person_cannot_trigger_human_credit_search(installation,monkeypatch):
    c,*_=installation;s=server();calls=[]
    name='Synthetic Game Character'
    assert c.post(API+'/people/library',json={'name':name}).status_code==200
    assert c.put(API+'/profiles/categories',json={'name':name,'categories':['Video game character']}).status_code==200
    monkeypatch.setattr(s,'fetch_credits',lambda name:(calls.append(name) or [],[]))
    assert c.get(API+'/discovery/credits',params={'name':name}).status_code==200
    assert c.get(API+'/discovery/credits',params={'name':name,'online':True}).status_code==400
    assert calls==[]


def test_fictional_saved_person_no_human_profile_link(page):
    tab,errors=page
    tab.evaluate('''() => {showTab('performers');$('filter').value='library';peopleLibraryData={people:[{name:'Synthetic Game Character',type:'Video game character',categories:['Video game character']}],roles:[]};$('search').value='Synthetic Game Character';render()}''')
    assert tab.locator('#list article').count()==1
    assert tab.locator('#list .profilelink').count()==0
    assert tab.locator('#list').get_by_role('button',name='Refresh roles').count()==0
    assert not errors,errors


def test_saved_person_identity_correction_keeps_classification(installation):
    c,*_=installation
    assert c.post(API+'/people/library',json={'name':'Synthetic Performer'}).status_code==200
    assert c.put(API+'/profiles/categories',json={'name':'Synthetic Performer','categories':['Actor']}).status_code==200
    assert c.put(API+'/identities',json={'original_name':'Synthetic Performer','display_name':'Corrected Performer'}).status_code==200
    p=c.get(API+'/people/library').json()['people']
    assert [v['categories'] for v in p if v['name']=='Corrected Performer']==[['Actor']]
    assert not any(v['name']=='Synthetic Performer' for v in p)


def test_saved_identity_repeat_correction_collision_and_private_guard(installation):
    c,*_=installation
    for name in ('Synthetic Performer','Separate Performer'):
        assert c.post(API+'/people/library',json={'name':name}).status_code==200
    assert c.post(API+'/personal',json={'name':'Private Synthetic'}).status_code==200
    def rename(old,new):return c.put(API+'/identities',json={'original_name':old,'display_name':new})
    assert rename('Synthetic Performer','Separate Performer').status_code==409
    assert rename('Synthetic Performer','Private Synthetic').status_code==403
    assert c.put(API+'/profiles/categories',json={'name':'Synthetic Performer','categories':['Actor']}).status_code==200
    assert c.put(API+'/profiles/markers',json={'name':'Synthetic Performer','adult':True}).status_code==200
    assert rename('Synthetic Performer','Corrected Performer').status_code==200
    assert rename('Corrected Performer','Final Performer').status_code==200
    assert c.post(API+'/people/library',json={'name':'Synthetic Performer'}).json()=={'name':'Final Performer','created':False}
    assert c.put(API+'/profiles/categories',json={'name':'Corrected Performer','categories':['Musician']}).status_code==200
    assert c.get(API+'/profiles/markers').json()['Final Performer'] is True
    assert c.put(API+'/profiles/markers',json={'name':'Final Performer','adult':False}).status_code==200
    assert c.get(API+'/profiles/markers').json()=={}
    people=c.get(API+'/people/library').json()['people']
    assert {p['name']:p['categories'] for p in people}['Final Performer']==['Musician']
    assert not any(p['name'] in ('Synthetic Performer','Corrected Performer','Private Synthetic') for p in people)


def test_saved_person_symbol_survives_alias_and_clear(installation):
    c,*_=installation
    assert c.post(API+'/people/library',json={'name':'Synthetic Performer'}).status_code==200
    assert c.put(API+'/profiles/gender',json={'name':'Synthetic Performer','symbol':'♀'}).status_code==200
    assert c.put(API+'/identities',json={'original_name':'Synthetic Performer','display_name':'Corrected Performer'}).status_code==200
    assert c.get(API+'/profiles/gender').json()=={'correctedperformer':'♀'}
    assert c.put(API+'/profiles/gender',json={'name':'Corrected Performer','symbol':''}).status_code==200
    assert c.get(API+'/profiles/gender').json()=={}


def test_identity_correction_updates_current_library_search(page):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.savedName='Synthetic Performer';window.prompt=()=> 'Corrected Performer';window.fetch=async(u,o={})=>{const json=d=>({ok:true,json:async()=>d});if(u==='api/people/library')return json({people:[{name:savedName,type:'Unclassified'}],roles:[]});if(u==='api/identities'&&o.method==='PUT'){savedName='Corrected Performer';return json({display_name:savedName})}if(u==='api/identities')return json({known:{},overrides:{syntheticperformer:savedName}});return old(u,o)};showTab('performers');$('filter').value='library';$('search').value=savedName;loadPeopleLibrary()}''')
    tab.wait_for_function("$('list').textContent.includes('Synthetic Performer')")
    tab.locator('#list').get_by_role('button',name='Edit identity').click()
    tab.wait_for_function("$('list').textContent.includes('Corrected Performer')")
    assert tab.locator('#search').input_value()=='Corrected Performer'
    assert not errors,errors


def test_invalid_display_name_must_not_remove_saved_identity(installation):
    c,*_=installation
    assert c.post(API+'/people/library',json={'name':'Synthetic Performer'}).status_code==200
    assert c.put(API+'/identities',json={'original_name':'Synthetic Performer','display_name':'..'}).status_code==400
    assert any(p['name']=='Synthetic Performer' for p in c.get(API+'/people/library').json()['people'])

def test_direct_human_profile_lookup_blocks_fictional_installed(installation,monkeypatch):
    c,*_=installation;s=server();calls=[]
    assert c.put(API+'/profiles/categories',json={'name':'Ada Test','categories':['Video game character']}).status_code==200
    def no_network(*a,**k):calls.append(True);raise RuntimeError('blocked synthetic network')
    monkeypatch.setattr(s.httpx,'Client',no_network)
    assert c.get(API+'/profiles/link',params={'name':'Ada Test'}).status_code==400
    assert calls==[]

def test_flux_identity_edit_uses_current_profile_name(page):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.identityPayload=null;window.prompt=()=> 'Corrected Performer';window.fetch=async(u,o={})=>{if(u==='api/identities'&&o.method==='PUT'){identityPayload=JSON.parse(o.body);return new Promise(()=>{})}return old(u,o)};catalog={...catalog,models:[{name:'Synthetic Flux Performer',path:'flux2/celebs/Synthetic_Flux_Performer_flux.safetensors',family:'flux2'}],people:[{name:'Synthetic Flux Performer',type:'Unclassified'}],roles:[]};performerIndexSnapshot=null;showTab('performers');$('search').value='Synthetic Flux Performer';render()}''')
    tab.locator('#list').get_by_role('button',name='Edit identity').click()
    tab.wait_for_function('identityPayload!==null')
    assert tab.evaluate('identityPayload.original_name')=='Synthetic Flux Performer'
    assert not errors,errors
