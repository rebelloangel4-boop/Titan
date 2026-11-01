"""Optional CPU semantic memory. Pinned model; explicit download; no remote code."""
import argparse,hashlib,json,math,os,threading

MODEL='sentence-transformers/all-MiniLM-L6-v2'
REVISION='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
IDENTITY=MODEL+'@'+REVISION+':chunks1000x4:v1'
_model=None
_lock=threading.Lock()

class SemanticUnavailable(RuntimeError):pass

def load_model(download=False):
 global _model
 with _lock:
  if _model is None:
   try:
    from sentence_transformers import SentenceTransformer
    _model=SentenceTransformer(MODEL,revision=REVISION,device='cpu',trust_remote_code=False,local_files_only=not download,token=False,model_kwargs={'use_safetensors':True})
    _model.max_seq_length=256
   except Exception:
    raise SemanticUnavailable('Semantic model unavailable. Install requirements-semantic.txt and run python -m titan.semantic --download on the host.') from None
  return _model

def embed(texts):
 model=load_model()
 with _lock:
  vectors=model.encode(texts,batch_size=16,normalize_embeddings=True,show_progress_bar=False).tolist()
 return [validate_vector(v) for v in vectors]

def validate_vector(value):
 if not isinstance(value,list) or not 1<=len(value)<=4096 or any(type(x) not in (int,float) or not math.isfinite(x) for x in value):raise ValueError('Invalid embedding')
 norm=math.sqrt(sum(x*x for x in value))
 if norm<1e-10:raise ValueError('Zero embedding')
 return [x/norm for x in value]

def chunks(record):
 text=record['key']+'\n'+record['value']
 return [text[i:i+1000] for i in range(0,min(len(text),4000),1000)]

def rank(db,project,records,query,limit,max_chars):
 if not query.strip() or not records:return []
 # records have already been scoped and expiry-filtered by Workspace.retrieve.
 q=embed([query[:4000]])[0]
 with db.connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS embeddings(project TEXT,key TEXT,model TEXT,content_hash TEXT,vectors TEXT,PRIMARY KEY(project,key,model))')
  cached={r['key']:dict(r) for r in c.execute('SELECT * FROM embeddings WHERE project=? AND model=?',(project,IDENTITY))}
 scored=[]
 for record in records:
  content_hash=hashlib.sha256(json.dumps([record['key'],record['value']],ensure_ascii=False).encode()).hexdigest()
  row=cached.get(record['key']);vectors=None
  if row and row['content_hash']==content_hash:
   try:
    raw=json.loads(row['vectors'])
    if not isinstance(raw,list) or not 1<=len(raw)<=4:raise ValueError('Invalid cached chunks')
    vectors=[validate_vector(v) for v in raw]
    if any(len(v)!=len(q) for v in vectors):vectors=None
   except (ValueError,TypeError):vectors=None
  if vectors is None:
   vectors=embed(chunks(record))
   if any(len(v)!=len(q) for v in vectors):raise ValueError('Embedding dimensions changed')
   with db.connect() as c:
    c.execute('INSERT OR REPLACE INTO embeddings VALUES(?,?,?,?,?)',(project,record['key'],IDENTITY,content_hash,json.dumps(vectors)))
  score=max(sum(a*b for a,b in zip(q,v)) for v in vectors)
  if score>=0.25:scored.append((score,record))
 scored.sort(key=lambda x:(-x[0],-x[1]['updated'],x[1]['key']))
 result=[];used=0
 for score,record in scored[:limit]:
  remaining=max_chars-used-len(record['key'])
  if remaining<=0:break
  value=record['value'][:remaining];used+=len(record['key'])+len(value)
  result.append({**record,'value':value,'score':round(score,6),'retrieval':'semantic_minilm','embedding_model':IDENTITY,'embedding_truncated':len(record['key'])+1+len(record['value'])>4000,'truncated':len(value)<len(record['value'])})
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');a=p.parse_args()
 if not a.download:p.error('Use --download to explicitly provision the pinned model')
 load_model(download=True);print('Pinned semantic model is ready: '+IDENTITY)
