"""Film title resolution using synthetic Wiki responses."""
from importlib import import_module
import pytest
from test_native_plugin import installation
API='/casting-studio/api'

def lead(year,original,alias=''):
    return f'<table class="infobox"><tr><th>Directed by</th><td>Example Director</td></tr><tr><th>Release date</th><td>May 25, {year}</td></tr><tr><th>Running time</th><td>121 minutes</td></tr></table><p><b>{original}</b> (later retitled <b>{alias}</b>) is a film.</p>'

@pytest.fixture
def wiki(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server');calls=[]
    pages=[{'title':'Star Wars','pageid':1},{'title':'Star Wars (film)','pageid':2},{'title':'Star Wars: The Empire Strikes Back','pageid':3}]
    casts='<ul><li>Mark Hamill as <a>Luke Skywalker</a>: Description.</li><li>Carrie Fisher as <a>Princess Leia Organa</a>: Description.</li><li>David Prowse / James Earl Jones (voice; uncredited)<sup class="reference">[12]</sup> as Darth Vader: Description.</li></ul>'
    def fake(client,params):
        calls.append(params.copy())
        if params['action']=='query':
            if 'titles' in params:return {'query':{'pages':[{'title':'Missing','missing':True}]}}
            return {'query':{'pages':pages}}
        title=params['page']
        if params.get('section')==0:
            text={'Star Wars':'<table class="infobox"><tr><th>Creator</th><td>Example</td></tr></table><p><b>Star Wars</b> is a franchise.</p>','Star Wars (film)':lead(1977,'Star Wars','Star Wars: Episode IV – A New Hope'),'Star Wars: The Empire Strikes Back':lead(1980,'Star Wars: The Empire Strikes Back')}[title]
            return {'parse':{'text':text}}
        assert title=='Star Wars (film)'
        if params['prop']=='sections':return {'parse':{'sections':[{'line':'Cast','index':'2'}]}}
        return {'parse':{'text':casts}}
    monkeypatch.setattr(s,'wiki_api',fake)
    return c,s,calls,pages

@pytest.mark.parametrize('title',['star wars a new hope','Star Wars: Episode IV – A New Hope (1977)','star wars a new hope 1977','Star Wars (film)','Star Wars (1977 film)'])
def test_title_alias_and_year(wiki,title):
    c,s,calls,_=wiki
    d=c.get(API+'/productions/cast-suggestions',params={'production':title,'kind':'film'}).json()
    assert d['matched_show']=='Star Wars (film)' and d['year']==1977,d
    assert {(x['actress'],x['character']) for x in d['candidates']}=={('Mark Hamill','Luke Skywalker'),('Carrie Fisher','Princess Leia Organa'),('David Prowse','Darth Vader'),('James Earl Jones','Darth Vader')}
    assert all(x['year']==1977 and x['source_url'].endswith('Star_Wars_%28film%29') for x in d['candidates'])
    assert any(x.get('generator')=='search' for x in calls)

@pytest.mark.parametrize('title',['star wars a new hope 1999','Star Wars: Episode VI – A New Hope','Star Wars a new hope returns'])
def test_wrong_year_episode_or_title_not_guessed(wiki,title):
    c,s,calls,_=wiki
    d=c.get(API+'/productions/cast-suggestions',params={'production':title,'kind':'film'}).json()
    assert d['candidates']==[] and d['matched_show'] is None,d
    assert not any(x.get('prop')=='sections' for x in calls)

def test_explicit_redirect(wiki,monkeypatch):
    c,s,calls,pages=wiki;original=s.wiki_api
    def redirect(client,params):
        if 'titles' in params:return {'query':{'pages':[pages[1]],'redirects':[{'from':'A New Hope','to':'Star Wars (film)'}]}}
        return original(client,params)
    monkeypatch.setattr(s,'wiki_api',redirect)
    d=s.film_cast_lookup('A New Hope')
    assert d['year']==1977 and len(d['cast'])==4
    assert not any(x.get('generator')=='search' for x in calls)

def test_retry_after_failure_and_saved_film_mode(wiki,monkeypatch):
    c,s,calls,_=wiki;original=s.wiki_api
    q={'production':'star wars a new hope','kind':'film'}
    monkeypatch.setattr(s,'wiki_api',lambda *a:{'error':{'code':'temporary'}})
    d=c.get(API+'/productions/cast-suggestions',params=q).json()
    assert 'unavailable' in d['note'] and not d['candidates']
    monkeypatch.setattr(s,'wiki_api',original)
    d=c.get(API+'/productions/cast-suggestions',params=q).json();assert d['candidates']
    assert c.post(API+'/productions',json={'name':q['production'],'kind':'film','year':1977,'preserve_existing':True}).status_code==200
    assert c.get(API+'/productions/cast-suggestions',params={'production':q['production']}).json()['year']==1977
    assert not c.get(API+'/productions/cast-suggestions',params={'production':q['production']+' 1999','kind':'film'}).json()['candidates']
    assert c.post(API+'/productions',json={'name':q['production'],'kind':'film','year':1999,'preserve_existing':True}).status_code==409
    assert c.post(API+'/productions',json={'name':q['production'].upper(),'kind':'film','preserve_existing':True}).json()['name']==q['production']
    with s.connect() as db:assert db.execute('SELECT year,kind FROM productions').fetchone()==(1977,'film')

def test_private_alias_base_blocked_before_network(wiki):
    c,s,calls,_=wiki
    assert c.post(API+'/personal',json={'name':'Synthetic Private','consent':False}).status_code==200
    assert c.get(API+'/productions/cast-suggestions',params={'production':'Synthetic Private (1977 film)','kind':'film'}).status_code==403
    assert not calls

def test_ambiguous_films_do_not_select_first(wiki,monkeypatch):
    c,s,calls,_=wiki
    def fake(client,params):
        if params['action']=='query':return {'query':{'pages':[{'title':'Example (1980 film)'},{'title':'Example (2000 film)'}]}}
        assert params['section']==0
        return {'parse':{'text':lead(1980 if '1980' in params['page'] else 2000,'Example')}}
    monkeypatch.setattr(s,'wiki_api',fake)
    d=s.film_cast_lookup('Example')
    assert not d['cast'] and 'Multiple matching films' in d['note']


def test_film_button_uses_result_once_and_keeps_year():
    import shutil
    from pathlib import Path
    from playwright.sync_api import sync_playwright
    from test_generator_session_browser import setup_js
    html=(Path(__file__).resolve().parents[1]/'app/index.html').read_text()
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=shutil.which('chromium'),args=['--no-sandbox','--disable-dev-shm-usage'])
        page=b.new_page();page.evaluate(setup_js)
        page.evaluate('''() => {const old=fetch;window.filmCalls=[];window.created=[];window.fetch=async(u,o)=>{const p=String(u);let d;if(p.startsWith('api/productions/cast-suggestions?')){filmCalls.push(p);d={year:1977,matched_show:'Star Wars (film)',source:'Wikipedia film credits',source_url:'https://en.wikipedia.org/wiki/Star_Wars_(film)',candidates:[{actress:'Carrie Fisher',character:'Princess Leia Organa',year:1977}]}}else if(p==='api/productions'&&o?.method==='POST'){created.push(JSON.parse(o.body));d={name:'star wars a new hope'}}else if(p.startsWith('api/productions/cast?')){d={production:'star wars a new hope',cast:[]}}else if(p.startsWith('api/productions?')){d=[]}else return old(u,o);return {ok:true,json:async()=>d};};}''')
        page.set_content(html,wait_until='domcontentloaded');page.wait_for_function('choices.length===2')
        page.evaluate("showTab('productions',true);$('productionQuery').value='star wars a new hope';searchFilmProduction()")
        page.wait_for_function("$('castPickerList').textContent.includes('Carrie Fisher')",timeout=5000)
        assert page.evaluate('filmCalls')==['api/productions/cast-suggestions?kind=film&production=star%20wars%20a%20new%20hope']
        assert page.evaluate('created')==[{'name':'star wars a new hope','kind':'film','year':1977,'preserve_existing':True}]
        assert 'Star Wars (film)' in page.locator('#castPickerSource').text_content()
        b.close()
