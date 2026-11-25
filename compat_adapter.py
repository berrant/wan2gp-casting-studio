"""Refmod-Fork boundary: read-only discovery; no source imports or monkeypatches.

Never couple Casting Studio to Refmod-Fork private UI functions. Missing/unknown
versions are explicitly *not* considered queue-compatible.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

MODEL_MIN_FORK = {
    'h3_video': 1,
    'h3_image': 55,
    'h3_image_pruned': 55,
    'p_h3_image': 50,
    'flux2_dev': 31,
    'flux2_klein4': 31,
    'flux2_klein9': 31,
    'pi_flux2': 31,
    'flux3_klein': 31,
}


def _read_plugin_info(info_file: Path) -> dict[str, Any] | None:
    try:
        if not info_file.is_file() or info_file.stat().st_size > 65536:
            return None
        value = json.loads(info_file.read_text(encoding='utf8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _fork_number(version: str) -> int | None:
    match = re.search(r'(?:^|[-.])fork\.(\d+)(?:\D|$)', version, flags=re.I)
    return int(match.group(1)) if match else None


def _inventory(folder: Path) -> int:
    # Do not load weights or interpret .safetensors payloads.
    try:
        return sum(1 for p in folder.rglob('*.safetensors') if p.is_file() and not p.name.startswith('._'))
    except OSError:
        return 0


class RefmodForkAdapter:
    """Versioned, side-effect-free capability check for separate Refmod-Fork installs."""

    def __init__(self, wangp_root: Path):
        self.root = Path(wangp_root).resolve()
        self.refmod_root = Path(os.environ.get('CASTING_STUDIO_REFMOD_ROOT') or (self.root/'loras'/'refmods_plugin')).resolve()

    def discover(self) -> dict[str, Any]:
        plugins_dir = self.root/'plugins'
        candidates: list[tuple[Path, dict[str, Any]]] = []
        if plugins_dir.is_dir():
            for folder in sorted(plugins_dir.iterdir()):
                if not folder.is_dir() or folder.is_symlink():
                    continue
                info = _read_plugin_info(folder/'plugin_info.json')
                if not info:
                    continue
                url = str(info.get('url','')).casefold().rstrip('/')
                name = str(info.get('name','')).casefold()
                # Exact upstream repo identity; other RefMods branches are not silently trusted.
                if 'github.com/jedsdead/refmod-fork' in url or ('refmods for wan gp' in name and 'jedsdead' in str(info.get('author','')).casefold()):
                    candidates.append((folder,info))
        if not candidates:
            return {'installed':False,'compatible':False,'version':None,'fork_revision':None,
                    'plugin_directory':None,'supported_models':{},
                    'message':'Refmod-Fork (jedsdead) not detected. Existing inventory and casting remain usable.',
                    'inventory':self._inventory()}
        folder,info=candidates[0]
        version=str(info.get('version',''))
        revision=_fork_number(version)
        supports={name: (revision is not None and revision>=minimum)
                  for name,minimum in MODEL_MIN_FORK.items()}
        return {'installed':True,'compatible':bool(revision is not None and revision>=55),
                'version':version,'fork_revision':revision,'plugin_directory':str(folder),
                'supported_models':supports,'inventory':self._inventory(),
                'message':('Supported model families identified from fork metadata; queue payload still requires live verification.'
                           if revision is not None and revision>=55 else
                           'Unsupported or unknown Refmod-Fork version: queue delivery disabled; casting remains available.')}

    def _inventory(self) -> dict[str,int]:
        root=self.refmod_root
        return {key:_inventory(root/part) for key,part in {
            'h3_public':'minimax_h3/celebs', 'h3_private':'minimax_h3/personal',
            'flux_public':'flux2/celebs','flux_private':'flux2/personal',
        }.items()}

    def paths(self) -> dict[str,Path]:
        root=self.refmod_root
        return {'h3_public':root/'minimax_h3'/'celebs', 'h3_private':root/'minimax_h3'/'personal',
                'flux_all':root/'flux2', 'flux_private':root/'flux2'/'personal'}

    def validate_refmod(self, *, relative_path: str, family: str, personal: bool=False) -> Path:
        """Resolve a selected RefMod, rejecting traversal and public/private crossovers.

        Does not open or change safetensors files. Raises ValueError on mismatch.
        """
        if family not in ('minimax_h3','flux2'):
            raise ValueError('Unsupported model family')
        if not isinstance(relative_path,str) or not relative_path or '\\' in relative_path:
            raise ValueError('Invalid RefMod path')
        rel=Path(relative_path)
        if rel.is_absolute() or '..' in rel.parts or rel.suffix.casefold()!='.safetensors':
            raise ValueError('Invalid RefMod path')
        if family=='minimax_h3':
            if personal:
                if rel.parts[0]!='personal':raise ValueError('Private H3 RefMod must come from personal/')
                base=self.paths()['h3_private']; subpath=Path(*rel.parts[1:])
            else:
                if rel.parts[0] in ('personal','flux2'):raise ValueError('Public H3 RefMod outside celebs/')
                base=self.paths()['h3_public'];subpath=rel
        else:
            if len(rel.parts)<2 or rel.parts[0]!='flux2':raise ValueError('Flux RefMod must start flux2/')
            base=self.refmod_root/'flux2'
            subpath=Path(*rel.parts[1:])
            if personal != (subpath.parts[0]=='personal'):
                raise ValueError('Public/private Flux RefMod mismatch')
            if subpath.parts[0] in ('celebs','personal'):
                base=base/subpath.parts[0];subpath=Path(*subpath.parts[1:])
        target=(base/subpath).resolve()
        if not target.is_relative_to(base.resolve()) or not target.is_file():
            raise ValueError('RefMod is missing or outside its approved folder')
        return target
