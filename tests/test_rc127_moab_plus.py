"""RC12.7 adversarial tests; isolated synthetic runtime, no external research."""
import json
from PIL import Image
from test_native_plugin import installation
from test_rc2_jackhammer import server
API='/casting-studio/api'


def choose(c,character='Captain',path='Ada_Test_H3.safetensors',production='Example Show'):
    r=c.put(API+'/choices',json={'key':'','person':'Ada Test','character':character,'production':production,'refmod':path});assert r.status_code==200,r.text


def test_factory_fields_migrate_without_overwriting_custom_fields(installation):
    c,*_=installation;s=server();default=c.get(API+'/prompts/image-template?model=flux2_dev').json()
    assert default['shots'][0]['framing'] and default['shots'][0]['expression']
    assert 'chest-up' not in default['shots'][0]['action'].lower()
    default['shots'][0].update(action=s.LEGACY_IMAGE_SCENE_DEFAULTS['scene1'],framing='Head to mid thigh',expression='Serious')
    default['shots'][1]['action']='My deliberately customized action and framing'
    with s.connect() as db:db.execute('INSERT OR REPLACE INTO prompt_settings VALUES (?,?)',('image_flux2_dev',json.dumps(default)))
    got=c.get(API+'/prompts/image-template?model=flux2_dev').json()
    assert got['shots'][0]['action']==s.IMAGE_SCENE_DEFAULTS['scene1']
    assert got['shots'][0]['framing']=='Head to mid thigh' and got['shots'][0]['expression']=='Serious'
    assert got['shots'][1]['action']==default['shots'][1]['action']


def test_variants_are_discovered_and_selected_exactly(installation):
    c,p,root,_=installation
    variant='Ada_Test__role__Captain_Example_Show_H3.safetensors'
    (root/'refmods/minimax_h3/celebs'/variant).write_bytes(b'synthetic')
    catalog=c.get(API+'/catalog').json()['models'];m=next(x for x in catalog if x['path']==variant)
    assert m['name']=='Ada Test' and m['role_specific']
    choose(c,path=variant)
    assert c.get(API+'/choices').json()[0]['refmod']==variant
    assert c.post(API+'/choices/reconcile',json={'family':'minimax_h3'}).json()['choices'][0]['refmod']==variant
    assert c.put(API+'/choices',json={'key':'','person':'Other Person','character':'Captain','production':'Example Show','refmod':variant}).status_code==400


def test_saved_set_restore_skips_missing_files_and_keeps_existing(installation):
    c,p,root,_=installation
    name='Ada_Test__role__Captain_Example_Show_H3.safetensors';file=root/'refmods/minimax_h3/celebs'/name;file.write_bytes(b'synthetic')
    choose(c,path=name);choose(c,'Doctor')
    payload={'production':'Example Show','family':'minimax_h3'}
    assert c.put(API+'/production-selection-set',json=payload).json()=={'saved':2}
    choices=c.get(API+'/choices').json();key=next(x['key'] for x in choices if x['character']=='Captain')
    with server().connect() as db:db.execute('DELETE FROM choices WHERE key=?',(key,))
    file.unlink();r=c.post(API+'/production-selection-set/restore',json=payload);assert r.status_code==200,r.text
    assert r.json()['added']==0 and r.json()['skipped']==1 and len(r.json()['errors'])==1
    assert len(c.get(API+'/choices').json())==1
    file.write_bytes(b'synthetic');assert c.post(API+'/production-selection-set/restore',json=payload).json()['added']==1
    assert len(c.get(API+'/choices').json())==2


def test_corrupt_set_fails_closed(installation):
    c,*_=installation;choose(c);s=server();payload={'production':'Example Show','family':'minimax_h3'}
    assert c.put(API+'/production-selection-set',json=payload).status_code==200
    before=c.get(API+'/choices').json()
    with s.connect() as db:db.execute('UPDATE production_selection_sets SET payload=?',('{bad',))
    assert c.post(API+'/production-selection-set/restore',json=payload).status_code==409
    assert c.get(API+'/choices').json()==before


def test_selection_sets_family_guard(installation):
    c,*_=installation;choose(c);p={'production':'Example Show','family':'invalid'}
    assert c.put(API+'/production-selection-set',json=p).status_code==400
    assert c.post(API+'/production-selection-set/restore',json=p).status_code==400
    assert c.put(API+'/production-selection-set',json={**p,'family':'flux2'}).status_code==409


def test_gallery_deleted_or_changed_files_never_reappear(installation):
    c,p,root,_=installation;b=p.queue_bridge;b._jobs['gallery']={'id':'gallery','state':'running'}
    files=[]
    for i in range(3):
        f=root/f'synthetic-{i}.png';Image.new('RGB',(30,30),(i,0,0)).save(f);files.append(f);b._record_monitor_output('gallery',str(f),i+1)
    first=c.get(API+'/generator/monitor-gallery').json()['results'];assert len(first)==3
    assert [r['task_index'] for r in first]==[3,2,1]
    files[0].unlink();files[1].write_bytes(b'changed')
    assert len(c.get(API+'/generator/monitor-gallery').json()['results'])==1
    assert b.monitor_output(first[1]['id']) is None


