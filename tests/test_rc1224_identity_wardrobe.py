"""Do not promote AI costume descriptions to persistent physical identity."""
import importlib
from test_rc1213_appearance import app, stage, run, approve
from test_native_plugin import installation
from test_dev55_browser import page


def test_wardrobe_leakage_rejected_without_overwriting_approved_profile(app):
    c,p,s,b,n,r=app
    identity=dict(person='Ada Test',character='Example Alien 1',production='Example Series',year=2023,traits='Green skin, paired lekku and integrated mechanical forearm.')
    assert c.put(p+'/characters/identity',json=identity).status_code==200
    job=stage(app).json()['id']
    result=run(app,job)['results'][0]
    draft='Green skin. A brown leather strap crosses the chest. A segmented gauntlet encases the forearm. A brown utility belt is worn.'
    with b.lock:b.job['results'][0]['traits']=draft
    status=c.get(p+'/appearance/batch/'+job).json()['results'][0]
    assert status['traits']==draft
    assert set(status['wardrobe_flags'])=={'leather strap','gauntlet','utility belt'}
    response=approve(app,job,traits=draft)
    assert response.status_code==400 and 'wardrobe' in response.text
    assert s.exact_identity_snapshot(result['profile_key'])[0]==identity['traits']
    assert c.get(p+'/appearance/batch/'+job).json()['results'][0]['state']=='review'
    clean='Green pigmentation, paired lekku, integrated mechanical forearm and permanent facial markings.'
    assert approve(app,job,traits=clean).status_code==200
    assert s.exact_identity_snapshot(result['profile_key'])[0]==clean


def test_anatomy_not_stripped_and_instruction_contract(app):
    _,_,s,*_=app
    clean='Mechanical plating integrated into the skull, prosthetic facial structure, blue irises, orange skin, two lekku, permanent makeup markings, uniform matte green pigmentation, a natural fur coat and biological armor plates.'
    assert s.appearance_wardrobe_flags(clean)==[]
    assert s.appearance_wardrobe_flags('A helmet, goggles and brown leather jacket.')==['helmet','goggles','jacket']
    instructions=importlib.import_module('cb_under_test.vision_bridge').INSTRUCTIONS
    for phrase in ('changing into completely different clothes','integrated prosthetic anatomy','removable armor','conflicting or uncertain observations','every sentence'):
        assert phrase in instructions


def test_browser_warns_without_deleting_draft(page):
    tab,errors=page
    tab.evaluate("""()=>renderAppearanceResults({id:'test',results:[{index:0,character:'Example',label:'Example',state:'review',traits:'Green skin and a utility belt.',wardrobe_flags:['utility belt']}]})""")
    assert 'Remove these details' in tab.locator('#appearanceResults [role=status]').inner_text()
    assert tab.locator('#appearanceResults textarea').input_value()=='Green skin and a utility belt.'
    assert not errors,errors
