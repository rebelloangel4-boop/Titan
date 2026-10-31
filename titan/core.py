import asyncio, json, os, sqlite3, time, uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

PROVIDERS = {
 'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions','GEMINI_API_KEY','gemini-2.5-flash'),
 'groq': ('https://api.groq.com/openai/v1/chat/completions','GROQ_API_KEY','llama-3.3-70b-versatile'),
 'openai': ('https://api.openai.com/v1/chat/completions','OPENAI_API_KEY','gpt-4.1-mini'),
 'claude': ('https://api.anthropic.com/v1/messages','ANTHROPIC_API_KEY','claude-sonnet-4-5'),
 'deepseek': ('https://api.deepseek.com/chat/completions','DEEPSEEK_API_KEY','deepseek-chat'),
 'grok': ('https://api.x.ai/v1/chat/completions','XAI_API_KEY','grok-4'),
}

class Store:
 def __init__(self, path='titan.db'):
  self.db=sqlite3.connect(path)
  self.db.execute('CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY, objective TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created REAL NOT NULL)')
  self.db.execute('CREATE TABLE IF NOT EXISTS evaluations (id INTEGER PRIMARY KEY, mission_id TEXT, candidate TEXT, score INTEGER, notes TEXT)')
  self.db.commit()
 def create(self, objective):
  mid=str(uuid.uuid4()); self.db.execute('INSERT INTO missions VALUES (?,?,?,?,?)',(mid,objective,'queued',None,time.time()));self.db.commit();return mid
 def update(self, mid, status, result=None):
  self.db.execute('UPDATE missions SET status=?, result=? WHERE id=?',(status,result,mid));self.db.commit()
 def get(self, mid):
  row=self.db.execute('SELECT id,objective,status,result FROM missions WHERE id=?',(mid,)).fetchone()
  return dict(zip(('id','objective','status','result'),row)) if row else None
 def evaluate(self, mid, candidate, score, notes):
  self.db.execute('INSERT INTO evaluations (mission_id,candidate,score,notes) VALUES (?,?,?,?)',(mid,candidate,score,notes));self.db.commit()

async def call_model(provider, messages, timeout=45):
 """Compatibility adapter; production missions should use the durable Worker API."""
 from .store import Database
 from .providers import Router
 return await Router(Database(os.getenv('TITAN_DB','titan.db'))).call(provider,messages)

async def debate(objective, providers, store, model_call=call_model):
 if len(set(providers))<2: raise ValueError('At least two distinct providers required')
 mid=store.create(objective);store.update(mid,'running')
 try:
  prompt='Propose a concrete, testable plan for this mission. Explicitly identify failure modes and uncertainties:\n'+objective
  proposals=await asyncio.gather(*(model_call(p,[{'role':'user','content':prompt}]) for p in providers),return_exceptions=True)
  valid={p:r for p,r in zip(providers,proposals) if isinstance(r,str) and r.strip()}
  if len(valid)<2: raise RuntimeError('Fewer than two independent model responses succeeded')
  critiques={}
  for p in valid:
   others='\n'.join(f'{k}: {v[:5000]}' for k,v in valid.items() if k!=p)
   critiques[p]=await model_call(p,[{'role':'user','content':'Critically review the OTHER proposals. Identify concrete errors, missing evidence, and fixes. Do not rubber stamp.\n'+others}])
  judge=next(iter(valid))
  result=await model_call(judge,[{'role':'user','content':'Synthesize the strongest verifiable plan. State unresolved disputes. Do not claim tests were run.\nPROPOSALS:\n'+json.dumps(valid)+'\nCRITIQUES:\n'+json.dumps(critiques)}])
  store.evaluate(mid,judge,0,'Unverified synthesis; objective scoring requires external tests')
  store.update(mid,'completed',json.dumps({'proposals':valid,'critiques':critiques,'synthesis':result}))
 except Exception as e:
  from .security import redact
  store.update(mid,'failed',redact(str(e)));raise
 return mid
