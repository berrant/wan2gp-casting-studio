"""Direct People registration without a production or installed RefMod."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_native_plugin import installation
from test_rc2_jackhammer import server
from test_dev55_browser import page
API='/casting-studio/api'


def test_add_public_person_without_role_or_model(installation,monkeypatch):
    c,*_=installation;s=server()
    def no_network(*a,**k):raise AssertionError('Unexpected online research')
    monkeypatch.setattr(s,'fetch_credits',no_network)
    url=API+'/people/library'
    r=c.post(url,json={'name':'  Synthetic   Performer  '})
    assert r.status_code==200 and r.json()=={'name':'Synthetic Performer','created':True}
    r=c.post(url,json={'name':'synthetic-performer'})
    assert r.json()=={'name':'Synthetic Performer','created':False}
    assert [p['name'] for p in c.get(url).json()['people']].count('Synthetic Performer')==1
    assert not any(p['name']=='Synthetic Performer' for p in c.get(API+'/catalog').json()['people'])
    assert c.get(API+'/productions').json()==[]
    assert c.get(API+'/choices').json()==[]
    assert c.get(API+'/discovery/people',params={'q':'Synthetic Performer'}).json()[0]['name']=='Synthetic Performer'
    assert c.put(API+'/profiles/categories',json={'name':'Synthetic Performer','categories':['Actor']}).status_code==200
    assert c.post(url,json={'name':'Synthetic Performer'}).json()['created'] is False
    assert c.get(API+'/profiles/categories').json()['Synthetic Performer']==['Actor']


def test_invalid_private_and_concurrent_add(installation):
    c,*_=installation;url=API+'/people/library'
    assert c.post(API+'/personal',json={'name':'Private Person'}).status_code==200
    assert c.post(url,json={'name':'Private Person'}).status_code==403
    assert all(p['name']!='Private Person' for p in c.get(url).json()['people'])
    for name in ('  ','123','\x00Person'):
        assert c.post(url,json={'name':name}).status_code==400
    with ThreadPoolExecutor(max_workers=4) as pool:
        rs=list(pool.map(lambda _:c.post(url,json={'name':'Synthetic Actor'}).json(),range(8)))
    assert sum(r['created'] for r in rs)==1


def test_people_add_and_reference_collection(page):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.peopleRequests=[];window.savedPeople=[];window.failPersonSave=false;window.fetch=async(u,o={})=>{if(String(u).startsWith('api/people/library')){peopleRequests.push([String(u),o.method||'GET']);if(o.method==='POST'){if(failPersonSave)return {ok:false,json:async()=>({detail:'Simulated failure'})};const name=JSON.parse(o.body).name;savedPeople=[{name,type:'Unclassified'}];return {ok:true,json:async()=>({name,created:true})}}return {ok:true,json:async()=>({people:savedPeople,roles:[]})}}return old(u,o)};showTab('performers')}''')
    assert tab.locator('#addPublicPersonForm').is_hidden()
    tab.locator('#search').fill('Synthetic Performer')
    tab.locator('#addPublicPersonButton').click()
    assert tab.locator('#newPublicPersonName').input_value()=='Synthetic Performer'
    tab.evaluate('failPersonSave=true');tab.locator('#savePublicPersonButton').click()
    tab.wait_for_function("$('peopleLibraryStatus').textContent.includes('Simulated failure')")
    assert tab.locator('#newPublicPersonName').input_value()=='Synthetic Performer'
    tab.evaluate('failPersonSave=false');tab.locator('#savePublicPersonButton').click()
    tab.wait_for_function("$('list').textContent.includes('Synthetic Performer') && $('peopleLibraryStatus').textContent.includes('Performer added')")
    assert tab.locator('#filter').input_value()=='library'
    assert 'RefMod missing' in tab.locator('#list').inner_text()
    assert tab.locator('#list').get_by_role('button',name='Collect reference photos',exact=True).count()==1
    assert tab.locator('#list').get_by_role('button',name='+ As themselves',exact=True).count()==0
    tab.locator('#filter').select_option('all');assert tab.locator('#list article').count()==0
    tab.locator('#filter').select_option('missing');tab.wait_for_function("$('list').textContent.includes('Synthetic Performer')")
    tab.evaluate("window.openPhoto=(...args)=>window.collected=args")
    tab.locator('#list').get_by_role('button',name='Collect reference photos',exact=True).click()
    assert tab.evaluate('collected')==['Synthetic Performer',None,'actress',True]
    assert not errors,errors


@pytest.mark.parametrize("change",["search","clear","navigate"])
def test_pending_add_does_not_hijack_new_search(page,change):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.savedPeople=[];window.fetch=async(u,o={})=>{if(String(u)==='api/people/library'){if(o.method==='POST'){const name=JSON.parse(o.body).name;return new Promise(resolve=>{window.finishPersonSave=()=>{savedPeople=[{name,type:'Unclassified'}];resolve({ok:true,json:async()=>({name,created:true})})}})}return {ok:true,json:async()=>({people:savedPeople,roles:[]})}}return old(u,o)};showTab('performers')}''')
    tab.locator('#search').fill('Synthetic Performer')
    tab.locator('#addPublicPersonButton').click()
    tab.locator('#savePublicPersonButton').click()
    tab.wait_for_function('typeof finishPersonSave === "function"')
    if change=='clear':
        tab.locator('#browseSection').get_by_role('button',name='Clear',exact=True).click()
    elif change=='navigate':
        tab.evaluate("showTab('productions');showTab('performers')")
    else:
        tab.locator('#search').fill('Other')
    tab.evaluate('finishPersonSave()')
    tab.wait_for_function('!peopleAddBusy')
    assert tab.locator('#search').input_value()=={'search':'Other','clear':'','navigate':'Synthetic Performer'}[change]
    assert tab.locator('#filter').input_value()=='all'
    assert 'Performer added to saved people' in tab.locator('#peopleLibraryStatus').inner_text()
    assert tab.locator('#addPublicPersonForm').is_hidden()
    assert not errors,errors


def test_registered_person_survives_new_db_connection_and_role_research(installation,monkeypatch):
    c,*_=installation;s=server()
    name='Synthetic Performer';url=API+'/people/library'
    assert c.post(url,json={'name':name}).status_code==200
    monkeypatch.setattr(s,'fetch_credits',lambda n:([{'production':'Example Film','character':'Example Role','year':2024}],[]))
    assert c.get(API+'/discovery/credits',params={'name':name,'online':True}).status_code==200
    with s.connect() as db:
        assert db.execute('SELECT name FROM profile_categories WHERE name=?',(name,)).fetchone()==(name,)
    d=c.get(url).json()
    assert any(p['name']==name for p in d['people'])
    assert any(r['actress']==name and r['production']=='Example Film' and r['character']=='Example Role' for r in d['roles'])
    assert c.post(url,json={'name':name}).json()['created'] is False
