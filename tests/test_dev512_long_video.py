"""Native 60-second sliding-window generation and Productions-first navigation."""
import json
from test_native_plugin import installation, _mock_fork, FakeWanSession, _create_public_selection, _await_job
from test_dev55_browser import page
from pathlib import Path

API='/casting-studio/api'

def test_60_second_native_one_movie_with_four_window_prompts(installation):
    client,plugin,root,_=installation
    _mock_fork(root)
    session=FakeWanSession()
    session.defs[0]['sliding_window']=True
    plugin.queue_bridge.api_session=session
    key=_create_public_selection(client)
    body={"choice_key":key,"model":"h3_video","model_type":"h3_ref2va_pruned_checkpoint",
          "video_seconds":60,"video_script_mode":"sequence","steps":8,
          "sliding":{"sliding_window_size":362,"sliding_window_overlap":18,
                     "sliding_window_color_correction_strength":0.5,"sliding_window_overlap_noise":0,
                     "sliding_window_discard_last_frames":0,"sliding_window_trim_first_frames":0}}
    # set exactly four independently editable videos
    current=client.get(API+'/prompts/template').json();current.update({'video_count':4})
    for n in range(1,5):
        current[f'video{n}_action']=f'VISIBLE ACTION FOR WINDOW {n}'
    assert client.put(API+'/prompts/template',json=current).status_code==200
    preview=client.post(API+'/generator/preview',json=body)
    assert preview.status_code==200,preview.text
    for n in range(1,5):assert f'VISIBLE ACTION FOR WINDOW {n}' in preview.json()['prompt']
    assert preview.json()['prompt'].count('subject_definitions:')==4
    submitted=client.post(API+'/generator/submit',json=body)
    assert submitted.status_code==200,submitted.text
    result=_await_job(client,submitted.json()['id'])
    assert result['state']=='completed',result
    assert len(session.submitted)==1
    sent=session.submitted[0]
    assert sent['video_length']=='60s'
    assert sent['multi_prompts_gen_type']=='PW'
    assert sent['sliding_window_overlap']==18
    assert sent['sliding_window_size']==362
    for n in range(1,5):assert f'VISIBLE ACTION FOR WINDOW {n}' in sent['prompt']

def test_repeat_prompt_30s_and_invalid_unsupported(installation):
    client,plugin,root,_=installation
    _mock_fork(root);session=FakeWanSession();session.defs[0]['sliding_window']=True
    plugin.queue_bridge.api_session=session
    key=_create_public_selection(client)
    task={'choice_key':key,'model':'h3_video','model_type':'h3_ref2va_pruned_checkpoint','video_seconds':30,
          'video_script_mode':'single','sliding':{'sliding_window_size':362,'sliding_window_overlap':18}}
    first=client.post(API+'/generator/submit',json=task)
    assert first.status_code==200
    assert _await_job(client,first.json()['id'])['state']=='completed'
    assert session.submitted[-1]['multi_prompts_gen_type']=='FG'
    assert session.submitted[-1]['video_length']=='30s'
    assert client.post(API+'/generator/submit',json={**task,'video_seconds':70}).status_code==422
    failed=client.post(API+'/generator/submit',json={**task,'sliding':{'sliding_window_size':150,'sliding_window_overlap':149,'sliding_window_discard_last_frames':2}})
    assert failed.status_code==400
    assert 'Window size must exceed' in failed.text

def test_productions_first_people_dropdown_and_no_nav_counts(page):
    tab,errors=page
    assert tab.locator('#navTabs .tab-count').count()==0
    assert tab.locator('#navTabs #productionsTab').count()==1
    assert tab.locator('#peopleMenu button span').all_text_contents()==['Performers','Personal','Models / Influencers','Television Personalities']
    tab.locator('#peopleMenuButton').click();tab.locator('[data-people-category=\"'+str('performers')+'\"]').click()
    assert tab.locator('#browseSection').is_visible()
    tab.locator('#peopleMenuButton').click();tab.locator('[data-people-category=\"'+str('personal')+'\"]').click()
    assert tab.locator('#personalSection').is_visible()
    tab.locator('#productionsTab').click()
    assert tab.locator('#productionSection').is_visible()
    assert not errors,errors
