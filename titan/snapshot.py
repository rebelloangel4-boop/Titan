"""Portable database + referenced artifacts snapshot. Restore into a new directory only."""
import argparse,hashlib,json,os,shutil,sqlite3,stat,tempfile,zipfile
from pathlib import Path
from .backup import backup

MAX_FILE=256_000_000
MAX_TOTAL=1_000_000_000

def read_regular(path,limit=MAX_FILE):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError('Regular file required')
  data=f.read(limit+1)
 if len(data)>limit:raise ValueError('Snapshot file too large')
 return data

def create(database,artifact_root,destination):
 destination=Path(destination)
 if destination.exists():raise ValueError('Destination already exists')
 with tempfile.TemporaryDirectory() as tmp:
  db=Path(tmp)/'state.db';backup(database,db)
  entries={'state.db':read_regular(db)}
  with sqlite3.connect(db) as c:
   has=c.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone()
   rows=c.execute('SELECT id,size,sha256 FROM artifacts').fetchall() if has else []
  if len(rows)>10000 or sum(size for _,size,_ in rows)+len(entries['state.db'])>MAX_TOTAL:raise ValueError('Snapshot quota exceeded')
  import re
  for aid,size,sha in rows:
   if not re.fullmatch('[a-f0-9]{32}',aid):raise ValueError('Invalid artifact ID')
   data=read_regular(Path(artifact_root)/aid,25_000_000)
   if len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Artifact integrity failure')
   entries['artifacts/'+aid]=data
  if sum(map(len,entries.values()))>MAX_TOTAL:raise ValueError('Snapshot quota exceeded')
  manifest={name:{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in entries.items()}
  fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  try:
   with os.fdopen(fd,'wb') as f:
    with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:
     z.writestr('manifest.json',json.dumps({'version':1,'files':manifest}))
     for name,data in entries.items():z.writestr(name,data)
    f.flush();os.fsync(f.fileno())
  except BaseException:
   destination.unlink(missing_ok=True);raise
 return {'files':len(entries),'bytes':sum(map(len,entries.values()))}

def restore(source,destination):
 destination=Path(destination)
 # Exclusive creation also rejects existing directories and dangling symlinks.
 destination.mkdir(mode=0o700)
 try:
  with zipfile.ZipFile(source) as z:
   infos=z.infolist();names=[i.filename for i in infos]
   if len(names)!=len(set(names)) or len(names)>10002:raise ValueError('Duplicate/excessive entries')
   if any(i.file_size>MAX_FILE for i in infos) or sum(i.file_size for i in infos)>MAX_TOTAL:raise ValueError('Snapshot quota exceeded')
   if z.getinfo('manifest.json').file_size>2_000_000:raise ValueError('Manifest too large')
   manifest=json.loads(z.read('manifest.json'))
   if manifest.get('version')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Unsupported manifest')
   files=manifest['files']
   if set(names)!=set(files)|{'manifest.json'} or 'state.db' not in files:raise ValueError('Manifest mismatch')
   import re
   for name,metadata in files.items():
    if name!='state.db' and not re.fullmatch(r'artifacts/[a-f0-9]{32}',name):raise ValueError('Unsafe entry path')
    data=z.read(name)
    if len(data)!=metadata['size'] or hashlib.sha256(data).hexdigest()!=metadata['sha256']:raise ValueError('Snapshot integrity failure')
    path=destination/name;path.parent.mkdir(mode=0o700,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)
  with sqlite3.connect(destination/'state.db') as c:
   if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failure')
   has=c.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone()
   rows=c.execute('SELECT id,size,sha256 FROM artifacts').fetchall() if has else []
  expected={'state.db'}
  for aid,size,sha in rows:
   name='artifacts/'+aid;expected.add(name)
   if name not in files or files[name]!={'size':size,'sha256':sha}:raise ValueError('Artifact database mismatch')
  if expected!=set(files):raise ValueError('Unexpected snapshot files')
 except BaseException:
  shutil.rmtree(destination);raise
 return str(destination/'state.db')

if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
 c=sub.add_parser('create');c.add_argument('database');c.add_argument('artifact_root');c.add_argument('destination')
 r=sub.add_parser('restore');r.add_argument('source');r.add_argument('destination')
 a=p.parse_args();print(create(a.database,a.artifact_root,a.destination) if a.action=='create' else restore(a.source,a.destination))
