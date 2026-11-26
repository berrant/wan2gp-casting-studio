"""Queue-pass, remake isolation, responsible-use UX and cast coverage regressions."""
from importlib import import_module
from test_native_plugin import installation
from test_dev56 import _init_128
from test_v102_film_search import lead
from test_dev55_browser import page
import pytest
API='/casting-studio/api'

def test_subset_preserves_distinct_prompts_and_scope(installation):
    c,plugin,session,body=_init_128(installation)
    keys=[x['key'] for x in c.get(API+'/choices').json()]
    body['choice_keys']=keys[7:107]
    r=c.post(API+'/generator/batch/preview',json=body)
    assert r.status_code==200,r.text
    rows=r.json()['tasks']
    assert [x['choice_key'] for x in rows]==keys[7:107]
    assert len(set(x['prompt'] for x in rows))==100
    assert c.post(API+'/generator/batch/submit',json=body).json()['task_count']==100
    assert len(plugin.queue_bridge._pending)==1
    for bad in ([keys[0],keys[0]],[keys[0],'missing']):
        r=c.post(API+'/generator/batch/submit',json={**body,'choice_keys':bad})
        assert r.status_code==400,r.text
    assert c.post(API+'/generator/batch/submit',json={**body,'scope':'production:nonexistent'}).status_code==400
    assert len(plugin.queue_bridge._pending)==1
    plugin.queue_bridge.process_pending_in_gradio(session)
    assert len(session.manifests)==1 and len(session.manifests[0])==100


