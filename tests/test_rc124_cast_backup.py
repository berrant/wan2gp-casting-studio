"""Cast-scoped reference collections, portable prompts and persistent model defaults."""
import json
from test_beta5215_empty_and_references import photo_setup
from test_native_plugin import installation
from test_persona_power import tab
API='/casting-studio/api'

def test_role_collections_do_not_mix(photo_setup):
    c,s,_,raw=photo_setup
    def upload(prod,role):
        r=c.post(API+'/reference-images/upload',params={'person':'Example Anchor','production':prod,'character':role},headers={'Content-Type':'image/png'},content=raw)
        assert r.status_code==200,r.text
        return r.json()['id']
    a=upload('Example Show','Captain');b=upload('Example Show','Doctor');g=upload('','')
    assert len({a,b,g})==3
    assert upload('Example Show (2025)','Captain')==a
    for path in ('reference-images','workshop/photos'):
        r=c.get(API+'/'+path,params={'person':'Example Anchor','production':'Example Show','character':'Doctor'})
        assert r.status_code==200,r.text
        rows=r.json() if path=='reference-images' else r.json()['photos']
        assert [x['id'] for x in rows]==[b]
    sources=c.get(API+'/workshop/sources?role_aware=true').json()['sources']
    assert {(x['production'],x['character']) for x in sources}=={('Example Show','Captain'),('Example Show','Doctor'),('','')}
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(c.get(API+'/reference-images/export',params={'person':'Example Anchor','production':'Example Show','character':'Captain'}).content)) as z:
        assert [x['id'] for x in json.loads(z.read('sources.json'))]==[a]

def test_backup_roundtrip_and_atomic_validation(installation):
    c,*_=installation
    original=c.get(API+'/prompts/template').json();original['wardrobe']='Synthetic custom wardrobe'
    assert c.put(API+'/prompts/template',json=original).status_code==200
    backup=c.get(API+'/settings/prompt-backup').json();assert backup['templates']['default']['wardrobe']==original['wardrobe']
    assert c.post(API+'/prompts/template/reset').status_code==200
    assert c.post(API+'/settings/prompt-backup',json=backup).status_code==200
    assert c.get(API+'/prompts/template').json()['wardrobe']==original['wardrobe']
    bad=json.loads(json.dumps(backup));bad['templates']['default']['wardrobe']='Do not save this';bad['templates']['image_bogus']={}
    assert c.post(API+'/settings/prompt-backup',json=bad).status_code==422
    assert c.get(API+'/prompts/template').json()['wardrobe']==original['wardrobe']
    bad=json.loads(json.dumps(backup));bad['final_edits']=[{'key':'bad','choice_key':'x','personal_id':'','prompt':'invalid fake prompt'}]
    assert c.post(API+'/settings/prompt-backup',json=bad).status_code==422

def test_backup_private_edits_require_existing_consent(installation):
    c,*_=installation
    data=c.get(API+'/settings/prompt-backup').json()
    data['final_edits']=[{'key':json.dumps(['private-key','h3_video','checkpoint',1,0],separators=(',',':')),'choice_key':'private-key','personal_id':'missing-id','prompt':'Synthetic private prompt'}]
    r=c.post(API+'/settings/prompt-backup',json=data);assert r.status_code==200,r.text
    assert r.json()['skipped_private_edits']==1
    assert c.get(API+'/settings/prompt-backup').json()['final_edits']==[]

