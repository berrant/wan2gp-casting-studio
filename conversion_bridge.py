"""Refmod-Fork compatible H3 picture -> FLUX conversion plan.

GPU work is performed by QueueBridge from a *native WanGP Gradio callback*.
This module does not import the fork, and never rewrites an existing RefMod.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

H3_SETTING = 'h3_refmod_state'
H3_JOB_KEY = '__h3refmod_extract__'
FLUX_SETTING = 'flux_refmod_state'
FLUX_JOB_KEY = '__flux_refmod_extract__'


@dataclass(frozen=True)
class ConversionItem:
    key: str
    source: str
    person: str
    personal_id: str = ''


@dataclass(frozen=True)
class ConversionTask:
    target_model: str
    h3_model_type: str
    flux_model_type: str
    items: tuple[ConversionItem, ...]
    library: bool = False


def conversion_settings(session, model_type: str, family: str, spec: dict) -> dict:
    if family == 'minimax_h3':
        key, wrapper = H3_SETTING, H3_JOB_KEY
    elif family == 'flux2':
        key, wrapper = FLUX_SETTING, FLUX_JOB_KEY
    else:
        raise ValueError('Unsupported conversion family')
    data = {'model_type':model_type,
            'custom_settings':{key:json.dumps({wrapper:spec}, separators=(',', ':'))}}
    if family == 'minimax_h3':
        data['video_length'] = 107
    merged = session.merge_settings_with_defaults(data)
    merged['model_type'] = model_type
    merged['custom_settings'] = dict(merged.get('custom_settings') or {})
    merged['custom_settings'][key] = data['custom_settings'][key]
    return merged


def is_h3_picture_refmod(meta: dict) -> bool:
    """Identify H3 still-picture collections even when stored as `kind: video`.

    The H3 writer marks multiple images in one latent stack as kind=video.
    We must distinguish that from genuine temporal video. Never infer picture
    status from the kind field alone, and never convert audio-bearing mods.
    """
    if not isinstance(meta, dict) or meta.get('has_audio') not in (None, False, '', 0):
        return False
    if meta.get('kind') == 'image':
        return True
    if meta.get('kind') != 'video':
        return False
    source = str(meta.get('source') or '').strip().casefold()
    tags = meta.get('tags') or []
    tags = ' '.join(str(x) for x in tags) if isinstance(tags, (list, tuple)) else str(tags)
    tag = tags.casefold()
    # The fork explicitly labels a still stack (23 img, 0 vid), as seen in
    # older RefMods. A source=stack alone is insufficient if a video count exists.
    images = __import__('re').search(r'(\d+)\s*(?:img|images|pics|pictures)\b', tag)
    videos = __import__('re').search(r'(\d+)\s*(?:vid|video|videos)\b', tag)
    if videos and int(videos.group(1)) > 0:
        return False
    if images and int(images.group(1)) > 0 and videos and int(videos.group(1)) == 0:
        return True
    # A known picture stack can be encoded as several + separated stills;
    # require explicitly declared source=stack and no video reference tags.
    shape = str(meta.get('source_shape') or '')
    if source in ('stack', 'images', 'pictures') and '+' in shape and not videos:
        return True
    return False


def safetensors_metadata(path: Path, meta_key: str) -> dict:
    """Tiny read-only header inspection, avoiding tensor loading/execution."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size < 32:
        raise ValueError('Missing or malformed RefMod')
    with path.open('rb') as fh:
        length = int.from_bytes(fh.read(8), 'little')
        if length < 2 or length > 1024*1024 or length+8 >= path.stat().st_size:
            raise ValueError('Invalid safetensors header length')
        header = json.loads(fh.read(length).decode('utf-8'))
    raw = (header.get('__metadata__') or {}).get(meta_key)
    if not isinstance(raw, str):
        raise ValueError('Missing required RefMod metadata')
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError('Invalid RefMod metadata')
    return parsed


def free_destination(root:Path, name:str):
    """Non-overwriting destination, preserving fork's subfolder conventions."""
    if not name or any(part in ('','.','..') or not part.replace('_','').replace('-','').isalnum() for part in name.split('/')):
        raise ValueError('Unsafe RefMod name')
    base=(root/'flux2').resolve()
    i=1
    while True:
        candidate = name if i == 1 else f'{name}_{i}'
        path=(base/(candidate+'.safetensors')).resolve()
        if not path.is_relative_to(base):
            raise ValueError('Unsafe conversion output path')
        if not path.exists():
            return candidate, path
        i += 1
        if i>10000:
            raise ValueError('No free conversion filename')
