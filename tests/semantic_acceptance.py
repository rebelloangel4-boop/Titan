"""Real pinned model benchmark. No provider API or synthetic embeddings."""
import hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from titan.store import Database
from titan.workspace import Workspace
from titan.semantic import MODEL,REVISION

def main():
 raw=Path('benchmarks/semantic.json').read_bytes();suite=json.loads(raw)
 os.environ['TITAN_MEMORY_MODE']='semantic';results=[];started=time.monotonic()
 with tempfile.TemporaryDirectory() as d:
  path=Path(d)/'state.db';db=Database(path);ws=Workspace(db)
  for key,text in suite['memories'].items():ws.remember('default',key,text)
  other=ws.create_project('private');ws.remember(other,'private','My car engine gets too hot. What should I do?')
  ws.remember('default','expired','My car engine gets too hot. What should I do?','short')
  with db.connect() as c:c.execute("UPDATE knowledge SET updated=0 WHERE key='expired'")
  for case in suite['queries']:
   matches=ws.retrieve('default',case['query'])
   assert all(m['key'] not in ('private','expired') for m in matches),'Isolation failure'
   top=matches[0]['key'] if matches else None
   results.append({**case,'actual':top,'passed':top==case['expected']})
  accuracy=sum(r['passed'] for r in results)/len(results)
  # A separate process must reuse persisted document vectors, not re-embed them.
  code='''import sys,json
from titan.store import Database
from titan.workspace import Workspace
from titan import semantic
original=semantic.embed
query="My car engine gets too hot. What should I do?"
def query_only(texts):
 assert texts==[query],"Document embeddings were not restored from SQLite"
 return original(texts)
semantic.embed=query_only
print(json.dumps(Workspace(Database(sys.argv[1])).retrieve('default',query)))
'''
  child=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,timeout=120,check=True)
  assert json.loads(child.stdout)[0]['key']=='m1','Restart retrieval failed'
  ws.remember('default','m1','A completely unrelated recipe for chocolate cake.')
  updated=ws.retrieve('default',suite['queries'][0]['query'])
  assert not updated or updated[0]['key']!='m1','Stale vector after update'
 report={'model':MODEL,'revision':REVISION,'suite_sha256':hashlib.sha256(raw).hexdigest(),'top1_accuracy':accuracy,'required_accuracy':suite['minimum_top1_accuracy'],'queries':results,'project_isolation':True,'expired_memory_excluded':True,'process_restart_cache':True,'update_invalidation':True,'elapsed_seconds':round(time.monotonic()-started,3),'external_inference_calls':0}
 Path('docs/evidence/semantic-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 assert accuracy>=suite['minimum_top1_accuracy'],'Frozen semantic benchmark failed'

if __name__=='__main__':main()
