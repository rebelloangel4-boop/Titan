"""Project-scoped knowledge, immutable artifacts, recurring schedules and chat history."""
import hashlib,json,os,re,sqlite3,time,uuid
from pathlib import Path

class Workspace:
 def __init__(self,db):
  self.db=db
  self.root=Path(os.getenv('TITAN_ARTIFACT_DIR',str(Path(db.path).resolve().parent/'artifacts'))).resolve()
  self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
  with db.connect() as c:
   c.executescript('''
   CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,created REAL);
   INSERT OR IGNORE INTO projects VALUES('default','My workspace',0);
   CREATE TABLE IF NOT EXISTS knowledge(project TEXT,key TEXT,value TEXT,updated REAL,PRIMARY KEY(project,key));
   CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,project TEXT,job TEXT,name TEXT,mime TEXT,size INTEGER,sha256 TEXT,created REAL);
   CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,project TEXT,objective TEXT,kind TEXT,payload TEXT,interval_seconds INTEGER,next_run REAL,enabled INTEGER);
   CREATE TABLE IF NOT EXISTS provider_quality(provider TEXT,model TEXT,suite TEXT,job TEXT,score REAL,created REAL,PRIMARY KEY(provider,model,suite));
   CREATE TABLE IF NOT EXISTS chat(id INTEGER PRIMARY KEY,project TEXT,role TEXT,content TEXT,provider TEXT,created REAL);
   ''')
   c.execute('BEGIN IMMEDIATE')
   knowledge_cols={r[1] for r in c.execute('PRAGMA table_info(knowledge)')}
   if 'scope' not in knowledge_cols:c.execute("ALTER TABLE knowledge ADD COLUMN scope TEXT DEFAULT 'long'")
   cols={r[1] for r in c.execute('PRAGMA table_info(jobs)')}
   for name in ('project','parent'):
    if name not in cols:c.execute('ALTER TABLE jobs ADD COLUMN '+name+' TEXT')
 def require(self,project):
  with self.db.connect() as c:
   if not c.execute('SELECT 1 FROM projects WHERE id=?',(project,)).fetchone():raise ValueError('Unknown project')
 def create_project(self,name):
  if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise ValueError('Project name must be 1–100 characters')
  pid=uuid.uuid4().hex
  with self.db.connect() as c:c.execute('INSERT INTO projects VALUES(?,?,?)',(pid,name.strip(),time.time()))
  return pid
 def projects(self):
  with self.db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM projects ORDER BY created')]
 def remember(self,project,key,value,scope='long'):
  if scope not in ('short','long'):raise ValueError('Invalid memory scope')
  self.require(project)
  if not isinstance(key,str) or not isinstance(value,str) or not 1<=len(key)<=200 or len(value)>20000:raise ValueError('Invalid knowledge entry')
  from .security import redact
  with self.db.connect() as c:c.execute('INSERT OR REPLACE INTO knowledge(project,key,value,updated,scope) VALUES(?,?,?,?,?)',(project,key,redact(value),time.time(),scope))
 def search(self,project,query='',limit=20):
  self.require(project)
  if not isinstance(query,str) or len(query)>1000:raise ValueError('Invalid search query')
  # Literal substring search; wildcard characters do not change query semantics.
  with self.db.connect() as c:return [dict(r) for r in c.execute("SELECT * FROM knowledge WHERE project=? AND (scope='long' OR updated>?) AND (instr(lower(key),lower(?))>0 OR instr(lower(value),lower(?))>0) ORDER BY updated DESC LIMIT ?",(project,time.time()-86400,query,query,min(max(int(limit),1),100)))]
 def retrieve(self,project,query,limit=8,max_chars=12000):
  """Rank the latest 500 active project memories; bound prompt content size."""
  self.require(project)
  if not isinstance(query,str) or len(query)>12000:raise ValueError('Invalid retrieval query')
  if type(limit) is not int or not 1<=limit<=20:raise ValueError('Invalid retrieval limit')
  if type(max_chars) is not int or not 200<=max_chars<=20000:raise ValueError('Invalid context budget')
  from .retrieval import rank
  with self.db.connect() as c:
   rows=[dict(r) for r in c.execute("SELECT * FROM knowledge WHERE project=? AND (scope='long' OR updated>?) ORDER BY updated DESC,key LIMIT 500",(project,time.time()-86400))]
  mode=os.getenv('TITAN_MEMORY_MODE','lexical')
  if mode=='semantic':
   from .semantic import rank as semantic_rank
   return semantic_rank(self.db,project,rows,query,limit,max_chars)
  if mode!='lexical':raise ValueError('Unknown memory retrieval mode')
  return rank(rows,query,limit,max_chars)
 def artifact(self,project,job,name,data,mime='application/octet-stream'):
  self.require(project)
  if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}',name):raise ValueError('Invalid artifact filename')
  if not isinstance(data,bytes) or len(data)>25_000_000:raise ValueError('Artifact exceeds 25 MB')
  # Root is trusted configuration; never follow artifact symlinks or user paths.
  aid=uuid.uuid4().hex;path=self.root/aid;sha=hashlib.sha256(data).hexdigest()
  cap=int(os.getenv('TITAN_ARTIFACT_BYTES','250000000'))
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   prior=c.execute('SELECT * FROM artifacts WHERE project=? AND job=? AND name=? AND sha256=?',(project,job,name,sha)).fetchone()
   if prior:return {'artifact_id':prior['id'],'name':name,'size':prior['size'],'sha256':sha,'mime':prior['mime']}
   used=c.execute('SELECT COALESCE(SUM(size),0) FROM artifacts').fetchone()[0]
   if used+len(data)>cap:raise ValueError('Artifact storage quota exceeded')
   fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   try:
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?)',(aid,project,job,name,mime,len(data),sha,time.time()))
   except BaseException:
    path.unlink(missing_ok=True);raise
  return {'artifact_id':aid,'name':name,'size':len(data),'sha256':sha,'mime':mime}
 def artifacts(self,project=None):
  with self.db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM artifacts WHERE (? IS NULL OR project=?) ORDER BY created DESC LIMIT 100',(project,project))]
 def read_artifact(self,aid):
  if not re.fullmatch('[a-f0-9]{32}',aid):raise KeyError(aid)
  with self.db.connect() as c:r=c.execute('SELECT * FROM artifacts WHERE id=?',(aid,)).fetchone()
  if not r:raise KeyError(aid)
  fd=os.open(self.root/aid,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as f:data=f.read(25_000_001)
  if len(data)!=r['size'] or hashlib.sha256(data).hexdigest()!=r['sha256']:raise ValueError('Artifact integrity failure')
  return dict(r),data
 def append_chat(self,project,role,content,provider=None):
  self.require(project)
  if role not in ('user','assistant') or not isinstance(content,str) or len(content)>20000:raise ValueError('Invalid chat message')
  from .security import redact
  with self.db.connect() as c:c.execute('INSERT INTO chat(project,role,content,provider,created) VALUES(?,?,?,?,?)',(project,role,redact(content),provider,time.time()))
 def history(self,project):
  self.require(project)
  with self.db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM (SELECT * FROM chat WHERE project=? ORDER BY id DESC LIMIT 40) ORDER BY id',(project,))]
 def schedule(self,project,objective,kind,payload,interval):
  self.require(project)
  if kind not in ('analysis','document','backtest','video','debate'):raise ValueError('Only bounded mission types can recur')
  if isinstance(interval,bool) or not isinstance(interval,int) or not 60<=interval<=31536000:raise ValueError('Interval must be 60 seconds–1 year')
  if not isinstance(objective,str) or not 1<=len(objective)<=12000 or not isinstance(payload,dict):raise ValueError('Invalid schedule')
  sid=uuid.uuid4().hex
  with self.db.connect() as c:c.execute('INSERT INTO schedules VALUES(?,?,?,?,?,?,?,1)',(sid,project,objective,kind,json.dumps(payload,allow_nan=False),interval,time.time()+interval))
  return sid
 def schedules(self):
  with self.db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM schedules ORDER BY next_run LIMIT 100')]
 def toggle_schedule(self,sid,enabled):
  if not isinstance(enabled,bool):raise ValueError('Boolean required')
  with self.db.connect() as c:
   if c.execute('UPDATE schedules SET enabled=? WHERE id=?',(int(enabled),sid)).rowcount!=1:raise KeyError(sid)
 def tick(self):
  now=time.time();created=[]
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   for r in c.execute('SELECT * FROM schedules WHERE enabled=1 AND next_run<=? LIMIT 20',(now,)).fetchall():
    # Coalesce missed ticks and avoid piling up the same recurring task.
    if not c.execute("SELECT 1 FROM jobs WHERE parent=? AND status IN ('queued','running','blocked','paused')",(r['id'],)).fetchone():
     mid=uuid.uuid4().hex
     c.execute("INSERT INTO jobs(id,objective,kind,payload,status,created,due,project,parent) VALUES(?,?,?,?, 'queued',?,?,?,?)",(mid,r['objective'],r['kind'],r['payload'],now,now,r['project'],r['id']))
     created.append(mid)
    c.execute('UPDATE schedules SET next_run=? WHERE id=?',(now+r['interval_seconds'],r['id']))
  return created