def test_same_title_different_release_keeps_both(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    def fake(client,params):
        if params['action']=='query':return {'query':{'pages':[{'title':'The Thing (1982 film)'},{'title':'The Thing (2011 film)'}]}}
        year=1982 if '1982' in params['page'] else 2011
        if params.get('section')==0:return {'parse':{'text':lead(year,'The Thing')}}
        if params['prop']=='sections':return {'parse':{'sections':[{'line':'Cast','index':'2'}]}}
        return {'parse':{'text':f'<ul><li>Example Performer as Role {year}</li></ul>'}}
    monkeypatch.setattr(s,'wiki_api',fake)
    # A manually created record without a year must acquire the verified year.
    assert c.post(API+'/productions',json={'name':'The Thing','kind':'film'}).status_code==200
    for year in (1982,2011):
        d=c.get(API+'/productions/cast-suggestions',params={'production':f'The Thing ({year})','kind':'film'}).json()
        assert d['year']==year and len(d['candidates'])==1,d
        title=d['production']
        assert c.post(API+'/productions',json={'name':title,'kind':'film','year':year,'preserve_existing':True}).status_code==200
        assert c.post(API+'/productions/cast/bulk',json={'production':title,'members':[{**d['candidates'][0],'production':title}]}).status_code==200
    a=c.get(API+'/productions/cast',params={'production':'The Thing'}).json()['cast']
    b=c.get(API+'/productions/cast',params={'production':'The Thing (2011 film)'}).json()['cast']
    assert [(x['character'],x['year']) for x in a]==[('Role 1982',1982)]
    assert [(x['character'],x['year']) for x in b]==[('Role 2011',2011)]
    assert s.portrayal_production_label(b[0])=='The Thing (2011)'
    with s.connect() as db:assert db.execute('SELECT year FROM productions WHERE key=?',('thething',)).fetchone()==(1982,)
    assert s.canonical_role_key('Example Performer','Same Role','The Thing')!=s.canonical_role_key('Example Performer','Same Role','The Thing (2011 film)')


def test_multiformat_cast_and_billed_coverage(installation,monkeypatch):
    c,*_=installation;s=import_module('cb_under_test.app.server')
    def fake(client,params):
        if params['action']=='query':return {'query':{'pages':[{'title':'Synthetic Feature (film)'}]}}
        if params.get('section')==0:
            text=lead(1983,'Synthetic Feature').replace('</table>','<tr><th>Starring</th><td><a href="/wiki/Example_A">Example Actor</a><br><a href="/wiki/Example_B">Missing Actor</a></td></tr></table>')
            return {'parse':{'text':text}}
        if params['prop']=='sections':return {'parse':{'sections':[{'line':'Cast','index':'2'},{'line':'Voice cast','index':'3'},{'line':'Production','index':'4'}]}}
        if params['section']=='2':return {'parse':{'text':'''<ul><li>Example Actor as Dr. Example: a physician.<ul><li>Nested Performer as Assistant</li></ul></li></ul><table><tr><th>Character</th><th>Actor</th></tr><tr><td>Captain</td><td>Table Performer</td></tr></table><p>The cast also includes Extra Performer as Pilot, Another Performer as Engineer and Final Performer as Navigator.</p><p>The plot describes Nobody Here as a character.</p>'''}}
        assert params['section']=='3'
        return {'parse':{'text':'<ul><li>Example Actor as Dr. Example</li><li>Voice Performer as Robot</li></ul>'}}
    monkeypatch.setattr(s,'wiki_api',fake)
    d=c.get(API+'/productions/cast-suggestions',params={'production':'Synthetic Feature','kind':'film'}).json()
    assert [(x['actress'],x['character']) for x in d['candidates']]==[('Example Actor','Dr. Example'),('Nested Performer','Assistant'),('Table Performer','Captain'),('Extra Performer','Pilot'),('Another Performer','Engineer'),('Final Performer','Navigator'),('Voice Performer','Robot')],d
    assert '1 billed performer' in d['note'] and 'not an exhaustive' in d['coverage']
    assert c.post(API+'/personal',json={'name':'Extra Performer','consent':False}).status_code==200
    again=c.get(API+'/productions/cast-suggestions',params={'production':'Synthetic Feature','kind':'film'}).json()
    assert 'Extra Performer' not in [x['actress'] for x in again['candidates']]
    assert c.post(API+'/productions/cast/bulk',json={'production':'Synthetic Feature','members':[{'production':'Synthetic Feature','actress':'Extra Performer','character':'Pilot'}]}).status_code==403
    s.CAST_SUGGEST_CACHE.clear()
    def partial(client,params):
        if params.get('section')=='3':raise ValueError('temporary outage')
        return fake(client,params)
    monkeypatch.setattr(s,'wiki_api',partial)
    result=c.get(API+'/productions/cast-suggestions',params={'production':'Synthetic Feature','kind':'film'}).json()
    assert result['candidates'] and 'cast section(s) unavailable' in result['note']
    monkeypatch.setattr(s,'wiki_api',fake)
    assert any(x['actress']=='Voice Performer' for x in c.get(API+'/productions/cast-suggestions',params={'production':'Synthetic Feature','kind':'film'}).json()['candidates'])


def test_acknowledged_dialog_is_read_only_and_clear(page):
    tab,errors=page
    tab.evaluate('''()=>{const old=fetch;window.fetch=async(u,o={})=>u==='api/responsible-use'?{ok:true,json:async()=>({version:'test',acknowledged:true,rules:['Example rule']})}:old(u,o);}''')
    tab.locator('#responsibleUseOpen').click()
    tab.wait_for_function("$('responsibleUseStatus').textContent.includes('Responsibilities acknowledged')")
    assert not tab.locator('#responsibleUseAccept').is_visible()
    assert not tab.locator('#responsibleUseSave').is_visible()
    assert tab.locator('#responsibleUseDismiss').text_content()=='Close'
    tab.locator('#responsibleUseDismiss').click()
    assert not tab.locator('#responsibleUseModal').is_visible()
    assert not errors,errors


def test_last_selection_cannot_repeat_without_new_pass(page):
    tab,errors=page
    # about:blank in the browser fixture has an opaque origin; emulate tab storage.
    tab.evaluate('''()=>{const m=new Map();Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}})}''')
    tab.evaluate('openGenerator()');tab.wait_for_function("!$('generatorSubmit').disabled")
    assert '1 left' in tab.locator('#generatorSubmit').text_content()
    tab.locator('#generatorSubmit').click()
    tab.wait_for_function("window.responses.length===1&&!generatorSubmitBusy")
    assert tab.locator('#generatorSubmit').is_disabled()
    assert tab.locator('#generatorQueueAll').is_disabled()
    tab.evaluate('submitGenerator(true)');assert tab.evaluate('window.responses.length')==1
    tab.evaluate('generatorQueuePasses.clear();generatorUpdateSubmitEnabled()')
    assert tab.locator('#generatorSubmit').is_disabled()
    tab.once('dialog',lambda d:d.accept());tab.locator('#generatorRestartPass').click()
    assert tab.locator('#generatorSubmit').is_enabled()
    assert not errors,errors


def test_queue_all_after_one_of_hundred_and_failed_preflight(page):
    tab,errors=page
    tab.evaluate('''()=>{choices=Array.from({length:100},(_,i)=>({key:'choice'+i,person:'Example Person',character:'Role '+i,production:'Example Show',refmod:'Example.safetensors'}));window.batchWrites=[];window.blockBatch=true;const orig=fetch;const ok=d=>({ok:true,json:async()=>d,text:async()=>JSON.stringify(d)});window.fetch=async(u,o={})=>{if(u==='api/generator/batch/preflight'){const n=JSON.parse(o.body).choice_keys.length;return ok({count:n,ready:window.blockBatch?n-1:n,blocked:window.blockBatch?1:0,relay_ready:true,issues:[]})}if(u==='api/generator/batch/submit'){const body=JSON.parse(o.body);batchWrites.push(body);return ok({id:'batch00000000',task_count:body.choice_keys.length})}return orig(u,o);};openGenerator();}''')
    tab.wait_for_function("!$('generatorSubmit').disabled&&$('generatorChoice').options.length===100")
    first=tab.locator('#generatorChoice').input_value()
    tab.locator('#generatorSubmit').click();tab.wait_for_function("window.responses.length===1&&!$('generatorQueueAll').disabled")
    assert '99 left' in tab.locator('#generatorQueueAll').text_content()
    tab.locator('#generatorQueueAll').click();tab.wait_for_function("$('generatorStatus').textContent.includes('Preflight blocked')")
    assert tab.evaluate('batchWrites.length')==0 and '99 left' in tab.locator('#generatorQueueAll').text_content()
    tab.evaluate('blockBatch=false');tab.once('dialog',lambda d:d.accept());tab.locator('#generatorQueueAll').click()
    tab.wait_for_function('batchWrites.length===1&&!generatorSubmitBusy')
    req=tab.evaluate('batchWrites[0]');assert len(req['choice_keys'])==99 and first not in req['choice_keys']
    assert len(set(req['choice_keys']))==99
    assert tab.locator('#generatorQueueAll').is_disabled() and tab.locator('#generatorSubmit').is_disabled()
    assert not errors,errors
