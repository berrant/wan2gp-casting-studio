"""Check a distributable ZIP or the exact staged Git index. No private denylist.

Run: python check_release_privacy.py path/to/release.zip
     python check_release_privacy.py --git-index
Requires Pillow for inspection of the generic PNG assets.
This is a narrow packaging guard, not proof of anonymity or a security audit.
"""
from pathlib import PurePosixPath
import ast, hashlib, io, json, re, stat, subprocess, sys, zipfile
from PIL import Image

ROOT = 'wan2gp-casting-studio'
FILES = {'LICENSE','NOTICE.md','CONTRIBUTING.md','README.md','CHANGELOG.md','REQUIREMENTS.md','REGRESSION_CHECKLIST.md',
         '__init__.py','plugin.py','plugin_info.json','compat_adapter.py','conversion_bridge.py',
         'queue_bridge.py','workshop_bridge.py','vision_bridge.py','requirements.txt','run_regression.py','check_release_privacy.py',
         'app/__init__.py','app/server.py','app/index.html','app/credit_service.py','app/credit_sync.py',
         'app/requirements.txt','app/casting_db.json','app/refmod_identities.json'}
ICONS = {'app/icons/'+x+'.png' for x in ('adult','casting-logo','models','performers','personal','productions','workshop','television')}
# Build patterns without literal examples that would match this checker itself.
PATTERNS = {
 'absolute user-home path': r'(?i)(?:/home/|/Users/|[A-Z]:[\\/]Users[\\/])[\w.-]+',
 'email address': r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
 'private network address': r'\b(?:192\.168|10\.(?:\d{1,3})|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b',
 'credential-like token': r'(?i)\b(?:ghp_|github_pat_|hf_|sk-|xox[baprs]-)[A-Za-z0-9_-]{20,}\b|\bAKIA[A-Z0-9]{16}\b',
 'private key': r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
}
CATALOG_KEYS={'people':{'name','type','credits','actress'},'roles':{'actress','character','production','franchise'},
              'productions':{'id','title','year','franchise','roles','source','wiki'}}

GITHUB_FILES = {'.gitignore','PUBLISHING.md','TEST_RESULTS.txt'}

LICENSE_SHA256 = '026ef905367dd50b07dd541fd81acb1f9c6e2a29368d55d67cdf53db0e8955b4'
REQUIRED_NOTICE = "Required Notice: Copyright (c) 2026 Casting Studio's respective copyright holders (https://github.com/berrant/wan2gp-casting-studio)."

