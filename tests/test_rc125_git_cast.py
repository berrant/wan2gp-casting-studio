"""RC12.5 cast coverage, local Git install layout, and persistent storage checks."""
import importlib, json, shutil, subprocess
from pathlib import Path
import pytest
from test_native_plugin import installation
from test_beta5215_empty_and_references import photo_setup
from test_persona_power import tab
API='/casting-studio/api'

def test_cast_reference_counts_are_role_scoped_and_existing(photo_setup):
    c,srv,_,raw=photo_setup
    for role in ('Captain','Doctor'):
        r=c.post(API+'/productions/cast',json={'production':'Example Show','actress':'Example Anchor','character':role});assert r.status_code==200,r.text
    def upload(prod,char):
        r=c.post(API+'/reference-images/upload',params={'person':'Example Anchor','production':prod,'character':char},headers={'Content-Type':'image/png'},content=raw)
        assert r.status_code==200,r.text;return r.json()['id']
    upload('','');upload('Example Show','Captain');missing=upload('Example Show','Doctor');upload('Other Show','Captain')
    def counts():
        r=c.get(API+'/productions/cast',params={'production':'Example Show'});assert r.status_code==200,r.text
        return {x['character']:x['reference_counts'] for x in r.json()['cast']}
    assert counts()=={'Captain':{'performer':1,'character':1},'Doctor':{'performer':1,'character':1}}
    with srv.connect() as db: fname=db.execute('SELECT filename FROM reference_images WHERE id=?',(missing,)).fetchone()[0]
    (srv.REFERENCE_DIR/fname).unlink()
    assert counts()['Doctor']=={'performer':1,'character':0}


def test_coverage_filter_compact_and_recent(tab):
    tab.evaluate("""() => {const m=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}});showProductionCast(productionData)}""")
    assert tab.locator('#productionCoverageSummary').text_content()=='2/3 installed · 0 convertible · 1 missing · 3 shown'
    tab.locator('#productionCoverageFilter').select_option('missing')
    assert tab.locator('#productionCast .cast-row').count()==1
    assert 'Missing Character' in tab.locator('#productionCast').text_content()
    tab.locator('#productionCastFilter').fill('no such role')
    assert 'No cast members match' in tab.locator('#productionCast').text_content()
    tab.locator('#productionCastFilter').fill('')
    tab.locator('#productionCompact').check()
    assert tab.locator('#productionCast').evaluate("e=>e.classList.contains('compact')")
    assert tab.evaluate('localStorage.getItem(CAST_COMPACT_KEY)')=='true'
    tab.evaluate('showProductionCast(productionData)')
    assert tab.locator('#productionCoverageFilter').input_value()=='missing'
    tab.evaluate("showProductionCast({production:'Different Show',cast:[]})")
    assert tab.locator('#productionCoverageFilter').input_value()=='all'
    assert tab.evaluate('JSON.parse(localStorage.getItem(CAST_RECENT_KEY))')==['Different Show','Dark Matter']
    tab.evaluate("recentProductions=[];loadCastViewPrefs()")
    assert tab.locator('#recentProductions option').count()==3
    tab.evaluate('clearRecentProductions()');assert tab.locator('#recentProductionsBar').is_hidden()


def test_repeated_native_mount_preserves_user_data(installation):
    c,p,root,_=installation
    srv=importlib.import_module('cb_under_test.app.server')
    original=c.get(API+'/prompts/template').json();original['wardrobe']='Synthetic upgrade preservation test'
    assert c.put(API+'/prompts/template',json=original).status_code==200
    assert c.post(API+'/productions/cast',json={'production':'Example Show','actress':'Ada Test','character':'Captain'}).status_code==200
    assert srv.DATA==root/'user_data'
    p.create_web_app();srv.startup()
    assert c.get(API+'/prompts/template').json()['wardrobe']==original['wardrobe']
    assert len(c.get(API+'/productions/cast',params={'production':'Example Show'}).json()['cast'])==1
    assert not srv.DATA.is_relative_to(Path(__file__).resolve().parents[1])


