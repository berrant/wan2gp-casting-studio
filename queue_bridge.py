"""Casting Studio -> WanGP session API, without importing Refmod-Fork internals.

Contract: Refmod-Fork fork.58 uses model-declared h3_refmod_state or
flux_refmod_state (JSON strings) and mod identifiers relative to its own
minimax_h3/ or flux2/ directory, without .safetensors.

Fail closed if an installed WanGP model does not declare the setting.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from copy import deepcopy
import logging
from pathlib import Path
from io import BytesIO
from threading import RLock
from typing import Callable
from .workshop_bridge import WorkshopTask, extract_job_settings, read_header
from .conversion_bridge import (is_h3_picture_refmod, ConversionTask, conversion_settings,
                                safetensors_metadata, free_destination)
import json
import math
import re
import uuid
import time


BASE_ARCHITECTURES = {
    "h3_video": {"minimax_h3_ref2va", "minimax_h3_ref2va_pruned"},
    "h3_image": {"minimax_h3_image"},
    "h3_image_pruned": {"minimax_h3_image_pruned"},
    "p_h3_image": {"minimax_p_h3_image"},
    "flux2_dev": {"flux2_dev"},
    "flux2_klein4": {"flux2_klein_4b"},
    "flux2_klein9": {"flux2_klein_9b"},
    "pi_flux2": {"pi_flux2"},
    "flux3_klein": {"flux3_klein", "flux3_klein_base"},
}

SETTING_BY_FAMILY = {"minimax_h3": "h3_refmod_state", "flux2": "flux_refmod_state"}


def finite_progress(value):
    try:
        number=float(value)
    except (TypeError,ValueError,OverflowError):
        return None
    return max(0.0,min(100.0,number)) if math.isfinite(number) else None


def valid_step(value):
    try:
        number=float(value)
    except (TypeError,ValueError,OverflowError):
        return None
    return int(number) if math.isfinite(number) and 0<=number<=1_000_000 and number.is_integer() else None


def _arch(record):
    meta = record.get("metadata") or {}
    return str(meta.get("base_model_type") or record.get("architecture") or record.get("model_type") or "")


def model_matches(record, board_model):
    names = BASE_ARCHITECTURES.get(board_model, set())
    return bool({_arch(record), str(record.get('architecture') or ''),
                 str(record.get('model_type') or '')} & names)


def refmod_identifier(file: Path, root: Path, family: str) -> str:
    """Translate physical file into what Refmod-Fork's storage API loads.

    Use only verified files supplied by RefmodForkAdapter.validate_refmod().
    Refuse spellings that the fork's sanitizers would normalize to *another*
    name: that would cause a silent missing-mod fallback.
    """
    base = root / ('minimax_h3' if family == 'minimax_h3' else 'flux2')
    physical=file.resolve()
    matches=[]
    for category in ('celebs','personal'):
        folder=(base/category).resolve()
        if physical.is_relative_to(folder) and physical!=folder:
            matches.append(category+'/'+physical.relative_to(folder).with_suffix('').as_posix())
    if len(matches)!=1:
        raise ValueError('RefMod must resolve to exactly one public or Personal model folder')
    name=matches[0]
    parts = name.split('/')
    if not parts or parts[0] not in ('celebs', 'personal'):
        raise ValueError('RefMod must be inside celebs/ or personal/ for the selected model family')
    for part in parts:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', part):
            raise ValueError('RefMod filename uses characters that Refmod-Fork would rename; rename the file in its library before generating')
    return name


def selected_custom_settings(family: str, mod_identifier: str, strength: float, use_audio: bool = True) -> dict[str, str]:
    if not 0 < strength <= 2.0:
        raise ValueError('RefMod strength must be between 0 (exclusive) and 2')
    if family == 'minimax_h3':
        data = {"rows": [{"mod": mod_identifier, "strength": strength,
                          "as_video": False, "use_audio": use_audio}],
                "retention": 1.0, "scramble_seed": -1, "curve": None}
    elif family == 'flux2':
        data = {"rows": [{"mod": mod_identifier, "strength": strength}]}
    else:
        raise ValueError('Unknown model family')
    return {SETTING_BY_FAMILY[family]: json.dumps(data, separators=(',', ':'))}


@dataclass
class Submission:
    model: str
    model_type: str
    choice_key: str
    scene: int = 1
    steps: int | None = None
    resolution: str = ''
    seed: int = -1
    strength: float = 1.0
    extra_settings: dict | None = None
    loras: list[dict] | None = None
    video_seconds: int = 15
    video_script_mode: str = 'single'
    sliding: dict | None = None
    window_loras: dict | None = None
    fixed_windows: bool = False
    queue_pass: str = "initial"
    portrait_completion: Callable | None = None
    monitor_details: dict | None = None


class QueueBridge:
    """One queued WanGP session at a time; reports *actual* completion.

    A validating callback returns (prompt, family, physical_refmod_file).
    Run it again in the worker, immediately before submitting: private consent
    could have been revoked after the job was queued.
    """
    def __init__(self, adapter, api_session=None):
        self.adapter = adapter
        self.api_session = api_session
        self.providers: dict = {}
        self.session_error = ""
        # Native iframe requests cannot call WanGP's Gradio API outside a
        # registered Gradio button callback. The pending job is handed off
        # to that callback; the standalone test adapter remains unchanged.
        self.dispatch_mode = 'worker'
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='casting_wangp')
        self._lock = RLock()
        self._jobs: dict[str, dict] = {}
        self._handles: dict[str, object] = {}
        self._pending: list[tuple] = []
        # Latest WanGP preview for each recent job. Bytes stay in RAM rather than
        # private files on disk. Cap each preview and the number of retained jobs.
        self._previews: dict[str, tuple[bytes, str]] = {}
        # Completed output is separate from transient inference media. Only
        # native callback/result paths may enter this bounded registry.
        self._monitor_outputs = {}
        self._monitor_gallery = {}
        self._last_monitor_output = None
        self.history_sink = None
        self.gallery_sink = None

    @property
    def live_session_ready(self):
        # The native tab's injected proxy is valid *inside* Gradio callback
        # events, not inside the separate FastAPI request made by the iframe.
        return bool(self.api_session is not None and (
            self.dispatch_mode == 'gradio' or
            getattr(self.api_session, '_use_webui_queue', False)))

    def _definitions(self):
        provider=self.providers.get('list_model_defs')
        if callable(provider):
            return provider()
        session=self._session()
        return session.list_model_defs()

    def _model_record(self, model_type):
        return next((rec for rec in self._definitions() if
                     isinstance(rec,dict) and rec.get('model_type')==model_type), None)

    def _definition_sources(self, model_type, record=None):
        """Read WanGP's built-in/finetune JSON definitions without editing them.

        Files are provenance and a read-only fallback; the public WanGP factory
        function remains authoritative because handlers can change defaults.
        """
        record = record or self._model_record(model_type) or {}
        base = _arch(record) or model_type
        root = self.adapter.root
        paths = [(root/'defaults'/f'{base}.json', 'defaults'),
                 (root/'finetunes'/f'{model_type}.json', 'finetunes')]
        # A finetune can override a same-named default model, and the file is
        # included only once when the names collapse.
        result = {}
        sources = []
        for path, kind in paths:
            try:
                if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
                    continue
                definition = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(definition, dict):
                    continue
                # Only top-level generation settings; nested 'model' describes
                # weights and should NEVER become submitted generation settings.
                result.update({key: value for key, value in definition.items()
                               if key != 'model'})
                sources.append(f'{kind}/{path.name}')
            except (OSError, UnicodeError, ValueError):
                continue
        return result, sources

    def _factory_defaults(self, model_type):
        record = self._model_record(model_type)
        source_defaults, _ = self._definition_sources(model_type, record)
        provider = self.providers.get('get_factory_settings')
        if callable(provider):
            factory = provider(model_type)
        else:
            factory = self._session().get_default_settings(model_type)
        # WanGP applies default definitions and model-specific handler logic.
        # Its resolved values win over the raw JSON file in every conflict.
        source_defaults.update(dict(factory or {}))
        return source_defaults

    def _lora_catalog(self, model_type, record):
        if record.get('no_lora'):
            return {'supported':False,'loras':[]}
        # The Python API is the authoritative list. In v20.00 the deferred
        # session cannot serve it until tab selection, so use the normal
        # WanGP model-specific LoRA folder as a read-only fallback.
        if self.live_session_ready and hasattr(self.api_session,'list_loras'):
            try:
                result=self.api_session.list_loras(model_type)
                if isinstance(result,dict):return result
            except Exception:
                pass
        provider=self.providers.get('get_lora_dir')
        if not callable(provider):
            return {'supported':False,'loras':[],'reason':'LoRA catalog is unavailable'}
        directory_value=provider(model_type)
        if not directory_value:
            return {'supported':False,'loras':[],'reason':'Model has no LoRA folder'}
        directory=Path(directory_value).resolve()
        if not directory.is_dir():
            return {'supported':True,'loras':[]}
        names=[]
        for file in directory.rglob('*'):
            if (file.is_file() and file.resolve().is_relative_to(directory)
                    and file.suffix.lower() in ('.safetensors','.sft')):
                rel=file.relative_to(directory).as_posix()
                # RefMod weights are a separate type of adapter, never LoRAs.
                if 'refmods_plugin' not in rel.split('/'):
                    names.append(rel)
        return {'supported':True,'loras':sorted(set(names),key=str.casefold)}

    def model_details(self, board_model: str, model_type: str) -> dict:
        model=next((item for item in self.models(board_model) if
                    item['model_type']==model_type),None)
        if model is None or not model['ready']:
            raise ValueError('Select a compatible WanGP model first')
        record=self._model_record(model_type)
        defaults=self._factory_defaults(model_type)
        # WanGP's published resolution presets and its per-model assessment.
        # Do not offer locked/out-of-range sizes merely because they are common.
        try:
            from shared.resolutions import (DEFAULT_RESOLUTION_CHOICES,
                DEFAULT_RESOLUTION_CHOICES_4K, assess_resolution,
                normalize_resolution_choices)
            presets=DEFAULT_RESOLUTION_CHOICES_4K+DEFAULT_RESOLUTION_CHOICES
            custom=normalize_resolution_choices(record.get('resolutions'),'model.resolutions',printer=lambda _:None) or []
            choices=custom+presets
            resolutions=[];seen=set()
            for label,value in choices:
                if value in seen: continue
                assessment=assess_resolution(record,value)
                if assessment['status'] != 'recommended': continue
                # Do not silently offer a different generation mode than selected.
                if assessment.get('settings'): continue
                resolutions.append({'label':label,'value':value})
                seen.add(value)
        except ImportError:
            # Small compatibility fallback for WanGP releases predating the
            # shared resolution API. Still enforce explicit lock lists.
            allowed=record.get('resolutions') or []
            if not record.get('lock_resolutions'):
                allowed+= [('1280x720 (16:9)','1280x720'),('720x1280 (9:16)','720x1280'),
                           ('1024x1024 (1:1)','1024x1024'),('960x544 (16:9)','960x544')]
            resolutions=[]
            for item in allowed:
                val=item[1] if isinstance(item,(list,tuple)) else item
                label=item[0] if isinstance(item,(list,tuple)) else str(item)
                if re.fullmatch(r'[1-9]\d+x[1-9]\d+',str(val)) and str(val) not in [x['value'] for x in resolutions]:
                    resolutions.append({'label':label,'value':str(val)})
        raw_loras=self._lora_catalog(model_type,record)
        _, sources = self._definition_sources(model_type, record)
        return {'model_type':model_type,'resolution_default':str(defaults.get('resolution') or ''),
                'steps_default':defaults.get('num_inference_steps'),
                'seed_default':defaults.get('seed',-1),
                'video_length_default':defaults.get('video_length'),
                'sliding_window_supported':bool(record.get('sliding_window',False)),
                'sliding_window_defaults':{k:defaults.get(k) for k in (
                    'sliding_window_size','sliding_window_overlap',
                    'sliding_window_color_correction_strength',
                    'sliding_window_overlap_noise','sliding_window_discard_last_frames',
                    'sliding_window_trim_first_frames') if defaults.get(k) is not None},
                'defaults_sources':sources,
                'resolutions':resolutions,'loras':raw_loras.get('loras',[]),
                'lora_supported':raw_loras.get('supported',False),
                'default_loras':defaults.get('activated_loras') or [],
                'default_multipliers':defaults.get('loras_multipliers') or ''}

    def _validate_loras(self, submission, model_record):
        requested=submission.loras
        if requested is None:
            return None  # leave WanGP factory defaults untouched
        if not isinstance(requested,list) or len(requested)>32:
            raise ValueError('Choose up to 32 LoRAs')
        catalog=self._lora_catalog(submission.model_type,model_record)
        if requested and not catalog.get('supported'):
            raise ValueError('This model does not support selectable LoRAs')
        available=set(catalog.get('loras',[]))
        names=[];mults=[]
        for entry in requested:
            if not isinstance(entry,dict):raise ValueError('Invalid LoRA selection')
            name=entry.get('name')
            if not isinstance(name,str) or name not in available:
                raise ValueError("Selected LoRA is missing from this model\'s installed LoRA folder")
            if name in names:raise ValueError('Duplicate LoRA selection')
            multiplier=entry.get('multiplier',1.0)
            try:multiplier=float(multiplier)
            except (ValueError,TypeError):raise ValueError('LoRA multiplier must be numeric')
            if not math.isfinite(multiplier) or not -5<=multiplier<=5:
                raise ValueError('LoRA multiplier must be between -5 and 5')
            names.append(name)
            mults.append(format(multiplier,'.4g'))
        return {'activated_loras':names,'loras_multipliers':' '.join(mults)}

    def _session(self):
        if self.api_session is None:
            raise RuntimeError('WanGP has not injected its queue API; restart WanGP after enabling the plugin')
        return self.api_session

    def _apply_window_lora_multipliers(self, prompt, submission, lora_settings):
        overrides=submission.window_loras or {}
        if not overrides:return prompt
        if submission.model!='h3_video' or submission.video_seconds<=15 or submission.video_script_mode!='sequence':
            raise ValueError('Window LoRA overrides require long-video sequence mode')
        if not isinstance(overrides,dict) or not lora_settings:
            raise ValueError('Window overrides require selected LoRAs')
        names=lora_settings['activated_loras']
        if set(overrides)-set(names):raise ValueError('Window override references an unselected LoRA')
        base=[float(v) for v in lora_settings['loras_multipliers'].split()]
        segments=prompt.split('\n\n')
        count=(submission.video_seconds+14)//15
        if len(segments)!=count:raise ValueError('Window prompt count does not match the requested sequence')
        for name,values in overrides.items():
            if not isinstance(values,list) or len(values)>count:raise ValueError('Invalid LoRA window count')
            for raw in values:
                if raw is None:continue
                if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) or not -5<=raw<=5:
                    raise ValueError('Window multiplier must be numeric and between -5 and 5')
        result=[]
        for idx,segment in enumerate(segments):
            mults=[overrides.get(name,[])[idx] if idx<len(overrides.get(name,[])) and overrides[name][idx] is not None else base[i] for i,name in enumerate(names)]
            command='[/loras_mult='+' '.join(format(v,'.4g') for v in mults)+']'
            if '[/loras_mult=' in segment:raise ValueError('Remove manually embedded LoRA commands before using window controls')
            result.append(command+' '+segment)
        return '\n\n'.join(result)

    def fixed_window_plan(self, submission):
        """One explicit duration per script paragraph; keep within window size.

        The current upstream explicit scheduler budgets discarded frames in each
        window (including the last). Model alignment is handled by WanGP.
        """
        if not getattr(submission,'fixed_windows',False):return None
        if submission.model!='h3_video' or submission.video_seconds not in (30,45,60) or submission.video_script_mode!='sequence':
            raise ValueError('Fixed windows require a 2–4 window H3 video sequence')
        if not self._model_record(submission.model_type).get('sliding_window',False):
            raise ValueError('Selected WanGP model does not declare sliding-window support')
        opts=submission.sliding or {}
        vals=[]
        for key,default,low,high in [('sliding_window_size',362,80,3000),('sliding_window_overlap',18,0,1500),('sliding_window_discard_last_frames',8,0,200)]:
            raw=opts.get(key,default)
            if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw) or int(raw)!=raw or not low<=raw<=high:
                raise ValueError(f'{key} must be a whole number between {low} and {high}')
            vals.append(int(raw))
        size,overlap,discard=vals
        if size<=overlap+discard:raise ValueError('Window size must exceed overlap plus discarded tail frames')
        n=submission.video_seconds//15
        return [size-discard]+[size-overlap-discard]*(n-1)

    def apply_fixed_window_plan(self,prompt,submission):
        durations=self.fixed_window_plan(submission)
        if durations is None:return prompt
        segments=prompt.split('\n\n')
        if len(segments)!=len(durations) or any(not x.strip() for x in segments):
            raise ValueError('Keep exactly one prompt paragraph per sliding window')
        if any(re.search(r'(?i)\[\s*/[^\]]*?(?:/|,)\s*(?:duration|overlap|new_shot)\b',x) or re.search(r'(?i)\[\s*/\s*(?:duration|overlap|new_shot)\b',x) for x in segments):
            raise ValueError('Window duration and overlap are controlled by the sliding-window settings; remove conflicting prompt commands')
        return '\n\n'.join(f'[/duration={frames}] '+part for frames,part in zip(durations,segments))

    def models(self, board_model: str) -> list[dict]:
        if board_model not in BASE_ARCHITECTURES:
            raise ValueError('Unknown Casting Studio model')
        fork = self.adapter.discover()
        if not fork.get('installed'):
            raise RuntimeError('Refmod-Fork was not detected. Install or enable the jedsdead Refmod-Fork plugin before queue submission')
        if not fork.get('supported_models', {}).get(board_model):
            raise RuntimeError(f'Refmod-Fork {fork.get("version") or "unknown"} does not declare compatibility with {board_model}')
        records = self._definitions()
        out = []
        for rec in records:
            if not isinstance(rec, dict) or not model_matches(rec, board_model):
                continue
            mt = str(rec.get('model_type') or '')
            if not mt:continue
            family = 'flux2' if board_model.startswith('flux') or board_model == 'pi_flux2' else 'minimax_h3'
            key = SETTING_BY_FAMILY[family]
            declared = any(isinstance(s, dict) and s.get('id') == key for s in (rec.get('custom_settings') or []))
            out.append({'model_type': mt, 'name': rec.get('name') or mt,
                        'architecture': _arch(rec), 'ready': declared,
                        'issue': '' if declared else f'Missing {key}: Refmod-Fork patch not active for this model'})
        out.sort(key=lambda row: (not row['ready'], 0 if board_model=='h3_video' and row['model_type']=='minimax_h3_ref2va_pruned' else 1, row['name']))
        return out

    def _video_settings(self,submission,data):
        if submission.model == 'h3_video':
            seconds=int(submission.video_seconds)
            if seconds not in (15,30,45,60):
                raise ValueError('Video duration must be 15, 30, 45 or 60 seconds')
            if submission.video_script_mode not in ('single','sequence'):
                raise ValueError('Unknown sliding-window script mode')
            if seconds>15 and not self._model_record(submission.model_type).get('sliding_window', False):
                raise ValueError('Selected WanGP model does not declare sliding-window support')
            fixed=self.fixed_window_plan(submission)
            data['video_length']=sum(fixed) if fixed is not None else f'{seconds}s'
            if seconds>15:
                from numbers import Real
                sliding=submission.sliding or {}
                if fixed is not None:
                    sliding={'sliding_window_size':362,'sliding_window_overlap':18,'sliding_window_discard_last_frames':8,**sliding}
                if not isinstance(sliding,dict):raise ValueError('Sliding-window options must be an object')
                spec={
                    'sliding_window_size':(80,3000,int),
                    'sliding_window_overlap':(0,1500,int),
                    'sliding_window_color_correction_strength':(0,1,float),
                    'sliding_window_overlap_noise':(0,100,int),
                    'sliding_window_discard_last_frames':(0,200,int),
                    'sliding_window_trim_first_frames':(0,200,int),
                }
                if set(sliding)-set(spec):raise ValueError('Unsupported sliding-window setting')
                for key,value in sliding.items():
                    low,high,typ=spec[key]
                    if isinstance(value,bool):raise ValueError(f'{key} must be numeric')
                    try:converted=typ(value)
                    except (TypeError,ValueError,OverflowError):raise ValueError(f'{key} must be numeric')
                    if (typ is int and float(value)!=converted) or not math.isfinite(converted) or not low<=converted<=high:
                        raise ValueError(f'{key} must be between {low} and {high}')
                    data[key]=converted
                window_size=int(data.get('sliding_window_size') or 0)
                overlap=int(data.get('sliding_window_overlap') or 0)
                discarded=int(data.get('sliding_window_discard_last_frames') or 0)
                if not window_size or overlap+discarded>=window_size:
                    raise ValueError('Window size must exceed overlap plus discarded tail frames')
                data['multi_prompts_gen_type']='PW' if submission.video_script_mode=='sequence' else 'FG'
            else:
                data['multi_prompts_gen_type']='FG'

    def prepare(self, submission: Submission, validate: Callable) -> dict:
        model_items = self.models(submission.model)
        found = next((x for x in model_items if x['model_type'] == submission.model_type), None)
        if not found:
            raise ValueError('WanGP model not in supported architecture list; refresh the model picker')
        if not found['ready']:
            raise ValueError(found['issue'])
        session = self._session()
        prompt, family, physical_path = validate(submission)
        name = refmod_identifier(physical_path, self.adapter.refmod_root, family)
        setting = SETTING_BY_FAMILY[family]
        custom = selected_custom_settings(family, name, submission.strength, use_audio=submission.model=='h3_video')
        if len(prompt) < 12:
            raise ValueError('Generated prompt is empty')
        # Refmod-Fork itself uses merge_settings_with_defaults before submitting.
        data = dict(submission.extra_settings or {})
        if {'activated_loras','loras_multipliers'} & set(data):
            raise ValueError('Configure LoRAs in the LoRA picker rather than advanced JSON')
        lora_settings=self._validate_loras(submission, self._model_record(submission.model_type))
        prompt=self._apply_window_lora_multipliers(prompt, submission, lora_settings)
        prompt=self.apply_fixed_window_plan(prompt,submission)
        if hasattr(submission,'_reviewed_native_prompt') and prompt!=submission._reviewed_native_prompt:
            raise ValueError('Native prompt transformation changed after review; review the task again')
        if lora_settings is not None:
            data.update(lora_settings)
        disallowed = {'model_type','prompt','custom_settings','image_refs','video_guide','image_start','image_end',
                      'video_length','multi_prompts_gen_type','sliding_window_size','sliding_window_overlap',
                      'sliding_window_overlap_noise','sliding_window_color_correction_strength',
                      'sliding_window_discard_last_frames','sliding_window_trim_first_frames'}
        if disallowed & set(data):
            raise ValueError('Advanced settings may not override identity, prompt, media references or RefMod payload')
        data.update({'model_type':submission.model_type, 'prompt':prompt, 'seed':submission.seed})
        self._video_settings(submission,data)
        if submission.steps is not None:
            if not 1 <= submission.steps <= 100:
                raise ValueError('Steps must be between 1 and 100')
            data['num_inference_steps'] = submission.steps
        if submission.resolution:
            import re
            if not re.fullmatch(r'[1-9][0-9]{1,4}x[1-9][0-9]{1,4}',submission.resolution):
                raise ValueError('Resolution must be WxH, e.g. 1280x720')
            data['resolution'] = submission.resolution
        merged = session.merge_settings_with_defaults(data)
        # merge defaults should not silently change the selected LoRA stack.
        if lora_settings is not None:
            merged.update(lora_settings)
        merged['model_type'] = submission.model_type
        merged['prompt'] = prompt
        if submission.portrait_completion is not None and submission.model == 'h3_video':raise ValueError('Portrait requires an image model')
        # Each reviewed casting task maps to one native generation.
        merged.update(batch_size=1, repeat_generation=1)
        # Defaults/previous synced data may include stale RefMod settings; replace,
        # never merge a prior identity into this casting selection.
        merged['custom_settings'] = {k:v for k,v in (merged.get('custom_settings') or {}).items()
                                     if k not in SETTING_BY_FAMILY.values()}
        merged['custom_settings'].update(custom)
        if setting not in merged['custom_settings']:
            raise ValueError('RefMod payload was lost during settings normalization')
        return {'settings': merged, 'refmod':name, 'model_type':submission.model_type,
                'prompt':prompt, 'family':family, 'monitor_details':{**(submission.monitor_details or {}), 'prompt':prompt, 'scene':submission.scene, 'model_type':submission.model_type}}

    def preflight(self, submission: Submission, validate: Callable) -> None:
        """Safe side-effect-free validation from the FastAPI request thread.

        The injected Gradio session can only merge defaults and submit while a
        native Gradio event is running. Revalidate *everything* in prepare()
        when that event runs, especially Personal consent and RefMod paths.
        """
        models = self.models(submission.model)
        selected = next((m for m in models if m['model_type']==submission.model_type),None)
        if not selected or not selected['ready']:
            raise ValueError(selected['issue'] if selected else 'Unsupported WanGP model')
        prompt, family, file = validate(submission)
        refmod_identifier(file, self.adapter.refmod_root, family)
        if len(prompt) < 12:
            raise ValueError('Generated prompt is empty')
        selected_custom_settings(family, 'celebs/valid', submission.strength)
        if submission.steps is not None and not 1 <= submission.steps <= 100:
            raise ValueError('Steps must be between 1 and 100')
        if submission.resolution and not re.fullmatch(r'[1-9][0-9]{1,4}x[1-9][0-9]{1,4}',submission.resolution):
            raise ValueError('Resolution must be WxH')
        extra = submission.extra_settings or {}
        disallowed={'model_type','prompt','custom_settings','image_refs','video_guide','image_start','image_end',
                    'activated_loras','loras_multipliers','video_length','multi_prompts_gen_type','sliding_window_size','sliding_window_overlap',
                    'sliding_window_overlap_noise','sliding_window_color_correction_strength','sliding_window_discard_last_frames','sliding_window_trim_first_frames'}
        if not isinstance(extra,dict) or (disallowed & set(extra)):
            raise ValueError('Advanced settings contain reserved keys and may not override generation identity or model settings')
        settings=self._validate_loras(submission, self._model_record(submission.model_type))
        self.apply_fixed_window_plan(self._apply_window_lora_multipliers(prompt,submission,settings),submission)
        self._video_settings(submission,{})

    @staticmethod
    def _history_settings(submission):
        # The history is local runtime data. Do not copy prompt, identity, paths,
        # callbacks or private portrait metadata into history records.
        return {f.name:deepcopy(getattr(submission,f.name)) for f in fields(Submission)
                if f.name not in ('choice_key','portrait_completion','monitor_details')}

    def _register_cast_history(self,job_id,submissions,validate):
        if any(s.portrait_completion is not None for s in submissions):return
        with self._lock:
            item=self._jobs[job_id]
            item['_monitor_history_settings']=self._history_settings(submissions[0])
            item['_monitor_history_labels']=[{k:d[k] for k in ('person','character','production','kind','scene') if k in d} for sub in submissions if isinstance(d:=getattr(sub,'monitor_details',None),dict) and not d.get('personal')][:100]
            item['_monitor_retry_source']=(list(submissions),validate)
            item['failed_task_indices']=[]
        self._persist_cast_history(job_id)

    def _persist_cast_history(self,job_id):
        if not callable(self.history_sink):return
        with self._lock:
            item=self._jobs.get(job_id,{})
            if '_monitor_history_settings' not in item:return
            record={k:deepcopy(item[k]) for k in ('id','state','message','model_type','total_tasks','failed_task_indices','retried_as') if k in item}
            record['settings']=deepcopy(item['_monitor_history_settings'])
            record['tasks']=deepcopy(item.get('_monitor_history_labels',[]))
            record['task_count']=item.get('total_tasks',1)
            record['output_count']=len(item.get('files') or [])
            # Store only explicitly failed tasks, never infer failed or skipped work.
            if record.get('state')=='failed' and not record.get('retried_as'):
                source=item.get('_monitor_retry_source',([],None))[0]
                snapshots=[]
                for i in record.get('failed_task_indices',[]):
                    if type(i) is not int or not 1<=i<=len(source):continue
                    sub=source[i-1];snap=getattr(sub,'_retry_snapshot',None)
                    if isinstance(snap,dict):snapshots.append({'index':i,'settings':{**self._history_settings(sub),'choice_key':sub.choice_key},'snapshot':deepcopy(snap)})
                if len(snapshots)==len(record.get('failed_task_indices',[])) and snapshots:record['_retry_tasks']=snapshots
                record['_retry_batch']=bool(item.get('batch'))
        try:self.history_sink(record)
        except Exception:logging.getLogger(__name__).exception('Casting Studio could not write local batch history')

    def retryable_indices(self,job_id):
        with self._lock:
            item=self._jobs.get(job_id,{})
            if item.get('state')!='failed' or item.get('retried_as') or item.get('_monitor_retry_busy') or not item.get('_monitor_retry_source'):return []
            return list(item.get('failed_task_indices') or [])

    def retry_failed(self,job_id):
        with self._lock:
            indices=self.retryable_indices(job_id)
            if not indices:raise ValueError('No confirmed failed tasks are available to retry in this WanGP process')
            item=self._jobs[job_id]
            source,validate=item['_monitor_retry_source']
            chosen=[deepcopy(source[i-1]) for i in indices]
            item['_monitor_retry_busy']=True
        try:
            # Preserve the original prompt snapshot, model, seed and LoRA settings.
            # The original validator still rechecks live consent and RefMod paths.
            new_id=self.enqueue_batch(chosen,validate) if item.get('batch') else self.enqueue(chosen[0],validate)
            with self._lock:item['retried_as']=new_id
            self._persist_cast_history(job_id)
            return new_id,len(chosen)
        finally:
            with self._lock:item.pop('_monitor_retry_busy',None)

    @staticmethod
    def _confirmed_failures(result,offset,size,output_indices):
        # WanGP GenerationError.task_index is one-based. Never infer failure
        # from the current progress index, missing outputs, or skipped chunks.
        if getattr(result,'cancelled',False) or getattr(result,'success',False):return []
        errors=getattr(result,'errors',None) or []
        failed=set()
        for e in errors:
            i=getattr(e,'task_index',None)
            if type(i) is not int or not 1<=i<=size:return []
            if not getattr(e,'cancelled',False):failed.add(offset+i)
        reported=getattr(result,'failed_tasks',None)
        if reported is not None and (type(reported) is not int or reported!=len(failed)):return []
        return sorted(failed-set(output_indices))

    def enqueue(self, submission: Submission, validate: Callable) -> str:
        # From FastAPI, never call the injected session's queue/Gradio APIs.
        # A native Gradio button event performs the final prepare+submission.
        if self.dispatch_mode == 'gradio':
            if self.api_session is None:
                raise RuntimeError('WanGP native tab has no injected API session')
            self.preflight(submission, validate)
        else:
            self.prepare(submission, validate)
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {'id':job_id,'state':'queued','message':('Waiting for Casting Studio native queue trigger' if self.dispatch_mode=='gradio' else 'Waiting for the WanGP queue'),
                                  '_monitor_cast':True,'model_type':submission.model_type,'scene':submission.scene,
                                  'files':[], 'error':''}
        self._register_cast_history(job_id,[submission],validate)
        if self.dispatch_mode == 'gradio':
            with self._lock:
                self._pending.append((job_id, submission, validate))
        else:
            self._executor.submit(self._run, job_id, submission, validate)
        return job_id

    def enqueue_batch(self, submissions: list[Submission], validate: Callable) -> str:
        """Stage an atomic batch for one native Gradio click/manifest submission.

        Preflight every task before accepting it. The native callback repeats
        all validations immediately before passing a manifest to WanGP.
        """
        if self.dispatch_mode != 'gradio' or not self.live_session_ready:
            raise RuntimeError('Bulk queue requires the active WanGP native Gradio relay')
        if not callable(getattr(self.api_session, 'submit_manifest', None)):
            raise RuntimeError('The active WanGP session does not expose submit_manifest(); bulk queue is unavailable with this WanGP version')
        if not submissions or len(submissions)>2000:
            raise ValueError('Batch must contain between 1 and 2000 tasks')
        for task in submissions:
            self.preflight(task,validate)
        batch_id=uuid.uuid4().hex
        with self._lock:
            self._jobs[batch_id]={'id':batch_id,'state':'queued',
                'message':f'{len(submissions)} tasks staged for one native WanGP manifest',
                '_monitor_cast':True,'total_tasks':len(submissions),'files':[],'error':'',
                'model_type':submissions[0].model_type,'scene':0,'batch':True}
        self._register_cast_history(batch_id,submissions,validate)
        with self._lock:self._pending.append((batch_id,list(submissions),validate))
        return batch_id

    def _run_batch(self,job_id, submissions, validate):
        """Run large image sets as sequential, bounded WanGP manifests.

        A batch stays one Casting Studio job. The native Gradio callback owns
        every submit_manifest call; neither FastAPI nor a background thread
        accesses the live Gradio API. No jobs can run until all preflight
        validations (including consent) have passed.
        """
        all_files=[]
        try:
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancelled before preparation')
                return
            prepared=[]
            for task in submissions:
                if self._cancelled(job_id):
                    self._change(job_id,state='cancelled',message='Cancelled during batch preparation');return
                prepared.append(self.prepare(task,validate))
            settings_list=[x['settings'] for x in prepared]
            count=len(settings_list)
            self._change(job_id,state='running',message=f'Submitting {count} individually prompted tasks to WanGP', task_index=1, _monitor_cast=True, _monitor_tasks=[x.get('monitor_details') for x in prepared])
            confirmed_aborts=0
            # Prevent oversized manifests from consuming excessive memory or
            # exceeding WanGP's practical per-call task capacities.
            chunk_size=250
            for offset in range(0,count,chunk_size):
                # A long-running earlier manifest may outlive consent, model
                # links or a casting choice. Revalidate later chunks before
                # submitting, but retain the already reviewed settings.
                if offset:
                    for task in submissions[offset:offset+chunk_size]:
                        validate(task)
                with self._lock:
                    if self._jobs[job_id].get('cancel_requested'):
                        self._change(job_id,state='cancelled',message='Batch cancellation requested; remaining chunks not submitted',files=all_files)
                        return
                self._advance_batch_task(job_id, offset+1, count)
                chunk=settings_list[offset:offset+chunk_size]
                chunk_total=len(chunk)
                outer=self
                def mapped_text(msg, base_offset=offset):
                    text=str(msg or '')
                    if len(text)>2048:return 'Task 0/0'
                    def replace(match):
                        if len(match.group(2))>6 or len(match.group(3))>6:return 'Task 0/0'
                        if int(match.group(3))!=min(250,count-base_offset):return 'Task 0/0'
                        return f'{match.group(1)} {base_offset+int(match.group(2))}/{count}'
                    return re.sub(r'\b(prompt|task)\s+(\d+)\s*/\s*(\d+)\b',replace,text,flags=re.I)
                class OffsetUpdate:
                    def __init__(self, raw, base_offset=offset):self.raw=raw;self.base_offset=base_offset
                    def __getattr__(self, name):
                        if name=='task_index':
                            index=getattr(self.raw,name,None)
                            try:return self.base_offset+int(index) if index is not None else None
                            except (TypeError,ValueError,OverflowError):return None
                        if name=='task_count':return count
                        if name=='status':return mapped_text(getattr(self.raw,'status',''),self.base_offset)
                        return getattr(self.raw,name)
                class Callbacks:
                    def __init__(self, base_offset=offset, size=chunk_total):
                        self.base_offset=base_offset;self.size=size
                    def is_current_chunk(self):
                        current=outer.status(job_id) or {}
                        return current.get('state')=='running' and self.base_offset < int(current.get('task_index') or 1) <= self.base_offset+self.size
                    def accepts_task_event(self, update=None, text=''):
                        # Caller holds the board lock through validation and update.
                        if not self.is_current_chunk():return False
                        current=int(outer._jobs[job_id].get('task_index') or 1)
                        marked=re.search(r'\b(?:prompt|task)\s+(\d+)\s*/\s*(\d+)\b',str(text),re.I)
                        indices=[]
                        if marked:
                            if int(marked.group(2))!=count:return False
                            indices.append(int(marked.group(1)))
                        reported=getattr(update,'task_index',None)
                        if reported is not None:indices.append(max(self.base_offset+1,reported))
                        return all(current<=i<=self.base_offset+self.size for i in indices) and len(set(indices))<=1
                    def on_status(self,msg):
                        if not msg:return
                        text=mapped_text(msg,self.base_offset)
                        with outer._lock:
                            if not self.accepts_task_event(text=text):return
                            outer._observe_batch_status(job_id,text)
                            outer._change(job_id,message=text[:500])
                    def raw_metadata_valid(self,update):
                        try:
                            idx=getattr(update,'task_index',None); total=getattr(update,'task_count',None)
                            return (idx is None or 0<=int(idx)<=self.size) and (total is None or int(total)==self.size)
                        except (ValueError,TypeError,OverflowError):return False
                    def on_progress(self,update):
                        if not self.raw_metadata_valid(update):return
                        wrapper=OffsetUpdate(update,self.base_offset)
                        with outer._lock:
                            if not self.accepts_task_event(wrapper,wrapper.status):return
                            outer._observe_batch_progress(job_id,wrapper)
                            outer._remember_native_task(job_id,wrapper)
                            progress=finite_progress(getattr(update,'progress',None))
                            overall=(self.base_offset + progress/100*self.size)/count*100 if progress is not None else None
                            outer._change(job_id,progress=overall,
                                current_step=getattr(update,'current_step',None),
                                total_steps=getattr(update,'total_steps',None))
                    def on_preview(self,update):
                        if self.raw_metadata_valid(update) and self.is_current_chunk():outer._store_preview(job_id,OffsetUpdate(update,self.base_offset))
                    def on_output(self,data):
                        if self.is_current_chunk():outer._observe_native_output(job_id,data)
                # Each chunk completes before the next is submitted. This
                # preserves queue ordering and keeps the native callback bound
                # to the WanGP session for the entire operation.
                job=self._session().submit_manifest(chunk,callbacks=Callbacks())
                with self._lock:
                    self._handles[job_id]=job
                    self._register_native_ids(job_id,job,offset)
                    # Resolve public methods inside the native Gradio callback;
                    # the HTTP Abort endpoint must not resolve the session proxy.
                    try:
                        queue_ops=(getattr(self._session(),'list_queue',None),getattr(self._session(),'cancel_queue_task',None))
                    except (RuntimeError,AttributeError):queue_ops=(None,None)
                    self._jobs[job_id]['_monitor_queue_ops']=queue_ops
                    cancelled_during_submit=self._jobs[job_id].get('cancel_requested')
                if cancelled_during_submit:
                    try:job.cancel()
                    except Exception:pass  # Native task may already be finished; never submit another chunk.
                result=job.result()
                with self._lock:
                    self._handles.pop(job_id,None)
                    self._jobs[job_id].pop('_monitor_queue_ops',None)
                files=[str(x) for x in (getattr(result,'generated_files',None) or [])]
                all_files.extend(files)
                for path in files:
                    if Path(path).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.webm'):
                        self._record_monitor_output(job_id,path,None,from_result=True)
                errors=[str(getattr(e,'message',e)) for e in (getattr(result,'errors',None) or [])]
                skipped=self._jobs[job_id].get('_monitor_skipped',set())
                raw_errors=getattr(result,'errors',None) or []
                expected_skips=bool(raw_errors) and all(getattr(e,'cancelled',False) and isinstance(getattr(e,'task_index',None),int) and offset+e.task_index in skipped for e in raw_errors)
                if expected_skips:confirmed_aborts+=len({e.task_index for e in raw_errors})
                if self._jobs[job_id].get('cancel_requested'):
                    self._change(job_id,state='cancelled',message='Batch cancellation requested; remaining chunks not submitted',files=all_files)
                    return
                if (getattr(result,'cancelled',False) or not getattr(result,'success',False) or errors) and not expected_skips:
                    with self._lock:output_indices=self._jobs[job_id].get('_monitor_output_indices',set()).copy()
                    confirmed=self._confirmed_failures(result,offset,chunk_total,output_indices)
                    self._change(job_id,state='cancelled' if getattr(result,'cancelled',False) else 'failed',
                                 failed_task_indices=confirmed, message=f'Manifest stopped after {offset+chunk_total}/{count} tasks',
                                 files=all_files,error='; '.join(errors) or 'WanGP reported a failed batch')
                    return
                self._change(job_id,progress=(offset+chunk_total)/count*100,
                             task_index=min(count,offset+chunk_total),
                             message=f'Completed batch chunk: {offset+chunk_total}/{count} tasks')
            self._change(job_id,state='cancelled' if confirmed_aborts==count else 'completed',message=f'Manifest finished: {count-confirmed_aborts}/{count} tasks completed'+(f' · {confirmed_aborts} aborted' if confirmed_aborts else ''),
                         files=all_files,progress=100,task_index=count)
        except Exception as exc:
            self._change(job_id,state='cancelled' if self._cancelled(job_id) else 'failed',message='Bulk queue submission stopped',files=all_files,error=str(getattr(exc,'detail',exc))[:900])
        finally:
            with self._lock:
                self._handles.pop(job_id,None)
                self._jobs.get(job_id,{}).pop('_monitor_queue_ops',None)

    def process_pending_in_gradio(self, api_session) -> str:
        """Called only by a registered native gr.Button.click callback.

        WanGP's injected Gradio session wraps this click to hand the job into
        the real main queue. Do not call from FastAPI or a background thread.
        """
        with self._lock:
            if not self._pending:
                return 'No casting jobs are waiting.'
            job_id, submission, validate = self._pending.pop(0)
        self.api_session = api_session
        if isinstance(submission,list):
            self._run_batch(job_id,submission,validate)
        elif isinstance(submission, WorkshopTask):
            self._run_workshop(job_id,submission,validate)
            if (self.status(job_id) or {}).get('state')=='completed' and callable(getattr(submission,'test_portrait',None)):
                try:
                    test_sub,test_validate=submission.test_portrait()
                    self.preflight(test_sub,test_validate)
                    test_id=uuid.uuid4().hex
                    with self._lock:
                        self._jobs[test_id]={'id':test_id,'state':'queued','message':'Workshop test portrait','model_type':test_sub.model_type,'scene':1,'files':[],'error':''}
                        self._jobs[job_id].update(test_portrait_job=test_id,test_portrait_state='running')
                    self._run(test_id,test_sub,test_validate)
                    result=self.status(test_id) or {}
                    with self._lock:self._jobs[job_id].update(test_portrait_state=result.get('state','failed'),test_portrait_error=result.get('error',''))
                except Exception as exc:
                    with self._lock:self._jobs[job_id].update(test_portrait_state='failed',test_portrait_error=str(getattr(exc,'detail',exc))[:500])
        elif isinstance(submission, ConversionTask):
            self._run_conversion(job_id,submission,validate)
        else:
            self._run(job_id, submission, validate)
        item = self.status(job_id)
        return f"Casting Studio {job_id[:8]}: {item['state']} — {item.get('message','')}" if item else 'Casting Studio: job history expired'

    def _change(self, job_id, **changes):
        if 'progress' in changes:
            progress=finite_progress(changes['progress'])
            if progress is None:changes.pop('progress')
            else:changes['progress']=progress
        for key in ('current_step','total_steps'):
            if key in changes:changes[key]=valid_step(changes[key])
        persist=False
        with self._lock:
            current=self._jobs.get(job_id)
            # Late native callbacks may arrive after the result is committed.
            if current is not None and (current.get('state') not in ('completed','failed','cancelled','partial') or (changes=={'applied':True} and current.get('operation')=='auto_convert')):
                persist=bool(changes.get('state') and changes['state']!=current.get('state'))
                current.update(changes)
                if changes.get('state') in ('completed','failed','cancelled','partial'):
                    self._previews.pop(job_id,None)
                    # Move completed entries to the end, independent of submission order.
                    self._jobs[job_id]=self._jobs.pop(job_id)
                    terminal=[key for key,item in self._jobs.items() if item.get('state') in ('completed','failed','cancelled','partial')]
                    for old in terminal[:-100]:
                        self._jobs.pop(old,None)
                        self._previews.pop(old,None)
        if persist:self._persist_cast_history(job_id)

    def _cancelled(self,job_id):
        with self._lock:
            item=self._jobs.get(job_id,{})
            return bool(item.get('cancel_requested') or item.get('state')=='cancelled')

    def _attach_handle(self,job_id,handle,register=False):
        with self._lock:
            self._handles[job_id]=handle
            if register:self._register_native_ids(job_id,handle,0)
            cancelled=self._cancelled(job_id)
        if cancelled:
            try:handle.cancel()
            except Exception:pass # Native task may already have ended; do not proceed to another operation.

    def _observe_batch_status(self, job_id, msg):
        # Status can lead progress (e.g. "Prompt 2/3 - Encoding Prompt").
        matched = re.search(r'\b(?:prompt|task)\s+(\d+)\s*/\s*(\d+)\b', str(msg)[:2048], re.I)
        if matched:
            self._advance_batch_task(job_id, int(matched.group(1)), int(matched.group(2)))

    def _observe_batch_progress(self, job_id, update):
        index = getattr(update, 'task_index', None)
        count = getattr(update, 'task_count', None)
        if index is not None:
            try:
                index = int(index)
                # WanGP's API uses 1-based task numbers; tolerate 0 for first.
                self._advance_batch_task(job_id, max(1, index), int(count) if count is not None else None)
            except (ValueError, TypeError, OverflowError):
                pass
        self._observe_batch_status(job_id, getattr(update, 'status', '') or '')

    def _advance_batch_task(self, job_id, new_index, total=None):
        """Drop prior-task preview bytes immediately when a manifest advances.

        The per-job preview endpoint must never serve a stale frame after a
        progress event announces the next task.
        """
        with self._lock:
            current = self._jobs.get(job_id)
            if not current or not current.get('batch') or current.get('state')!='running':
                return
            count = int(current.get('total_tasks') or 0)
            if new_index < 1 or (count and new_index > count):
                return
            if total is not None and count and total != count:
                return
            old = int(current.get('task_index') or 1)
            if new_index <= old:
                return
            self._previews.pop(job_id, None)
            current.pop('_preview_last',None)
            current.pop('_monitor_activity',None)
            current.update(task_index=new_index, preview_rev=0,
                           preview_kind='', preview_task_index=None,
                           current_step=None, total_steps=None, progress=0, preview_step=None, preview_total_steps=None, abort_requested=False, native_task_active=False)

    def set_preview_interest(self, job_id, enabled):
        """Browser opts in to preview capture only while its monitor is open.

        An expiring lease prevents expensive callbacks after a browser closes.
        Legacy API clients that don't supply a preference retain old behavior.
        """
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:return
            current['_preview_until'] = time.monotonic()+10 if enabled else 0
            if not enabled:
                self._previews.pop(job_id, None)
                current.update(preview_kind='', preview_task_index=None)
                current.pop('_preview_last', None)

    def _store_preview(self, job_id, update):
        """Accept WanGP PreviewUpdate (PIL frame and/or Tiny VAE MP4).

        Only bounded bytes are exposed to the embedded UI, never an arbitrary
        filesystem path or a preview from another queued job.
        """
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None or current.get('state')!='running' or current.get('abort_requested') or current.get('cancel_requested'):
                return
            captured_task = int(current.get('task_index') or 1)
            now=time.monotonic()
            interested=current.get('_preview_until')
            if interested is not None and (now>=interested or now-current.get('_preview_last',-1000)<1.25):
                return
        # All supplied task identifiers must agree; do not trust one over another.
        status_text=str(getattr(update, 'status', '') or '')
        if len(status_text)>2048:return
        marked = re.search(r'\b(?:prompt|task)\s+(\d+)\s*/\s*(\d+)\b',status_text,re.I)
        index=getattr(update,'task_index',None)
        reported_count=getattr(update,'task_count',None)
        try:
            expected_count=current.get('total_tasks') if current.get('batch') else None
            if marked and (int(marked.group(1))!=captured_task or (expected_count and int(marked.group(2))!=expected_count)):return
            if index is not None and max(1,int(index))!=captured_task:return
            if reported_count is not None and expected_count and int(reported_count)!=expected_count:return
        except (TypeError,ValueError,OverflowError):return
        payload = None
        mime = None
        video = getattr(update, 'video', None)
        if isinstance(video, bytes) and 0 < len(video) <= 30_000_000:
            payload, mime = video, 'video/mp4'
        if payload is None:
            frame = getattr(update, 'image', None)
            if frame is not None:
                try:
                    # Do not let callbacks retain massive VAE tensors/images.
                    frame = frame.copy()
                    frame.thumbnail((1280, 1280))
                    out = BytesIO()
                    frame.convert('RGB').save(out, format='JPEG', quality=83)
                    if len(out.getvalue()) <= 5_000_000:
                        payload, mime = out.getvalue(), 'image/jpeg'
                except (AttributeError, OSError, ValueError):
                    pass
        if payload is None:
            return
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None or current.get('state')!='running' or current.get('abort_requested') or current.get('cancel_requested') or int(current.get('task_index') or 1) != captured_task:
                return  # The next task began while we were encoding this preview.
            if '_preview_until' in current and time.monotonic()>=current['_preview_until']:return
            current['_preview_last']=time.monotonic()
            current['_monitor_activity']=max(now,current.get('_monitor_activity',now))
            self._previews[job_id] = (payload, mime)
            # Bound memory use even after many casting submissions.
            for old in list(self._previews)[:-8]:
                self._previews.pop(old, None)
            current = self._jobs[job_id]
            current['preview_kind'] = 'video' if mime == 'video/mp4' else 'image'
            current['preview_task_index'] = captured_task
            current['preview_rev'] = current.get('preview_rev', 0) + 1
            step=valid_step(getattr(update,'current_step',None))
            phase=getattr(update,'phase',None)
            current['preview_step']=step if phase in (None,'inference') else None
            current['preview_total_steps']=(valid_step(getattr(update,'total_steps',None)) or valid_step(current.get('total_steps'))) if phase in (None,'inference') else None
            progress=finite_progress(getattr(update,'progress',None))
            if progress is not None and not current.get('batch'):
                current['progress']=progress

    def preview(self, job_id, task_index=None, revision=None):
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or item.get('state')!='running' or item.get('abort_requested') or item.get('cancel_requested'):return None
            if revision is not None and item.get('preview_rev')!=revision:return None
            if task_index is not None and (item.get('state')!='running' or item.get('preview_task_index')!=task_index or int(item.get('task_index') or 1)!=task_index):return None
            return self._previews.get(job_id)

    def monitor_status(self, job_id, live_preview=None):
        """Follow live casting work, not the most recently staged request.

        Native submission may mark several jobs running before GPU work starts.
        Prefer observed native activity; otherwise use submission order. Never
        select conversion/analysis/Workshop jobs or expose unrelated native jobs.
        """
        with self._lock:
            requested=self._jobs.get(job_id)
            if requested is None:return None
            candidates=[(key,item) for key,item in self._jobs.items()
                        if (key==job_id or item.get('_monitor_cast'))
                        and item.get('state') in ('queued','running')]
            running=[(key,item) for key,item in candidates if item.get('state')=='running']
            active=[(key,item) for key,item in running if item.get('_monitor_activity') is not None and not item.get('abort_requested') and not item.get('cancel_requested')]
            if active:
                selected=max(active,key=lambda pair:pair[1]['_monitor_activity'])[0]
            elif running:selected=running[0][0]
            elif candidates:selected=candidates[0][0]
            else:selected=job_id
            if live_preview is not None:self.set_preview_interest(selected,live_preview)
            result=self.status(selected)
            if selected!=job_id:result['monitor_followed']=True
            return result

    @staticmethod
    def _task_monitor_details(item,index):
        tasks=item.get('_monitor_tasks',())
        if type(index) is int and 1<=index<=len(tasks) and isinstance(tasks[index-1],dict):return dict(tasks[index-1])
        return None

    def status(self, job_id):
        with self._lock:
            item = self._jobs.get(job_id)
            if not item:return None
            result={k:v for k,v in item.items() if not k.startswith(('_preview_','_monitor_'))}
            details=self._task_monitor_details(item,item.get('task_index') or 1)
            if details is not None:result['task_details']=details
            result['abort_available']=bool(item.get('state')=='running' and not item.get('cancel_requested') and job_id in self._handles and (not item.get('batch') or (item.get('native_task_active') and all(callable(fn) for fn in item.get('_monitor_queue_ops',())) and len(item.get('_monitor_queue_ops',()))==2)))
            if self._last_monitor_output:
                result['last_result']=dict(self._last_monitor_output)
            return result

    def _run(self, job_id, submission, validate):
        try:
            # Fresh read of the choice, model, file and consent before GPU work.
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancelled before preparation');return
            prepared = self.prepare(submission, validate)
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancelled before native submission');return
            self._change(job_id, state='running',message='Submitted to WanGP generation queue',
                         refmod=prepared['refmod'], _monitor_cast=True, _monitor_tasks=[prepared.get('monitor_details')])
            outer = self
            class Callbacks:
                def on_status(self, msg):
                    if msg: outer._change(job_id, message=str(msg)[:500])
                def on_progress(self, update):
                    outer._remember_native_task(job_id,update)
                    outer._change(job_id, progress=getattr(update,'progress',None),
                                  current_step=getattr(update,'current_step',None),
                                  total_steps=getattr(update,'total_steps',None))
                def on_preview(self, update):
                    outer._store_preview(job_id, update)
                def on_output(self,data):
                    if submission.portrait_completion is None:outer._observe_native_output(job_id,data)
            job = self._session().submit_task(prepared['settings'], callbacks=Callbacks())
            self._attach_handle(job_id,job,register=True)
            result = job.result()
            with self._lock:self._handles.pop(job_id,None)
            files = [str(x) for x in (getattr(result,'generated_files',None) or [])]
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancellation requested',files=files);return
            if getattr(result,'success',False) and files and not getattr(result,'cancelled',False):
                for path in reversed(files):
                    if Path(path).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.webm'):
                        if submission.portrait_completion is None:self._record_monitor_output(job_id,path,1,from_result=True)
                        break
                if submission.portrait_completion is not None:
                    try:
                        portrait_url=submission.portrait_completion(files)
                    except Exception as exc:
                        self._change(job_id,state='failed',message='Image generated but profile portrait was not changed',error=str(exc)[:500])
                        return
                    self._record_monitor_output(job_id,files[0],1,from_result=True)
                    self._change(job_id,state='completed',message='Profile portrait saved',portrait_url=portrait_url,progress=100)
                else:
                    self._change(job_id, state='completed',message='Generation completed',files=files,progress=100)
            else:
                errors = [str(getattr(e,'message',e)) for e in (getattr(result,'errors',None) or [])]
                state = 'cancelled' if getattr(result,'cancelled',False) else 'failed'
                confirmed=self._confirmed_failures(result,0,1,set()) if not files else []
                self._change(job_id, state=state, failed_task_indices=confirmed, message='Generation did not produce an output',
                             files=files,error='; '.join(errors) or 'WanGP returned no generated files')
        except Exception as exc:
            self._change(job_id, state='cancelled' if self._cancelled(job_id) else 'failed',message='Queue submission stopped',error=str(exc)[:900])
        finally:
            with self._lock:self._handles.pop(job_id, None)


    def enqueue_conversion(self, task:ConversionTask, validate:Callable) -> str:
        """Stage automatic H3-picture-to-FLUX conversion via native WanGP queue.

        Only the fork's existing extractor/decompiler payloads are used. This
        does not run GPU code in FastAPI, a background worker or the browser.
        """
        if self.dispatch_mode != 'gradio' or not self.live_session_ready:
            raise RuntimeError('Automatic conversion requires the native WanGP queue relay')
        fork = self.adapter.discover()
        if (fork.get('fork_revision') or 0) < 58:
            raise ValueError('Automatic conversion requires Refmod-Fork fork.58 or newer')
        if task.target_model not in BASE_ARCHITECTURES or not (
            task.target_model.startswith('flux') or task.target_model=='pi_flux2'
        ):
            raise ValueError('Automatic conversion can only target supported FLUX models')
        if not any(m['model_type']==task.h3_model_type and m['ready']
                   for m in self.models('h3_video')):
            raise ValueError('No compatible H3 Ref2VA decoder is installed')
        if not any(m['model_type']==task.flux_model_type and m['ready']
                   for m in self.models(task.target_model)):
            raise ValueError('No compatible FLUX encoder is installed')
        if not 1 <= len(task.items) <= 500:
            raise ValueError('Choose between 1 and 500 RefMods to convert')
        if len({i.key for i in task.items})!=len(task.items):
            raise ValueError('Duplicate casting entry in conversion')
        for entry in task.items:
            validate(entry)
        job_id = uuid.uuid4().hex
        with self._lock:
            if any(j.get('state') in ('queued','running') and (j.get('operation')=='library_convert' or (task.library and j.get('operation')=='auto_convert')) for j in self._jobs.values()):
                raise RuntimeError('A RefMod conversion is already active')
            self._jobs[job_id]={'id':job_id,'state':'queued','operation':'library_convert' if task.library else 'auto_convert',
                'message':'Waiting for native WanGP relay to convert H3 pictures to FLUX',
                'model_type':task.flux_model_type,'total_tasks':len(task.items),
                'completed_tasks':0,'converted':[],'failures':[], 'files':[], 'error':''}
            self._pending.append((job_id,task,validate))
        return job_id

    def library_conversion_status(self):
        with self._lock:
            ids=[k for k,v in self._jobs.items() if v.get('operation')=='library_convert']
        return self.status(ids[-1]) if ids else None

    def _run_conversion(self, job_id:str, task:ConversionTask, validate:Callable):
        """Execute the fork's own decode + encode jobs, safely and serially.

        Do NOT import Refmod-Fork's private Python helpers or modify its files.
        Conversion is not a copy or metadata rename: H3 and FLUX VAEs differ.
        """
        if self._cancelled(job_id):
            self._change(job_id,state='cancelled',message='Cancelled before conversion');return
        try:
            session=self._session()
            root=self.adapter.refmod_root
        except Exception as exc:
            self._change(job_id,state='failed',message='Conversion initialization failed',error=str(exc)[:900]);return
        class Callbacks:
            def on_status(cb, message):
                if message:self._change(job_id,message=str(message)[:500])
            def on_progress(cb, update):pass
            def on_error(cb, message):
                self._change(job_id,error=str(getattr(message,'message',message))[:700])
        converted=[];failures=[]
        successful_sources={};failed_sources={}
        self._change(job_id,state='running',message='Converting library H3 picture RefMods' if task.library else 'Converting selected H3 picture RefMods')
        for number,item in enumerate(task.items,1):
            if self._cancelled(job_id):break
            source_name=None
            try:
                source_file=validate(item)   # Recheck saved choice, identity, consent and physical source
                source_name=refmod_identifier(source_file,root,'minimax_h3')
                meta=safetensors_metadata(source_file,'refmod_meta')
                if not is_h3_picture_refmod(meta):
                    raise ValueError('Only still-image H3 RefMods (including picture stacks) can convert to FLUX')
                if source_name in successful_sources:
                    converted.append({'key':item.key,'source':item.source,
                                      'refmod':successful_sources[source_name],
                                      'personal_id':item.personal_id,'person':item.person})
                    continue
                if source_name in failed_sources:
                    raise ValueError(failed_sources[source_name])
                self._change(job_id,message=f'{number}/{len(task.items)}: decoding {item.person}')
                folder=(root/'decompiled'/source_name).resolve()
                if not folder.is_relative_to((root/'decompiled').resolve()):
                    raise ValueError('Unsafe decompile path')
                before={p.name:(p.stat().st_mtime_ns,p.stat().st_size) for p in folder.iterdir()
                        if p.is_file() and not p.is_symlink()} if folder.is_dir() else {}
                settings=conversion_settings(session,task.h3_model_type,'minimax_h3',
                            {'op':'decompile','name':source_name})
                if self._cancelled(job_id):break
                handle=session.submit_task(settings,callbacks=Callbacks())
                self._attach_handle(job_id,handle)
                result=handle.result()
                with self._lock:self._handles.pop(job_id,None)
                if getattr(result,'cancelled',False):
                    self._change(job_id,cancel_requested=True)
                if self._cancelled(job_id):break
                pictures=sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink()
                    and p.suffix.lower() in ('.png','.jpg','.jpeg')
                    and (p.name not in before or
                         (p.stat().st_mtime_ns,p.stat().st_size)!=before[p.name])) if folder.is_dir() else []
                if not pictures:
                    raise ValueError('H3 decoding produced no new pictures')
                validate(item)  # Consent can be revoked during the H3 VAE step
                target_name,target_path=free_destination(root,source_name)
                if task.library and target_name!=source_name:
                    raise ValueError('Destination now exists; no duplicate or overwrite created')
                self._change(job_id,message=f'{number}/{len(task.items)}: encoding {item.person} for FLUX')
                spec={'name':target_name,'images':[str(p) for p in pictures],
                      'budget':4096,'layout':'separate',
                      'concept_type':meta.get('concept_type') or 'identity',
                      'description':meta.get('description') or '',
                      'converted_from':source_name}
                settings=conversion_settings(session,task.flux_model_type,'flux2',spec)
                if self._cancelled(job_id):break
                handle=session.submit_task(settings,callbacks=Callbacks())
                self._attach_handle(job_id,handle)
                result=handle.result()
                with self._lock:self._handles.pop(job_id,None)
                if getattr(result,'cancelled',False):self._change(job_id,cancel_requested=True)
                if self._cancelled(job_id):break
                output=safetensors_metadata(target_path,'klein9_refmod_meta')
                if output.get('converted_from')!=source_name:
                    raise ValueError('FLUX output did not confirm the original source')
                # Preserve the choice's exact original file for apply-time validation.
                path='flux2/'+target_name+'.safetensors'
                successful_sources[source_name]=path
                converted.append({'key':item.key,'source':item.source,'refmod':path,
                                  'personal_id':item.personal_id,'person':item.person})
            except Exception as exc:
                # A repeated role must not try to decode the same broken source.
                if source_name:
                    failed_sources[source_name]=str(exc)[:280]
                failures.append({'key':item.key,'person':item.person,'reason':str(exc)[:280]})
            finally:
                with self._lock:self._handles.pop(job_id,None)
                self._change(job_id,completed_tasks=number if not self._cancelled(job_id) else number-1, converted=list(converted),
                    failures=list(failures),progress=round(100*number/len(task.items),1))
        success=len(converted)
        if self._cancelled(job_id):
            self._change(job_id,state='cancelled',message='Conversion cancelled; model files retained',files=[str(root/p['refmod']) for p in converted]);return
        self._change(job_id,state=('completed' if not failures else 'partial' if success else 'failed'),
            message=f'Converted {success} of {len(task.items)} RefMods; {len(failures)} failed',
            files=[str(root/p['refmod']) for p in converted],
            error='; '.join(f["person"]+': '+f["reason"] for f in failures)[:900])

    def enqueue_workshop(self, task: WorkshopTask, validate: Callable) -> str:
        """Stage a Refmod-Fork job; only native Gradio callback can execute it."""
        if self.dispatch_mode != 'gradio' or self.api_session is None:
            raise RuntimeError('RefMod Workshop requires the native WanGP queue relay')
        if task.op=='extract_flux':
            family_models=['flux2_dev','flux2_klein4','flux2_klein9','pi_flux2','flux3_klein']
            models=[]
            for family in family_models:
                try:models.extend(self.models(family))
                except (ValueError,RuntimeError):continue
            if not any(m['ready'] and m['model_type']==task.model_type for m in models):
                raise ValueError('Choose a Refmod-Fork compatible installed FLUX.2 or FLUX.3 model')
        else:
            models=self.models('h3_video')
            if not any(m['ready'] and m['model_type']==task.model_type for m in models):
                raise ValueError('Choose an installed MiniMax H3 Ref2VA model with Refmod-Fork enabled')
        fork=self.adapter.discover()
        if (fork.get('fork_revision') or 0)<39:
            raise ValueError('Refmod-Fork fork.39 or newer is required for Workshop jobs')
        validate(task)
        job_id=uuid.uuid4().hex
        with self._lock:
            destination=str(task.expected.resolve())
            if any(j.get('workshop_destination')==destination and j['state'] in ('queued','running') for j in self._jobs.values()):
                raise ValueError('A Workshop job already targets this destination')
            self._jobs[job_id]={'id':job_id,'state':'queued','message':'Waiting for native WanGP queue relay',
                                'model_type':task.model_type,'operation':task.op,'files':[], 'error':'','workshop_destination':destination}
            if callable(getattr(task,'test_portrait',None)):self._jobs[job_id]['test_portrait_state']='pending'
            self._pending.append((job_id,task,validate))
        return job_id

    def _run_workshop(self, job_id: str, task: WorkshopTask, validate: Callable):
        """Fork intentionally returns no generated video; verify actual disk output."""
        try:
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancelled before Workshop preparation');return
            validate(task)  # explicit consent, all file paths, collision check, again
            settings=extract_job_settings(self._session(),task)
            self._change(job_id,state='running',message='Refmod-Fork VAE operation submitted')
            outer=self
            class Callbacks:
                def on_status(self,msg):
                    if msg:outer._change(job_id,message=str(msg)[:500])
                def on_progress(self,update):
                    outer._change(job_id,progress=getattr(update,'progress',None))
                def on_preview(self, update):
                    outer._store_preview(job_id, update)
                def on_error(self,error):
                    outer._change(job_id,error=str(getattr(error,'message',error))[:700])
            before={}
            if task.op=='decompile' and task.expected.is_dir():
                before={p.name:(p.stat().st_mtime_ns,p.stat().st_size) for p in task.expected.iterdir()
                        if p.is_file() and not p.is_symlink()}
            if self._cancelled(job_id):
                self._change(job_id,state='cancelled',message='Cancelled before Workshop submission');return
            handle=self._session().submit_task(settings,callbacks=Callbacks())
            self._attach_handle(job_id,handle)
            result=handle.result()
            with self._lock:self._handles.pop(job_id,None)
            if task.op in ('extract','extract_flux'):
                found=False
                if task.expected.is_file() and not task.expected.is_symlink():
                    try:
                        if task.op=='extract_flux':
                            meta=safetensors_metadata(task.expected,'klein9_refmod_meta')
                            found=isinstance(meta,dict) and task.expected.stat().st_size>64
                        else:
                            read_header(task.expected)  # reject truncated/invalid output
                            found=True
                    except (ValueError,OSError,UnicodeError,KeyError):
                        pass
                files=[str(task.expected)] if found else []
            else:
                folder=task.expected
                files=[str(p) for p in sorted(folder.iterdir()) if p.is_file() and
                       p.suffix.lower() in ('.png','.jpg','.mp4','.wav')] if folder.is_dir() else []
                found=any((p.name not in before or
                           (p.stat().st_mtime_ns,p.stat().st_size)!=before[p.name])
                          for p in (Path(f) for f in files))
            if self._cancelled(job_id) or getattr(result,'cancelled',False):
                self._change(job_id,state='cancelled',message='Workshop cancelled; output files retained',files=files);return
            if found:
                self._change(job_id,state='completed',message='Refmod-Fork '+task.op+' complete',
                             files=files,error='',progress=100)
            else:
                errors=[str(getattr(e,'message',e)) for e in (getattr(result,'errors',None) or [])]
                self._change(job_id,state='failed',message='No RefMod output created',
                             error='; '.join(errors) or 'Fork completed without writing expected files')
        except Exception as exc:
            self._change(job_id,state='cancelled' if self._cancelled(job_id) else 'failed',message='Workshop operation stopped',error=str(exc)[:900])
        finally:
            with self._lock:self._handles.pop(job_id,None)

    def _register_native_ids(self, job_id, handle, offset):
        item=self._jobs.get(job_id)
        if not item:return
        ids=getattr(handle,'webui_client_ids',()) or ()
        mapping=item.setdefault('_monitor_native_ids',{})
        for i,client_id in enumerate(ids,offset+1):
            if client_id:mapping[str(client_id)]=i

    def _remember_native_task(self,job_id,update):
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or item.get('state')!='running':return
            idx=int(item.get('task_index') or 1)
            reported=getattr(update,'task_index',None)
            try:
                if reported is not None and max(1,int(reported))!=idx:return
            except (ValueError,TypeError,OverflowError):return
            native=getattr(update,'task_id',None)
            if native:
                item.setdefault('_monitor_native_ids',{})[str(native)]=idx
                item['_monitor_active_native']=str(native)
            phase=getattr(update,'phase',None)
            item['native_task_active']=bool(native and phase not in ('queued','cancelled','downloading_output'))
            if phase not in ('queued','cancelled','downloading_output') and not item.get('abort_requested') and not item.get('cancel_requested'):
                item['_monitor_activity']=time.monotonic()
            else:item.pop('_monitor_activity',None)
            if phase=='cancelled':
                self._previews.pop(job_id,None)
                item.update(preview_kind='',preview_task_index=None)

    def _observe_native_output(self, job_id, data):
        # WebUI output events identify the completed client, not necessarily
        # the task now denoising. Never infer identity from current progress.
        if not isinstance(data,dict) or not data.get('client_id') or not isinstance(data.get('path'),str):return
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or item.get('state')!='running':return
            index=item.get('_monitor_native_ids',{}).get(str(data['client_id']))
            if index is None:return
            item.setdefault('_monitor_output_indices',set()).add(index)
            if int(item.get('task_index') or 1)==index:
                item['native_task_active']=False
                item.pop('_monitor_activity',None)
        self._record_monitor_output(job_id,data['path'],index)

    def _record_monitor_output(self,job_id,filename,task_index,from_result=False):
        # Never accept paths from HTTP input; only native per-job outputs.
        try:
            path=Path(filename)
            if not path.is_absolute():path=self.adapter.root/path
            path=path.resolve(strict=True)
            mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.mp4':'video/mp4','.webm':'video/webm'}.get(path.suffix.lower())
            if not mime or not path.is_file():return
            stat=path.stat()
            if stat.st_size<=0:return
            if mime.startswith('image/'):
                from PIL import Image
                with Image.open(path) as pic:
                    if pic.format not in ('PNG','JPEG','WEBP'):return
                    pic.verify()
        except (OSError,ValueError,RuntimeError):return
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or (not from_result and item.get('state')!='running'):return
            previous=self._last_monitor_output
            for old,entry in self._monitor_outputs.items():
                details=self._monitor_gallery.get(old,{})
                if details.get('job_id')==job_id and entry[0]==path and entry[2:]==(stat.st_size,stat.st_mtime_ns):
                    # Manifest result lists may repeat an identified native output
                    # without a task index. Never replace known identity with unknown.
                    if details.get('task_index')==task_index or task_index is None:return
            token=uuid.uuid4().hex
            self._monitor_outputs[token]=(path,mime,stat.st_size,stat.st_mtime_ns)
            output={'id':token,'job_id':job_id,'task_index':task_index,'kind':'video' if mime.startswith('video/') else 'image', 'task_details':self._task_monitor_details(item,task_index)}
            self._monitor_gallery[token]=deepcopy(output)
            # Late earlier-task outputs belong in the gallery but must not rewind the live monitor.
            if not (previous and previous['job_id']==job_id and previous.get('task_index') and task_index and previous['task_index']>task_index):
                self._last_monitor_output=output
            for old in list(self._monitor_outputs)[:-30]:
                self._monitor_outputs.pop(old,None);self._monitor_gallery.pop(old,None)
            if self._last_monitor_output and self._last_monitor_output['id'] not in self._monitor_outputs:self._last_monitor_output=output
            if callable(self.gallery_sink):
                try:self.gallery_sink(self.gallery_snapshot())
                except Exception:logging.getLogger(__name__).exception('Casting Studio could not persist gallery')

    def gallery_snapshot(self):
        with self._lock:
            return [{'output':deepcopy(self._monitor_gallery[k]),'path':str(v[0]),'mime':v[1],'size':v[2],'mtime':v[3]} for k,v in self._monitor_outputs.items()]

    def restore_gallery(self,records):
        # Only from local runtime storage, never from an import or HTTP request.
        with self._lock:
            for rec in records[-30:]:
                try:
                    output=rec['output'];token=output['id'];path=Path(rec['path']);mime=rec['mime']
                    allowed={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.mp4':'video/mp4','.webm':'video/webm'}
                    if not re.fullmatch(r'[a-f0-9]{32}',token) or allowed.get(path.suffix.lower())!=mime or output.get('kind')!=('video' if mime.startswith('video/') else 'image'):continue
                    if not path.is_absolute() or path.resolve(strict=True)!=path or not path.is_file():continue
                    st=path.stat()
                    if (st.st_size,st.st_mtime_ns)!=(rec['size'],rec['mtime']):continue
                    self._monitor_outputs[token]=(path,mime,st.st_size,st.st_mtime_ns)
                    self._monitor_gallery[token]=deepcopy(output)
                except (OSError,ValueError,TypeError,KeyError,RuntimeError,AttributeError):continue
            # A historical result must not pretend to be a current job's live preview.


    def monitor_gallery(self):
        with self._lock:results=list(self._monitor_gallery.values())[::-1]
        return [deepcopy(r) for r in results if self.monitor_output(r['id']) is not None]

    def monitor_output(self,token):
        with self._lock:entry=self._monitor_outputs.get(token)
        if not entry:return None
        path,mime,size,mtime=entry
        try:
            stat=path.stat()
            if path.resolve()!=path or not path.is_file() or (stat.st_size,stat.st_mtime_ns)!=(size,mtime):return None
        except OSError:return None
        return path,mime

    def manage_native_queue(self, api_session, request):
        """Native Gradio callback only: never resolve a session proxy from HTTP."""
        token=''
        try:
            req=json.loads(request or '{}')
            token=str(req.get('token',''))[:80]
            action=req.get('action')
            if action not in ('list','cancel'):raise ValueError('Unknown queue action')
            listing=getattr(api_session,'list_queue',None)
            cancel=getattr(api_session,'cancel_queue_task',None)
            if not callable(listing):raise ValueError('This WanGP version does not expose native queue inspection. Use the main WanGP queue.')
            def snapshot():
                entries=listing()['tasks']
                return [{'queue_id':str(t['queue_id']), 'position':t.get('position',i+1),
                         'model_type':str(t.get('model_type',''))[:120], 'prompt':str(t.get('prompt',''))[:320],
                         'status':str(t.get('status','unknown')), 'client_id':str(t.get('client_id',''))}
                        for i,t in enumerate(entries) if t.get('queue_id')]
            rows=snapshot();message=''
            if action=='cancel':
                if not callable(cancel):raise ValueError('Individual cancellation is unavailable in this WanGP version.')
                target=req.get('queue_id');expected=req.get('status')
                row=next((r for r in rows if r['queue_id']==target),None)
                if not row or row['status']!=expected or expected not in ('queued','running'):
                    raise ValueError('Task changed or finished. Refresh the queue and try again.')
                # Register an intentional skip before cancellation can deliver its result.
                marked=[]
                with self._lock:
                    for item in self._jobs.values():
                        if not item.get('batch') or item.get('state')!='running':continue
                        index=item.get('_monitor_native_ids',{}).get(row['client_id'])
                        if index is not None:
                            skips=item.setdefault('_monitor_skipped',set())
                            if index not in skips:skips.add(index);marked.append((item,index))
                try:result=cancel(target)
                except Exception:
                    with self._lock:
                        for item,index in marked:item.get('_monitor_skipped',set()).discard(index)
                    raise
                message='Cancellation requested' if result.get('status')=='cancelling' else 'Task removed'
                rows=snapshot()
            for row in rows:row.pop('client_id',None)
            return json.dumps({'token':token,'tasks':rows,'can_cancel':callable(cancel),'message':message})
        except (ValueError,KeyError,TypeError,AttributeError,RuntimeError) as exc:
            return json.dumps({'token':token,'error':str(exc)[:300]})
        except Exception:
            return json.dumps({'token':token,'error':'Native queue request failed. Use the main WanGP queue.'})

    def abort_current(self,job_id,expected_task):
        # A stale UI click must not abort the following task. For a batch,
        # use the exact native queue id, never the whole manifest handle.
        with self._lock:
            item=self._jobs.get(job_id);handle=self._handles.get(job_id)
            if not item or item.get('state')!='running' or int(item.get('task_index') or 1)!=expected_task or not handle:
                raise ValueError('This generation is no longer active')
            if item.get('abort_requested') or item.get('cancel_requested'):raise ValueError('Cancellation already requested')
            single=not item.get('batch')
            if single:
                item['abort_requested']=True
            native=item.get('_monitor_active_native')
            if not single:
                if not native or item.get('_monitor_native_ids',{}).get(native)!=expected_task or not item.get('native_task_active'):
                    raise ValueError('Waiting for an identified active WanGP task')
                list_queue,cancel_task=item.get('_monitor_queue_ops',(None,None))
                if not callable(list_queue) or not callable(cancel_task):
                    raise ValueError('Installed WanGP cannot safely abort a single batch task; use WanGP Abort')
        # Do not hold the board lock while calling native queue methods.
        if single:
            try:handle.cancel()
            except Exception:
                with self._lock:self._jobs.get(job_id,{}).update(abort_requested=False)
                raise
            return
        entries=list_queue().get('tasks',[])
        matches=[x for x in entries if str(x.get('client_id') or '')==native and x.get('status')=='running' and x.get('queue_id')]
        if len(matches)!=1:raise ValueError('The selected generation is no longer running')
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or item.get('state')!='running' or int(item.get('task_index') or 1)!=expected_task or item.get('abort_requested') or item.get('cancel_requested'):
                raise ValueError('This generation is no longer active')
            item['abort_requested']=True
            item.setdefault('_monitor_skipped',set()).add(expected_task)
        try:cancel_task(matches[0]['queue_id'])
        except Exception:
            with self._lock:
                item=self._jobs.get(job_id,{})
                item.get('_monitor_skipped',set()).discard(expected_task)
                if int(item.get('task_index') or 1)==expected_task:item['abort_requested']=False
            raise

    def cancel(self, job_id):
        with self._lock:
            item=self._jobs.get(job_id)
            if not item or item.get('state') not in ('queued','running') or item.get('cancel_requested'):return False
            for index,(pending_id,_submission,_validate) in enumerate(self._pending):
                if pending_id==job_id:
                    self._pending.pop(index)
                    self._change(job_id,state='cancelled',message='Cancelled before queue submission')
                    return True
            handle=self._handles.get(job_id)
            item['cancel_requested']=True
        if handle:
            try:handle.cancel()
            except Exception:
                with self._lock:
                    if item.get('state') in ('queued','running'):item.pop('cancel_requested',None)
                raise
        return True
