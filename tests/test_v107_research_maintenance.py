"""Explicit research controls; isolated synthetic identities and mocked providers."""
import csv,io,time,json
from test_native_plugin import installation
from test_rc2_jackhammer import API,server
from test_dev55_browser import page
from playwright.sync_api import expect


def test_role_modes_cooldowns_and_csv(installation,monkeypatch):
    c,_,root,_=installation;s=server();now=int(time.time())
    for name in ['Beta_Test','Gamma_Test']:(root/'refmods/minimax_h3/celebs'/f'{name}_H3.safetensors').write_bytes(b'test')
    c.post(API+'/catalog/rescan')
    with s.connect() as db:
        db.executemany('INSERT INTO credit_refresh VALUES (?,?,?,?,?)', [('adatest',now,3,'ok',''),('betatest',now,0,'error','=1+1'),('privatetest',now,0,'error','private sentinel')])
    calls=[]
    monkeypatch.setattr(s,'launch_credit_sync',lambda names,**kw:(calls.append((names,kw)) or True))
    assert c.post(API+'/credits/refresh',json={}).json()['skipped']['cooldown']==2
    assert calls[-1][0]==['Gamma Test']
    assert c.post(API+'/credits/refresh',json={'retry_errors':True}).json()['pending']==1
    assert calls[-1][0]==['Beta Test']
    assert c.post(API+'/credits/refresh',json={'force':True}).json()['pending']==3
    assert set(calls[-1][0])=={'Ada Test','Beta Test','Gamma Test'}
    assert c.post(API+'/credits/refresh',json={'force':True,'retry_errors':True}).status_code==400
    rows=list(csv.DictReader(io.StringIO(c.get(API+'/credits/errors.csv').text)))
    assert len(rows)==1 and rows[0]['name']=='Beta Test' and rows[0]['detail']=="'=1+1"
    assert '3 discovered screen credits' in c.get(API+'/enrichment/review.csv').text


def test_classification_unclassified_and_persistent_runs(installation,monkeypatch):
    c,_,root,_=installation;s=server();now=int(time.time())
    for name in ['Beta_Test','Gamma_Test','Delta_Test']:(root/'refmods/minimax_h3/celebs'/f'{name}_H3.safetensors').write_bytes(b'test')
    c.post(API+'/catalog/rescan')
    with s.connect() as db:
        db.execute('INSERT INTO profile_categories VALUES (?,?)',('Ada Test','["Model"]'))
        db.execute('INSERT INTO profile_categories VALUES (?,?)',('Delta Test','["Video game character"]'))
        db.execute('INSERT INTO public_profiles(name_key,status,checked) VALUES (?,?,?)',('betatest','unmatched',now))
    calls=[]
    def profile(name):
        calls.append(name);return {'label':name,'qid':'Q123','imdb_id':'','categories':['Actor'],'status':'matched'}
    monkeypatch.setattr(s,'wikidata_profile',profile);monkeypatch.setattr(s.ENRICH_STOP,'wait',lambda _:False)
    s.enrichment_job('unclassified')
    assert calls==['Gamma Test']
    state=c.get(API+'/enrichment/status').json();run=state['runs'][0]
    assert run['status']=='completed' and run['done']==1 and run['skipped']=={'excluded':1,'outside_scope':1,'cooldown':1,'not_failed':0,'became_ineligible':0}
    s.ENRICH_STATE.update(total=0,done=0)
    assert c.get(API+'/enrichment/status').json()['runs'][0]==run
    s.enrichment_job('force')
    assert set(calls)=={'Ada Test','Beta Test','Gamma Test'}
    with s.connect() as db:
        assert db.execute("SELECT categories FROM profile_categories WHERE name='Ada Test'").fetchone()[0]=='["Model"]'
    s.research_snapshot('classification','all','interrupted-fixture',{'done':2,'total':5},'running',now+100)
    assert c.get(API+'/enrichment/status').json()['runs'][0]['status']=='interrupted'