def audit(path):
 errors=[]; seen=set(); counts={}
 with zipfile.ZipFile(path) as z:
  if z.comment:errors.append('ZIP comment present')
  if z.testzip():errors.append('ZIP integrity failed')
  # Detect the explicit repository-root layout; never strip arbitrary prefixes.
  source = 'plugin_info.json' in z.namelist()
  required = FILES | ICONS | (GITHUB_FILES if source else set())
  for info in z.infolist():
   p=PurePosixPath(info.filename)
   if not p.parts or p.is_absolute() or (not source and p.parts[0]!=ROOT) or '..' in p.parts or '\\' in info.filename:
    errors.append('Unexpected archive path');continue
   rel='/'.join(p.parts if source else p.parts[1:])
   if info.is_dir():
    if rel not in ('','app','app/icons','tests'):errors.append('Unexpected directory: '+rel)
    continue
   if rel in seen:errors.append('Duplicate archive entry: '+rel)
   seen.add(rel)
   if not (rel in required or re.fullmatch(r'tests/test_[a-zA-Z0-9_]+\.py',rel)):
    errors.append('Unexpected packaged file: '+rel);continue
   if info.extra or info.comment or info.date_time!=(2020,1,1,0,0,0) or stat.S_ISLNK(info.external_attr>>16):
    errors.append('Non-normalized archive metadata: '+rel)
   data=z.read(info)
   if rel in ICONS:
    with Image.open(io.BytesIO(data)) as im:
     if im.format!='PNG' or im.info or im.getexif():errors.append('Icon metadata present: '+rel)
    continue
   text=data.decode('utf-8')
   if rel=='LICENSE' and hashlib.sha256(data).hexdigest()!=LICENSE_SHA256:
    errors.append('License file changed; verify terms')
   if rel=='NOTICE.md' and REQUIRED_NOTICE not in text.splitlines():
    errors.append('Required copyright notice missing or changed')
   if rel!='check_release_privacy.py':
    for label,pattern in PATTERNS.items():
     if re.search(pattern,text):errors.append(label+' in '+rel)
   if rel=='app/server.py':
    seed_names={'KNOWN_IDENTITIES','CURATED_ROLE_DATA','CURATED_CATEGORIES','CURATED_CREDITS','CURATED_IMDB','CURATED_CHARACTER_TRAITS','ADULT_SEED'}
    found=set()
    for node in ast.parse(text).body:
     if not isinstance(node,ast.Assign):continue
     for target in node.targets:
      if not isinstance(target,ast.Name) or target.id not in seed_names:continue
      found.add(target.id);v=node.value
      empty=(isinstance(v,ast.Dict) and not v.keys) or (isinstance(v,ast.Call) and isinstance(v.func,ast.Name) and v.func.id=='set' and not v.args and not v.keywords)
      if not empty:errors.append('Nonempty shipped identity preset: '+target.id)
    if found!=seed_names:errors.append('Identity preset definitions changed; inspect before release')
   if rel=='app/refmod_identities.json' and json.loads(text)!={}:errors.append('Nonempty bundled identity aliases')
   if rel=='app/casting_db.json':
    catalog=json.loads(text)
    if set(catalog)!={'meta','people','roles','productions','creditSuggestions'} or catalog.get('creditSuggestions')!=[]:
     errors.append('Unexpected catalog sections')
    if set(catalog.get('meta',{}))!={'mapped_roles_count','production_count','inventory_notice'}:errors.append('Unexpected catalog metadata')
    for key,allowed in CATALOG_KEYS.items():
     rows=catalog[key];counts[key]=len(rows)
     if rows:errors.append('Bundled catalog must be empty: '+key)
     if any(not isinstance(row,dict) or set(row)-allowed for row in rows):errors.append('Unexpected catalog fields: '+key)
  for missing in sorted(required-seen):errors.append('Missing release file: '+missing)
 return errors, len(seen),counts

def audit_git_index():
 # Read staged blobs, not working-tree files. Reject symlinks, submodules,
 # and unresolved merge stages. No writes to the user's repository.
 root=subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip()
 def git(*args):return subprocess.check_output(['git','-C',root,*args])
 entries=git('ls-files','--stage','-z').split(b'\0')
 buffer=io.BytesIO()
 with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for entry in entries:
   if not entry:continue
   meta,name=entry.split(b'\t',1)
   mode,oid,stage=meta.split()
   if stage!=b'0' or mode not in (b'100644',b'100755'):
    raise ValueError('Unsupported Git index entry: '+name.decode('utf-8',errors='replace'))
   info=zipfile.ZipInfo(name.decode('utf-8'),(2020,1,1,0,0,0))
   info.create_system=3
   info.external_attr=int(mode,8)<<16
   z.writestr(info,git('cat-file','blob',oid.decode('ascii')),compress_type=zipfile.ZIP_DEFLATED)
 buffer.seek(0)
 return audit(buffer)

if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('Usage: python check_release_privacy.py path/to/release.zip OR --git-index')
 try:
  errors,count,catalog=audit_git_index() if sys.argv[1]=='--git-index' else audit(sys.argv[1])
 except (OSError,ValueError,KeyError,subprocess.CalledProcessError,zipfile.BadZipFile) as exc:
  raise SystemExit('FAIL: '+str(exc))
 print(f'{count} files inspected; public catalog counts: {catalog}')
 for err in errors:print('FAIL:',err)
 if errors:raise SystemExit(1)
 print('Distribution privacy checks passed. Manual review and publisher-account checks remain separate.')