def test_repository_root_git_clone_and_fast_forward(tmp_path):
    if not shutil.which('git'):pytest.skip('Git unavailable')
    root=Path(__file__).resolve().parents[1]
    src=tmp_path/'source';src.mkdir()
    def git(cwd,*args):return subprocess.check_output(['git','-C',str(cwd),*args],stderr=subprocess.STDOUT,text=True)
    git(src,'init','-b','main');git(src,'config','user.name','Synthetic Test');git(src,'config','user.email','synthetic@localhost')
    for name in ('plugin.py','plugin_info.json','__init__.py','requirements.txt','.gitignore'):
        shutil.copy2(root/name,src/name)
    shutil.copytree(root/'app',src/'app',ignore=shutil.ignore_patterns('__pycache__'))
    git(src,'add','.');git(src,'commit','-m','Initial fixture')
    host=tmp_path/'host';host.mkdir();plugins=host/'plugins';plugins.mkdir()
    dst=plugins/'wan2gp-casting-studio';git(plugins,'clone',str(src),str(dst))
    assert json.loads((dst/'plugin_info.json').read_text())['version']==json.loads((root/'plugin_info.json').read_text())['version']
    assert (dst/'plugin.py').is_file() and (dst/'app/index.html').is_file()
    data=host/'data'/'casting-studio';data.mkdir(parents=True);sentinel=data/'private-prefs.json';sentinel.write_text('{"fixture":true}')
    (src/'plugin.py').write_text((src/'plugin.py').read_text()+'\n# Synthetic update marker\n')
    git(src,'add','plugin.py');git(src,'commit','-m','Update fixture');git(dst,'pull','--ff-only')
    assert 'Synthetic update marker' in (dst/'plugin.py').read_text()
    assert sentinel.read_text()=='{"fixture":true}'
    assert not git(dst,'status','--porcelain').strip()


def test_convertible_filter_does_not_count_as_installed(tab):
    tab.evaluate("""() => {catalog={...catalog,models:catalog.models.map(m=>m.name==='Zoie Palmer'?{...m,convertible_to_flux:true}:m)};$('promptModel').value='flux2_dev';showProductionCast(productionData)}""")
    assert tab.locator('#productionCoverageSummary').text_content()=='0/3 installed · 1 convertible · 2 missing · 3 shown'
    tab.locator('#productionCoverageFilter').select_option('convertible')
    assert tab.locator('#productionCast .cast-row').count()==1
    assert 'Zoie Palmer' in tab.locator('#productionCast').text_content()
    assert tab.locator('#productionCoverageProgress').evaluate('e=>e.value')==0


def test_stale_cast_response_cannot_overwrite_new_model(tab):
    tab.evaluate("""() => {const old=fetch;window.castRequests=[];window.fetch=(u,o)=>String(u).startsWith('api/productions/cast?')?new Promise(resolve=>castRequests.push({url:String(u),resolve})):old(u,o);activeProduction='Dark Matter';activeTab='productions';$('promptModel').value='h3_video';window.pendingA=refreshProductionCast();$('promptModel').value='flux2_dev';window.pendingB=refreshProductionCast()}""")
    tab.evaluate("""async()=>{const response=(data)=>({ok:true,json:async()=>data});castRequests[1].resolve(response({...productionData,cast:[{actress:'Missing',character:'New response',production:'Dark Matter'}]}));await pendingB;castRequests[0].resolve(response({...productionData,cast:[{actress:'Missing',character:'Old response',production:'Dark Matter'}]}));await pendingA}""")
    assert 'New response' in tab.locator('#productionCast').text_content()
    assert 'Old response' not in tab.locator('#productionCast').text_content()


def test_recent_resume_clears_previous_search_results(tab):
    tab.evaluate("""() => {showProductionCast(productionData);$('productionMatches').hidden=false;$('productionMatches').textContent='Outdated results';$('productionQuery').value='Other title'}""")
    tab.evaluate("resumeRecentProduction('Dark Matter')")
    assert tab.locator('#productionQuery').input_value()=='Dark Matter'
    assert tab.locator('#productionMatches').text_content()==''
    assert 'Dark Matter' in tab.locator('#productionCurrentName').text_content()