def test_short_stage_requires_reviewed_stable_identity(installation,monkeypatch):
    c,_,root,_=installation;s=server()
    (root/'refmods/minimax_h3/celebs/V_H3.safetensors').write_bytes(b'test');c.post(API+'/catalog/rescan')
    def claim(value):return {'mainsnak':{'datavalue':{'value':value}}}
    entity={'labels':{'en':{'value':'Synthetic Performer'}},'aliases':{'en':[{'value':'V'}]},'claims':{'P31':[claim({'id':'Q5'})],'P106':[claim({'id':'Q33999'})]},'sitelinks':{'enwiki':{'title':'Synthetic Performer'}}}
    requests=[]
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    class Client:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def get(self,url,params):
            requests.append((url,params))
            if 'wikidata' in url:return Response({'entities':{'Q123':entity}})
            return Response({'parse':{'title':'Synthetic Performer','text':'<h2>Filmography</h2><table class="wikitable"><tr><th>Year</th><th>Title</th><th>Role</th></tr><tr><td>2020</td><td>Example Film</td><td>Named Role</td></tr></table>'}})
    monkeypatch.setattr(s.httpx,'Client',Client)
    import pytest
    with pytest.raises(ValueError,match='reviewed Wikidata'):s.researched_credits('V')
    assert not requests
    assert c.put(API+'/research/stage-identity',json={'person':'V','qid':'Q123','confirmed':False}).status_code==400
    assert not requests
    assert c.put(API+'/research/stage-identity',json={'person':'V','qid':'Q456','confirmed':True}).status_code==400
    assert c.put(API+'/research/stage-identity',json={'person':'V','qid':'Q123','confirmed':True}).status_code==200
    assert s.sync_one_public_person('V')['added']==1
    assert s.wikidata_profile('V')['qid']=='Q123'
    assert requests[-2][1]['page']=='Synthetic Performer'
    assert c.get(API+'/discovery/credits',params={'name':'V'}).status_code==200


def test_new_tables_are_additive_and_history_bounded(installation):
    c,*_=installation;s=server()
    with s.connect() as db:
        db.execute("INSERT INTO profile_categories VALUES ('Ada Test','[\"Model\"]')")
        db.execute('DROP TABLE research_runs');db.execute('DROP TABLE short_stage_identities')
        prior={name:db.execute('SELECT * FROM '+name).fetchall() for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for i in range(105):s.research_snapshot('credits','due',str(i),{'total':i,'done':i,'last':'Private sentinel'},'completed',i)
    with s.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0]==100
        assert all(db.execute('SELECT * FROM '+table).fetchall()==rows for table,rows in prior.items())
    runs=c.get(API+'/credits/status').json()['runs'];assert len(runs)==10 and runs[0]['done']==104
    assert 'Private sentinel' not in json.dumps(runs)


def test_browser_maintenance_controls(page):
    tab,errors=page
    tab.evaluate('''() => {const old=fetch;window.researchRequests=[];window.confirm=()=>true;window.fetch=async(u,o={})=>{if(o.method==='POST'&&(u.startsWith('api/credits/refresh')||u.startsWith('api/enrichment/start'))){researchRequests.push([u,o.body]);return {ok:true,json:async()=>({started:true,pending:2})}};if(u==='api/credits/status')return {ok:true,json:async()=>({running:false,history:{error:{performers:2}},skipped:{cooldown:5},runs:[{started:100,mode:'due',status:'completed',done:2,total:2,failed:0}]})};return old(u,o)}}''')
    tab.evaluate("refreshCredits('','force')")
    assert tab.evaluate('JSON.parse(researchRequests[0][1]).force')
    tab.evaluate("refreshCredits('','errors')")
    assert tab.evaluate('JSON.parse(researchRequests[1][1]).retry_errors')
    tab.evaluate("startEnrichment('unclassified')")
    assert tab.evaluate('researchRequests[2][0]')=='api/enrichment/start?mode=unclassified'
    expect(tab.locator('#creditsStatus')).to_contain_text('5 cooldown')
    expect(tab.locator('#researchRunHistory')).to_contain_text('2/2 processed')
    assert not errors,errors
