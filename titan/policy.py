"""Versioned routing configurations evaluated against fixed synthetic preference cases."""
import json,math,time,uuid
DEFAULT={'reliability':1.0,'quality':0.5,'latency':1/120,'cost':1.0}
def score(metric,policy):
 return metric.get('success_rate',.5)*policy['reliability']+(metric.get('quality') or 0)*policy['quality']-(metric.get('latency') or 0)*policy['latency']-(metric.get('cost') or 0)*policy['cost']
def validate(p):
 if set(p)!=set(DEFAULT) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=10 for v in p.values()):raise ValueError('Invalid routing weights')
 return p
CASES=[({'success_rate':1},{'success_rate':.1}),({'quality':1},{'quality':0}),({'latency':1},{'latency':60}),({'cost':0},{'cost':1})]
def evaluate(p):
 validate(p)
 return {str(i):int(score(good,p)>score(bad,p)) for i,(good,bad) in enumerate(CASES)}
def active(db):
 with db.connect() as c:r=c.execute("SELECT value FROM settings WHERE key='routing_policy'").fetchone()
 return json.loads(r[0]) if r else DEFAULT.copy()
def propose(db,policy):
 from .improvement import no_regression
 validate(policy);baseline=evaluate(active(db));result=evaluate(policy);iid=uuid.uuid4().hex
 status='policy_passed' if no_regression(baseline,result) else 'rejected'
 with db.connect() as c:c.execute('INSERT INTO improvements VALUES(?,?,?,?,?,?)',(iid,json.dumps({'routing_policy':policy,'previous':active(db)}),json.dumps(baseline),json.dumps(result),status,time.time()))
 return {'id':iid,'status':status,'scores':result,'scope':'Synthetic routing preference cases; not live AI quality'}
def promote(db,iid):
 from .improvement import no_regression
 with db.connect() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM improvements WHERE id=?',(iid,)).fetchone()
  if not row or row['status']!='policy_passed':raise ValueError('Candidate has not passed')
  candidate=json.loads(row['candidate']);p=validate(candidate['routing_policy'])
  current=c.execute("SELECT value FROM settings WHERE key='routing_policy'").fetchone();previous=json.loads(current[0]) if current else DEFAULT.copy()
  if not no_regression(evaluate(previous),evaluate(p)):raise ValueError('Regression against current baseline')
  candidate['previous']=previous
  c.execute("INSERT OR REPLACE INTO settings VALUES('routing_policy',?)",(json.dumps(p),))
  c.execute("UPDATE improvements SET status='promoted',candidate=? WHERE id=?",(json.dumps(candidate),iid))
 db.event(None,'policy_promoted',iid)
def rollback(db,iid):
 with db.connect() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM improvements WHERE id=?',(iid,)).fetchone()
  if not row or row['status']!='promoted':raise ValueError('No promoted candidate')
  candidate=json.loads(row['candidate']);current=c.execute("SELECT value FROM settings WHERE key='routing_policy'").fetchone()
  if not current or json.loads(current[0])!=candidate['routing_policy']:raise ValueError('Rollback newer policies first')
  c.execute("INSERT OR REPLACE INTO settings VALUES('routing_policy',?)",(json.dumps(candidate['previous']),))
  c.execute("UPDATE improvements SET status='rolled_back' WHERE id=?",(iid,))
 db.event(None,'policy_rolled_back',iid)