def test_gallery_bounded_and_duplicate_suppressed(installation):
    c,p,root,_=installation;b=p.queue_bridge;b._jobs['gallery']={'id':'gallery','state':'running'}
    for i in range(32):
        f=root/f'synthetic-{i}.png';Image.new('RGB',(16,16),(i,0,0)).save(f);b._record_monitor_output('gallery',str(f),i+1)
        b._record_monitor_output('gallery',str(f),i+1)
    results=b.monitor_gallery();assert len(results)==30 and len({x['id'] for x in results})==30
    assert [r['task_index'] for r in results]==list(range(32,2,-1))


def test_identity_shared_between_image_and_video_and_rejects_malformed(installation):
    c,*_=installation;s=server();p={'character':'Captain','production':'Example Show','traits':'Distinctive silver hair and brown eyes.'}
    assert c.put(API+'/characters/identity',json=p).status_code==200
    assert c.get(API+'/characters/identity',params={'character':'Captain','production':'Example Show'}).json()['traits']==p['traits']
    assert s.character_identity_traits('Captain','Example Show')==p['traits']
    assert c.put(API+'/characters/identity',json={**p,'traits':'wardrobe_description: altered'}).status_code==400
    assert s.character_identity_traits('Captain','Example Show')==p['traits']


def test_late_gallery_outputs_do_not_rewind_live_monitor(installation):
    c,p,root,_=installation;b=p.queue_bridge;b._jobs['gallery']={'id':'gallery','state':'running'}
    for i in (3,1,2,1):
        f=root/f'late-{i}.png'
        if not f.exists():Image.new('RGB',(16,16),(i,0,0)).save(f)
        b._record_monitor_output('gallery',str(f),i)
    assert b.status('gallery')['last_result']['task_index']==3
    assert {r['task_index'] for r in b.monitor_gallery()}=={1,2,3}
    assert len(b.monitor_gallery())==3


def test_cross_family_never_guesses_character_variant(installation):
    c,p,root,_=installation
    (root/'refmods/flux2/celebs/Ada_Test__role__Doctor_Example_Show_FLUX.safetensors').write_bytes(b'synthetic')
    choose(c)
    r=c.post(API+'/choices/reconcile',json={'family':'flux2'});assert r.status_code==200,r.text
    assert r.json()['choices']==[] and len(r.json()['removed'])==1


def test_export_and_live_preview_use_exact_variant(installation):
    c,p,root,_=installation;s=server()
    name='Ada_Test__role__Captain_Example_Show_H3.safetensors'
    (root/'refmods/minimax_h3/celebs'/name).write_bytes(b'synthetic')
    choose(c,path=name);choose(c,'Doctor')
    for model in ('h3_video','h3_image_pruned'):
        text=c.get(API+'/prompts/export',params={'model':model}).text
        assert name in text and 'Ada_Test_H3.safetensors' in text
        for item in c.get(API+'/choices').json():
            prompt,family,path=s.build_live_cast_prompt(s.CastTask(choice_key=item['key'],model=model))
            assert path.name==item['refmod']
    # Cross-family export and live preview must not guess a different character's variant.
    (root/'refmods/flux2/celebs/Ada_Test__role__Doctor_Example_Show_FLUX.safetensors').write_bytes(b'synthetic');s.scan(force=True)
    text=c.get(API+'/prompts/export',params={'model':'flux2_dev'}).text
    assert 'MISSING_COMPATIBLE_REFMOD' in text and '__role__Doctor' not in text
    import pytest
    with pytest.raises(ValueError):s.build_live_cast_prompt(s.CastTask(choice_key=c.get(API+'/choices').json()[0]['key'],model='flux2_dev'))


def test_saved_selection_corrupt_key_is_not_restored(installation):
    c,*_=installation;choose(c);s=server();payload={'production':'Example Show','family':'minimax_h3'}
    assert c.put(API+'/production-selection-set',json=payload).status_code==200
    with s.connect() as db:
        rows=json.loads(db.execute('SELECT payload FROM production_selection_sets').fetchone()[0]);rows[0]['key']='incorrect-key';db.execute('UPDATE production_selection_sets SET payload=?',(json.dumps(rows),))
    before=c.get(API+'/choices').json()
    assert c.post(API+'/production-selection-set/restore',json=payload).status_code==409
    assert c.get(API+'/choices').json()==before


def test_manifest_summary_does_not_replace_identified_output(installation):
    c,p,root,_=installation;b=p.queue_bridge
    b._jobs['gallery']={'id':'gallery','state':'running','_monitor_tasks':[{'person':'Synthetic actor','scene':1}]}
    f=root/'native.png';Image.new('RGB',(16,16)).save(f)
    b._record_monitor_output('gallery',str(f),1)
    original=b.status('gallery')['last_result']
    b._record_monitor_output('gallery',str(f),None,from_result=True)
    assert b.status('gallery')['last_result']==original
    assert b.monitor_gallery()==[original]
