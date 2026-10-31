"""Real API-to-worker-to-artifact demonstration. No external model fixture is used."""
import hashlib,json,secrets,tempfile,threading,time
from pathlib import Path
from urllib.request import Request,urlopen
from titan.store import Database
from titan.server import Server
from titan.engine import Worker
from titan.backup import backup

output=Path('docs/evidence');output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as d:
 db=Database(Path(d)/'demo.db');token=secrets.token_urlsafe(32);server=Server(('127.0.0.1',0),db,token);thread=threading.Thread(target=server.serve_forever);thread.start()
 base='http://127.0.0.1:'+str(server.server_port)
 def request(path,data=None,raw=False):
  headers={'Authorization':'Bearer '+token}
  if data is not None:headers['Content-Type']='application/json'
  with urlopen(Request(base+'/api/'+path,headers=headers,data=None if data is None else json.dumps(data).encode()),timeout=10) as response:return response.read() if raw else json.load(response)
 try:
  project=request('projects',{'name':'Verified local demonstration'})['id']
  request('knowledge',{'project':project,'key':'input-provenance','value':'Synthetic sample data for software testing; not live market data'})
  team=request('missions',{'project':project,'objective':'Create a local research package','kind':'team','payload':{'tasks':[{'objective':'Analyze durations','kind':'analysis','payload':{'values':[24,26,25,25]}},{'objective':'Write report','kind':'document','payload':{'title':'TITAN verified local demo','text':'This report was generated through the authenticated API and a durable child worker. Inputs are synthetic. External AI calls: zero.'}},{'objective':'Paper simulation','kind':'backtest','payload':{'prices':[100,101,102,103,102,104,105,106,104,107],'window':3,'fee_bps':10}}]}})['id']
  worker=Worker(db)
  for _ in range(6):worker.once()
  assert db.get(team)['status']=='completed'
  video=request('missions',{'project':project,'objective':'Render local preview','kind':'video','payload':{'title':'TITAN VERIFIED LOCAL DEMO','seconds':3}})['id'];worker.once();assert db.get(video)['status']=='completed',db.get(video)
  state=request('state');saved=[]
  for artifact in state['artifacts']:
   raw=request('artifacts/'+artifact['id'],raw=True);assert hashlib.sha256(raw).hexdigest()==artifact['sha256']
   dest=output/artifact['name'];dest.write_bytes(raw);saved.append({'name':dest.name,'size':len(raw),'sha256':artifact['sha256']})
  backup(db.path,str(Path(d)/'restore.db'));reopened=Database(Path(d)/'restore.db');assert reopened.get(team)['result']['all_succeeded']
  result={'date_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'model_calls':0,'project':project,'team':db.get(team),'video':db.get(video),'artifacts':saved,'api_download_hashes_verified':True,'database_restore_verified':True}
  (output/'integrated-demo.json').write_text(json.dumps(result,indent=2));print(json.dumps({'team_status':result['team']['status'],'child_count':len(result['team']['result']['children']),'video_status':result['video']['status'],'artifacts':saved,'restore':True},indent=2))
 finally:server.shutdown();server.server_close();thread.join()