def test_cast_collector_scope_and_workshop_return(tab):
    tab.evaluate("""() => {window.requests=[];const old=fetch;window.fetch=async(u,o)=>{window.requests.push(String(u));const path=String(u).split('?')[0];const out=(data)=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)});if(path==='api/images/search')return out({query:'test',images:[],has_more:false});if(path==='api/reference-images')return out([]);if(path==='api/workshop/sources')return out({sources:[{person:'Example Person',production:'',character:'',count:1},{person:'Example Person',production:'Example Show',character:'Captain',count:1},{person:'Example Person',production:'Example Show',character:'Doctor',count:1}]});if(path==='api/workshop/photos')return out({photos:[]});if(path==='api/workshop/models')return out({models:[]});if(path==='api/workshop/mods')return out({mods:[]});if(path==='api/productions/cast')return out({production:'Example Show',cast:[{actress:'Example Person',character:'Captain',production:'Example Show'}]});return old(u,o)}}""")
    tab.evaluate("$('productionQuery').value='Example';showProductionCast({production:'Example Show',cast:[{actress:'Example Person',character:'Captain',production:'Example Show'}]});openCastCollect('Example Person',{character:'Captain',production:'Example Show'})")
    assert not tab.evaluate("requests.some(x=>x.startsWith('api/images/search'))")
    tab.evaluate("switchCastCollection('both')")
    assert tab.evaluate("activeImage.kind")=='actress'
    assert tab.evaluate("activeImage.production")==''
    tab.evaluate("switchCastCollection('character')")
    assert tab.evaluate("activeImage.character")=='Captain'
    tab.evaluate("openActiveReferenceWorkshop()")
    tab.wait_for_function("$('workshopCollection').value==='1'")
    assert tab.evaluate("requests.some(x=>x.startsWith('api/workshop/photos')&&x.includes('character=Captain'))")
    tab.evaluate('returnToCast()');tab.wait_for_function("activeTab==='productions'&&activeProduction==='Example Show'")
    assert tab.locator('#productionQuery').input_value()=='Example'

def test_generator_preferences_survive_new_session(tab):
    tab.evaluate("""() => {const m=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}});Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});generatorSessionPrefs={version:1,boardModel:'h3_video',lastImageBoard:'flux2_dev',selectedModels:{h3_video:'video-checkpoint',flux2_dev:'image-checkpoint'},modelSettings:{}};storeGeneratorPrefs()}""")
    saved=tab.evaluate('loadGeneratorPrefs()');assert saved['selectedModels']=={'h3_video':'video-checkpoint','flux2_dev':'image-checkpoint'} and saved['lastImageBoard']=='flux2_dev'
    tab.evaluate("$('promptModel').value='h3_video';choices=[];switchPromptModality('image')")
    tab.wait_for_function("$('promptModel').value==='flux2_dev'")
    assert tab.evaluate('loadGeneratorPrefs().lastImageBoard')=='flux2_dev'

def test_backup_browser_roundtrip_and_failed_restore(tab):
    tab.evaluate("""() => {const m=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}});window.confirm=()=>true;window.alert=()=>{};window.backupPosts=0;window.backupReject=true;const old=fetch;window.fetch=async(u,o)=>{if(u==='api/settings/prompt-backup'){if(o?.method==='POST'){window.backupPosts++;return {ok:!window.backupReject,status:window.backupReject?422:200,json:async()=>({templates:1,overrides:0,final_edits:0}),text:async()=> 'invalid backup'}}return {ok:true,status:200,json:async()=>({templates:{default:{wardrobe:'Synthetic saved prompt'}},overrides:{},final_edits:[],character_traits:{}})}}return old(u,o)};URL.createObjectURL=b=>{window.exportedBackup=b;return 'blob:test'};URL.revokeObjectURL=()=>{};HTMLAnchorElement.prototype.click=function(){};localStorage.setItem(UX_MODE_KEY,'true')}""")
    tab.evaluate('exportStudioBackup()')
    backup=tab.evaluate('async()=>JSON.parse(await exportedBackup.text())')
    assert backup['format']=='casting-studio-settings' and backup['version']==1
    assert backup['prompts']['templates']['default']['wardrobe']=='Synthetic saved prompt'
    assert backup['preferences']['casting-studio:generator:session:v1']['version']==1
    tab.evaluate("""async data=>{data.preferences['casting-studio-basic-mode-v1']=false;await importStudioBackup({files:[new File([JSON.stringify(data)],'backup.json')],value:''})}""",backup)
    assert tab.evaluate('localStorage.getItem(UX_MODE_KEY)')=='true'
    assert tab.evaluate('backupPosts')==1
    assert 'Import failed' in tab.locator('#backupStatus').text_content()
    tab.evaluate("""async()=>{const text='{"format":"casting-studio-settings","version":1,"preferences":{"__proto__":{}},"prompts":{}}';await importStudioBackup({files:[new File([text],'bad.json')],value:''})}""")
    assert tab.evaluate('backupPosts')==1
    assert 'Invalid preference key' in tab.locator('#backupStatus').text_content()
