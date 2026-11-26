from importlib import import_module
from test_native_plugin import installation
from test_v102_film_search import lead
from types import SimpleNamespace
API='/casting-studio/api'

def test_remake_artwork(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    for name,year in [('The Thing',1982),('The Thing (2011 film)',2011)]:
        assert c.post(API+'/productions',json={'name':name,'kind':'film','year':year}).status_code==200
    def wiki(client,params):
        if params['action']=='query':
            title=params.get('titles','');year=2011 if '2011' in title else 1982
            return {'query':{'pages':[{'title':f'The Thing ({year} film)','thumbnail':{'source':f'https://example.org/{year}.jpg'}}]}}
        year=2011 if '2011' in params['page'] else 1982
        return {'parse':{'text':lead(year,'The Thing')}}
    monkeypatch.setattr(s,'wiki_api',wiki)
    result=c.get(API+'/productions/artwork',params={'name':'The Thing (2011 film)'}).json()
    assert result['image']=='https://example.org/2011.jpg',result

def test_tv_import_never_merges_same_title_different_years(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    class Client:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kw):
            year=1990 if '/1' in url else 2020
            data=([{'person':{'name':'Example Actor'},'character':{'name':f'Role {year}'}}] if url.endswith('/cast') else {'name':'Example Series','premiered':f'{year}-01-01'})
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
    monkeypatch.setattr(s.httpx,'Client',Client)
    for id in (1,2):assert c.post(API+f'/productions/import-tvmaze/{id}').status_code==200
    with s.connect() as db: rows=db.execute('SELECT name,year,kind FROM productions').fetchall()
    assert len(rows)==2,rows
    old=c.get(API+'/productions/cast',params={'production':'Example Series'}).json()['cast']
    assert len(old)==1 and old[0]['year']==1990,old

def test_bulk_cast_rejects_wrong_year(installation):
    c,*_=installation
    assert c.post(API+'/productions',json={'name':'Example Film','kind':'film','year':1982}).status_code==200
    body={'production':'Example Film','members':[{'production':'Example Film','actress':'Example Actor','character':'Role','year':2011}]}
    assert c.post(API+'/productions/cast/bulk',json=body).status_code==409
    assert c.get(API+'/productions/cast',params={'production':'Example Film'}).json()['cast']==[]

def test_tv_suggestions_respect_qualified_title(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server');calls=[]
    shows=[{'id':1,'name':'Example Series','premiered':'1990-01-01','image':{'medium':'https://example.org/1990.jpg'}},{'id':2,'name':'Example Series','premiered':'2020-01-01','image':{'medium':'https://example.org/2020.jpg'}}]
    class Client:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kw):
            calls.append((url,kw))
            if 'search/shows' in url:
                assert kw['params']['q']=='Example Series'
                data=[{'show':x} for x in shows]
            else:
                i=int(url.split('/')[4]);show=shows[i-1]
                data=[{'person':{'name':'Example Actor'},'character':{'name':f'Role {show["premiered"][:4]}'}}] if url.endswith('/cast') else show
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
    monkeypatch.setattr(s.httpx,'Client',Client)
    d=c.get(API+'/productions/cast-suggestions',params={'production':'Example Series'}).json()
    assert not d['candidates'] and 'Multiple series' in d['note'],d
    for i in (1,2,2):assert c.post(API+f'/productions/import-tvmaze/{i}').status_code==200
    for title,year in [('Example Series',1990),('Example Series (2020 TV series)',2020)]:
        d=c.get(API+'/productions/cast-suggestions',params={'production':title}).json()
        assert d['year']==year and [r['character'] for r in d['candidates']]==[f'Role {year}'],d
        assert d['candidates'][0]['already_added']
        assert c.get(API+'/productions/artwork',params={'name':title}).json()['image']==f'https://example.org/{year}.jpg'
        assert s.portrayal_production_label({'production':title,'year':year})==f'Example Series ({year})'
    assert c.post(API+'/personal',json={'name':'Synthetic Private','consent':False}).status_code==200
    before=len(calls)
    for endpoint,params in [('artwork',{'name':'Synthetic Private (2020 TV series)'}),('cast-suggestions',{'production':'Synthetic Private (2020 TV series)'})]:
        assert c.get(API+'/productions/'+endpoint,params=params).status_code==403
    assert len(calls)==before


def test_cast_year_validation_atomic_and_legacy(installation):
    c,*_=installation
    title='Example Film'
    assert c.post(API+'/productions',json={'name':title,'kind':'film'}).status_code==200
    def role(year,person='Example Actor'):
        return {'production':title,'actress':person,'character':'Role','year':year}
    assert c.post(API+'/productions/cast',json=role(1982)).status_code==200
    assert c.post(API+'/productions/cast',json=role(2011,'Other Actor')).status_code==409
    assert c.post(API+'/productions/cast/bulk',json={'production':title,'members':[role(1982,'Other Actor'),role(2011,'Third Actor')]}).status_code==409
    assert c.post(API+'/productions/cast/bulk',json={'production':title,'members':[role(-1)]}).status_code==400
    assert [x['actress'] for x in c.get(API+'/productions/cast',params={'production':title}).json()['cast']]==['Example Actor']
    assert c.post(API+'/productions/cast',json=role(None,'Manual Actor')).status_code==200
    assert c.post(API+'/productions/cast',json={**role(2011),'production':'Example Film (1982 film)'}).status_code==409
