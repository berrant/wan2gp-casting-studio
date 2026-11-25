"""Isolated, version-gated H3 Refmod-Fork Extract/Decompile job payloads.

Does NOT import Refmod-Fork or modify its source. Uses its documented H3
custom-settings extraction wrapper. H3 VAE work executes only in WanGP's
native Gradio queue callback. Every task is revalidated immediately before run.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import json, re

SETTING = 'h3_refmod_state'
WRAPPER = '__h3refmod_extract__'
ALLOWED_FILE = re.compile(r'^[A-Za-z0-9_-]+$')


@dataclass
class WorkshopTask:
    op: str
    model_type: str
    name: str
    spec: dict
    expected: Path
    sources: tuple[str, ...] = ()
    family: str = 'minimax_h3'


def safe_mod_name(display_name: str, personal: bool=False) -> str:
    prefix='personal' if personal else 'celebs'
    stem=re.sub(r'[^A-Za-z0-9_-]+','_',display_name.strip()).strip('_')[:120]
    if len(stem)<2 or not ALLOWED_FILE.fullmatch(stem):
        raise ValueError('Enter a RefMod name using letters, numbers, underscores and dashes')
    return f'{prefix}/{stem}'



def public_workshop_path(root: Path, category: str, name: str, suffix: str='') -> Path:
    """Resolve an installed public folder (including a directory link), never a linked file.

    The logical fork identifier stays celebs/NAME; compare physical paths to
    the resolved public directory, not its unresolved spelling.
    """
    if category not in ('minimax_h3','flux2','decompiled') or not re.fullmatch(r'celebs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+',name):
        raise ValueError('Invalid public Workshop identifier')
    public=(root/category/'celebs').resolve()
    for folder in ('minimax_h3','flux2','decompiled'):
        private=(root/folder/'personal').resolve()
        if public.is_relative_to(private) or private.is_relative_to(public):
            raise ValueError('Workshop public and Personal folders overlap; check your RefMod directory configuration')
    relative=Path(*name.split('/')[1:])
    lexical=public/(str(relative)+suffix)
    if lexical.resolve()!=lexical or lexical.is_symlink():
        raise ValueError('Workshop destination contains an unexpected file or subfolder link')
    return lexical

def build_extract_spec(name: str, paths: list[Path], mode='encode') -> dict:
    if not re.fullmatch(r'(?:celebs|personal)/[A-Za-z0-9_-]+',name):
        raise ValueError('RefMod name is outside the approved folder')
    if mode not in ('encode','training'):
        raise ValueError('Use encode or training mode')
    if not 1<=len(paths)<=20 or len(set(map(str,paths)))!=len(paths):
        raise ValueError('Select 1–20 different reference photos')
    return {
        'name':name,'mode':mode,'concept_type':'identity',
        'image_paths':[str(p) for p in paths], 'video_paths':[], 'audio_path':None,
        'remove_background_images_ref':0, 'ref_resolution':1024, 'enc_resolution':1024,
        'pool_h':16,'pool_w':16,'latent_frames':90, 'identity':500 if mode=='training' else 0,
        'multiplier':1,'max_tokens':65536, 'description':'', 'save':True,
        'use_clip_audio':False, 'video_trims':{}, 'video_as_pictures':False,
        'pictures_per_second':1.0, 'merge':False, 'audio_seconds':4.0,
        'clean_audio':False,
    }


def build_flux_extract_spec(name: str, paths: list[Path], layout='separate', budget=4096) -> dict:
    if not __import__('re').fullmatch(r'(?:celebs|personal)/[A-Za-z0-9_-]+',name):
        raise ValueError('Unsafe FLUX RefMod filename')
    if not 1 <= len(paths) <= 20 or len({str(p) for p in paths}) != len(paths):
        raise ValueError('Select 1–20 unique approved pictures')
    if layout not in ('separate','sheet','merge'):
        raise ValueError('Unsupported FLUX picture layout')
    if budget not in (512,1024,2048,4096):
        raise ValueError('Unsupported FLUX token budget')
    return {'name':name, 'images':[str(p) for p in paths], 'videos':[],
            'pictures_per_second':1.0,'layout':layout,'budget':budget,
            'concept_type':'identity','description':''}


def extract_job_settings(session, task: WorkshopTask):
    """Same single declared custom-settings slot used by fork's own Extract UI."""
    if task.op not in ('extract','decompile','extract_flux'):
        raise ValueError('Invalid workshop operation')
    if task.op=='extract_flux':
        if task.family!='flux2':raise ValueError('FLUX extraction requires FLUX model family')
        field='flux_refmod_state'; wrapper='__flux_refmod_extract__'
        data={'model_type':task.model_type,
              'custom_settings':{field:json.dumps({wrapper:task.spec},separators=(',',':'))}}
    else:
        if task.family!='minimax_h3':raise ValueError('H3 extraction requires H3 model family')
        field=SETTING
        data={'model_type':task.model_type,'video_length':107,
              'custom_settings':{field:json.dumps({WRAPPER:task.spec},separators=(',',':'))}}
    merged=session.merge_settings_with_defaults(data)
    merged['custom_settings']=dict(merged.get('custom_settings') or {})
    merged['custom_settings'][field]=data['custom_settings'][field]
    merged['model_type']=task.model_type
    return merged


def read_header(path:Path) -> dict:
    """Read only safetensors metadata header, never load weights or execute it."""
    if not path.is_file() or path.stat().st_size<16:raise ValueError('RefMod is missing or incomplete')
    with path.open('rb') as fh:
        size=int.from_bytes(fh.read(8),'little')
        if size<=0 or size>1024*1024 or size+8>=path.stat().st_size:
            raise ValueError('Invalid safetensors header')
        header=json.loads(fh.read(size).decode('utf-8'))
    raw=(header.get('__metadata__') or {}).get('refmod_meta')
    if not isinstance(raw,str):raise ValueError('No H3 RefMod metadata available')
    data=json.loads(raw)
    return {k:data.get(k) for k in ('name','kind','mode','source_shape','pool','optimize_steps',
            'concept_type','has_audio','description','tags','enc_layout','enc_fps')}
