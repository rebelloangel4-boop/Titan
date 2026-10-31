"""Fixed benchmark gate. Candidates are inert JSON config, never executable source."""
import json,time,uuid,math
from .engine import analyze

CASES=[([1,2,3],{'count':3,'sum':6,'mean':2,'median':2}),([-5,0,5],{'count':3,'sum':0,'mean':0,'median':0}),([2.5],{'count':1,'sum':2.5,'mean':2.5,'median':2.5})]
def benchmark(fn=analyze):
    scores={}
    for i,(values,expected) in enumerate(CASES):
        try:r=fn(values);scores[str(i)]=int(all(r.get(k)==v for k,v in expected.items()))
        except Exception:scores[str(i)]=0
    return scores

def no_regression(baseline,candidate):
    return bool(baseline) and baseline.keys()==candidate.keys() and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=baseline[k] for k,v in candidate.items())

class Improvements:
    def __init__(self,db):self.db=db
    def propose(self):
        with self.db.connect() as c:
            failures=[dict(r) for r in c.execute("SELECT error,COUNT(*) count FROM jobs WHERE error IS NOT NULL GROUP BY error ORDER BY count DESC LIMIT 10")]
        return {'failure_patterns':failures,'suggestions':[{'change':'Investigate '+r['error'],'evidence_count':r['count'],'state':'proposal_only'} for r in failures]}
    def evaluate(self,candidate,fn=analyze):
        # This gate tests analysis behavior only, never claims to score language-model quality.
        if set(candidate)-{'description'}:raise ValueError('Only descriptive candidates supported; production mutation prohibited')
        baseline=benchmark();scores=benchmark(fn);iid=uuid.uuid4().hex
        state='benchmark_passed' if no_regression(baseline,scores) else 'rejected'
        with self.db.connect() as c:c.execute('INSERT INTO improvements VALUES(?,?,?,?,?,?)',(iid,json.dumps(candidate),json.dumps(baseline),json.dumps(scores),state,time.time()))
        return {'id':iid,'status':state,'baseline':baseline,'scores':scores,'promoted':False,'scope':'Fixed deterministic analysis suite only'}
    def list(self):
        with self.db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM improvements ORDER BY created DESC LIMIT 100')]
