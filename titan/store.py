"""SQLite durable queue. Each operation has its own connection; leases fence stale workers."""
import json, sqlite3, time, uuid
from contextlib import contextmanager

class LostLease(RuntimeError): pass

class Database:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, objective TEXT NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
              due REAL NOT NULL, attempts INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 3,
              lease TEXT, expires REAL, checkpoint TEXT DEFAULT '{}', result TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, job TEXT, ts REAL, kind TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS memory(key TEXT PRIMARY KEY, value TEXT, scope TEXT, updated REAL);
            CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY, provider TEXT, model TEXT, ts REAL, status TEXT, latency REAL, cost REAL, quality REAL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, job TEXT, tool TEXT, digest TEXT, status TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS improvements(id TEXT PRIMARY KEY, candidate TEXT, baseline TEXT, scores TEXT, status TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS due_jobs ON jobs(status,due);
            ''')
            c.execute('BEGIN IMMEDIATE')
            columns={r[1] for r in c.execute('PRAGMA table_info(approvals)')}
            if 'arguments' not in columns:c.execute("ALTER TABLE approvals ADD COLUMN arguments TEXT DEFAULT '{}'")
    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        try:
            with c: yield c
        finally: c.close()
    def submit(self, objective, kind='debate', payload=None, due=None, max_attempts=3, project='default', parent=None):
        if not isinstance(objective,str) or not 1 <= len(objective.strip()) <= 12000: raise ValueError('Objective must be 1–12000 characters')
        if kind not in ('debate','analysis','tool','workflow','agent','chat','document','backtest','video','team','code','model_benchmark'): raise ValueError('Unsupported mission kind')
        from .workspace import Workspace
        Workspace(self).require(project)
        if not isinstance(payload or {},dict):raise ValueError('Payload must be an object')
        if not isinstance(max_attempts,int) or not 1<=max_attempts<=10:raise ValueError('Invalid attempts')
        mid=uuid.uuid4().hex
        with self.connect() as c:
            c.execute('INSERT INTO jobs(id,objective,kind,payload,status,created,due,max_attempts,project,parent) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (mid,objective,kind,json.dumps(payload or {}),'queued',time.time(),due or time.time(),max_attempts,project,parent))
        self.event(mid,'queued','Mission saved')
        return mid
    def get(self, mid):
        with self.connect() as c:
            row=c.execute('SELECT * FROM jobs WHERE id=?',(mid,)).fetchone()
        if not row: return None
        d=dict(row)
        for k in ('payload','checkpoint','result'):
            if d[k]: d[k]=json.loads(d[k])
        d.pop('lease',None)
        return d
    def list(self):
        with self.connect() as c: ids=[r[0] for r in c.execute('SELECT id FROM jobs ORDER BY created DESC LIMIT 200')]
        return [self.get(i) for i in ids]
    def claim(self, ttl=90):
        now=time.time()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE jobs SET status=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'queued' END,lease=NULL,error='Worker lease expired' WHERE status='running' AND expires<?",(now,))
            columns={r[1] for r in c.execute('PRAGMA table_info(jobs)')}
            if 'parent' in columns:c.execute("UPDATE jobs SET status='queued' WHERE status='waiting' AND EXISTS(SELECT 1 FROM jobs child WHERE child.parent=jobs.id) AND NOT EXISTS(SELECT 1 FROM jobs child WHERE child.parent=jobs.id AND child.status NOT IN ('completed','failed','cancelled'))")
            r=c.execute("SELECT id FROM jobs WHERE status='queued' AND due<=? AND attempts<max_attempts ORDER BY due LIMIT 1",(now,)).fetchone()
            if not r:return None
            lease=uuid.uuid4().hex
            c.execute("UPDATE jobs SET status='running',lease=?,expires=?,attempts=attempts+1 WHERE id=?",(lease,now+ttl,r[0]))
        self.event(r[0],'running','Worker claimed mission')
        return self.get(r[0]),lease
    def owned(self, c, mid, lease):
        if not c.execute("SELECT 1 FROM jobs WHERE id=? AND lease=? AND status='running' AND expires>?",(mid,lease,time.time())).fetchone(): raise LostLease('Mission paused, cancelled, or lease expired')
    def heartbeat(self,mid,lease,ttl=90):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');self.owned(c,mid,lease)
            c.execute('UPDATE jobs SET expires=? WHERE id=?',(time.time()+ttl,mid))
    def checkpoint(self,mid,lease,state):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');self.owned(c,mid,lease)
            c.execute('UPDATE jobs SET checkpoint=? WHERE id=?',(json.dumps(state),mid))
    def finish(self,mid,lease,result):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');self.owned(c,mid,lease)
            row=c.execute('SELECT kind,project,objective FROM jobs WHERE id=?',(mid,)).fetchone()
            if row['kind']=='model_benchmark':
                for provider,score in result['scores'].items():c.execute('INSERT OR REPLACE INTO provider_quality VALUES(?,?,?,?,?,?)',(provider,result['models'][provider],result['suite_sha256'],mid,score,time.time()))
            if row['kind']=='chat':
                from .security import redact
                for role,content in [('user',row['objective']),('assistant',result['content'])]:c.execute('INSERT INTO chat(project,role,content,provider,created) VALUES(?,?,?,?,?)',(row['project'] or 'default',role,redact(content),result.get('provider'),time.time()))
            c.execute("UPDATE jobs SET status='completed',result=?,lease=NULL,error=NULL WHERE id=?",(json.dumps(result),mid))
        self.event(mid,'completed','Result persisted; see verification label')
    def fail(self,mid,lease,error,blocked=False):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');self.owned(c,mid,lease)
            attempts,maximum=c.execute('SELECT attempts,max_attempts FROM jobs WHERE id=?',(mid,)).fetchone()
            state='blocked' if blocked else ('failed' if attempts>=maximum else 'queued')
            c.execute('UPDATE jobs SET status=?,error=?,due=?,lease=NULL WHERE id=?',(state,error,time.time()+min(300,2**attempts),mid))
        self.event(mid,state,error)
    def control(self,mid,action):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT status FROM jobs WHERE id=?',(mid,)).fetchone()
            if not row: raise KeyError(mid)
            allowed={'pause':({'queued','running','waiting'},'paused'),'resume':({'paused','blocked','failed'},'queued'),'cancel':({'queued','running','waiting','paused','blocked','failed'},'cancelled')}
            if action not in allowed or row[0] not in allowed[action][0]: raise ValueError('Invalid state transition')
            c.execute('UPDATE jobs SET status=?,lease=NULL,expires=NULL,attempts=CASE WHEN ?=\'resume\' THEN 0 ELSE attempts END WHERE id=?',(allowed[action][1],action,mid))
            if action=='cancel':c.execute("UPDATE jobs SET status='cancelled',lease=NULL WHERE parent=? AND status NOT IN ('completed','failed','cancelled')",(mid,))
            elif action=='pause':c.execute("UPDATE jobs SET status='paused',lease=NULL WHERE parent=? AND status IN ('queued','running')",(mid,))
            elif action=='resume':c.execute("UPDATE jobs SET status='queued',attempts=0 WHERE parent=? AND status='paused'",(mid,))
        self.event(mid,action,'Operator control')
    def event(self,mid,kind,detail):
        from .security import redact
        with self.connect() as c:c.execute('INSERT INTO events(job,ts,kind,detail) VALUES(?,?,?,?)',(mid,time.time(),kind,redact(str(detail))[:16000]))
    def events(self,mid=None):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT * FROM events WHERE (? IS NULL OR job=?) ORDER BY id DESC LIMIT 200',(mid,mid))]
    def remember(self,key,value,scope='long'):
        if scope not in ('short','long'):raise ValueError('Invalid memory scope')
        if not key or len(key)>200 or len(value)>20000:raise ValueError('Memory too large')
        from .security import redact
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO memory VALUES(?,?,?,?)',(key,redact(value),scope,time.time()))
    def memories(self):
        with self.connect() as c:return [dict(r) for r in c.execute("SELECT * FROM memory WHERE scope='long' OR updated>? ORDER BY updated DESC LIMIT 100",(time.time()-86400,))]
