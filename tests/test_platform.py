import asyncio,json,os,tempfile,threading,time,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from titan.store import Database,LostLease
from titan.engine import Worker,run_debate,analyze
from titan.providers import Router,ConfigurationError,ProviderError
from titan.security import redact,authenticate,public_https
from titan.tools import ToolRegistry
from titan.improvement import Improvements,no_regression
from titan.server import Server

class Base(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db';self.db=Database(self.path)
 def tearDown(self):self.temp.cleanup()
class Platform(Base):
 def test_persistence(self):
  mid=self.db.submit('persistent');self.assertEqual(Database(self.path).get(mid)['objective'],'persistent')
 def test_one_claim_among_workers(self):
  self.db.submit('race')
  with ThreadPoolExecutor(max_workers=8) as pool:r=list(pool.map(lambda _:self.db.claim(),range(8)))
  self.assertEqual(sum(x is not None for x in r),1)
 def test_crash_recovery_preserves_checkpoint(self):
  mid=self.db.submit('recovery');job,lease=self.db.claim();self.db.checkpoint(mid,lease,{'step':1})
  with self.db.connect() as c:c.execute('UPDATE jobs SET expires=0 WHERE id=?',(mid,))
  job2,lease2=Database(self.path).claim();self.assertNotEqual(lease,lease2);self.assertEqual(job2['checkpoint'],{'step':1})
  with self.assertRaises(LostLease):self.db.finish(mid,lease,{'stale':True})
 def test_crash_retry_exhaustion(self):
  mid=self.db.submit('crash',max_attempts=1);self.db.claim()
  with self.db.connect() as c:c.execute('UPDATE jobs SET expires=0')
  self.assertIsNone(self.db.claim());self.assertEqual(self.db.get(mid)['status'],'failed')
 def test_schedule(self):
  self.db.submit('later',due=time.time()+500);self.assertIsNone(self.db.claim())
 def test_pause_resume_cancel_fences_worker(self):
  mid=self.db.submit('control');j,l=self.db.claim();self.db.control(mid,'pause')
  with self.assertRaises(LostLease):self.db.finish(mid,l,{})
  self.db.control(mid,'resume');j,l=self.db.claim();self.db.control(mid,'cancel')
  with self.assertRaises(LostLease):self.db.checkpoint(mid,l,{})
  with self.assertRaises(ValueError):self.db.control(mid,'resume')
 def test_retry_backoff(self):
  mid=self.db.submit('fail');j,l=self.db.claim();self.db.fail(mid,l,'temporary');self.assertEqual(self.db.get(mid)['status'],'queued');self.assertIsNone(self.db.claim())
 def test_real_analysis_worker(self):
  mid=self.db.submit('Analyze sample','analysis',{'values':[10,20,30]});Worker(self.db).once();self.assertEqual(self.db.get(mid)['result']['mean'],20)
 def test_invalid_analysis(self):
  for v in [[],[True],[float('nan')],[float('inf')],['3'],[1e200]]:
   with self.assertRaises(ValueError):analyze(v)
 def test_missing_credentials_blocks(self):
  with patch.dict(os.environ,{},clear=True):
   mid=self.db.submit('live missing','debate',{'providers':['gemini','groq']});Worker(self.db).once();self.assertEqual(self.db.get(mid)['status'],'blocked')
 def test_memory_expiry(self):
  self.db.remember('old','temporary','short');self.db.remember('long','forever')
  with self.db.connect() as c:c.execute("UPDATE memory SET updated=0 WHERE key='old'")
  self.assertEqual([x['key'] for x in self.db.memories()],['long'])
 def test_debate_cross_examination_and_resume_mocked(self):
  calls=[]
  class Fake:
   async def call(self,p,m):calls.append((p,m));return json.dumps({k:[] for k in ['plan','evidence','risks','success_criteria','objections','questions','required_evidence','revisions','answers','unresolved','disputes','verification_steps']})
  mid=self.db.submit('test','debate',{'providers':['gemini','groq']});j,l=self.db.claim();r=asyncio.run(run_debate(self.db,j,l,Fake()))
  self.assertEqual(len(calls),7);self.assertEqual(r['verification'],'unverified_model_synthesis');self.assertIn('groq',calls[2][1][1]['content']);self.assertNotIn('"gemini":',calls[2][1][1]['content'])
  asyncio.run(run_debate(self.db,self.db.get(mid),l,Fake()));self.assertEqual(len(calls),7)
 def test_debate_partial_checkpoint_mocked(self):
  class Failing:
   async def call(self,p,m):
    if p=='groq':raise ProviderError('offline')
    return '{}'
  mid=self.db.submit('test','debate',{'providers':['gemini','groq']});j,l=self.db.claim()
  with self.assertRaises(ProviderError):asyncio.run(run_debate(self.db,j,l,Failing()))
  self.assertIn('gemini',self.db.get(mid)['checkpoint']['proposals'])
 def test_zero_spend_and_atomic_quota(self):
  with patch.dict(os.environ,{'TITAN_DAILY_USD':'0','TITAN_FREE_PROVIDERS':'','TITAN_DAILY_CALLS':'1'},clear=True):
   with self.assertRaises(ConfigurationError):Router(self.db).reserve('openai','m',[])
  with patch.dict(os.environ,{'TITAN_DAILY_USD':'0','TITAN_FREE_PROVIDERS':'groq','TITAN_DAILY_CALLS':'1'},clear=True):
   def reserve(_):
    try:Router(self.db).reserve('groq','m',[]);return True
    except ConfigurationError:return False
   with ThreadPoolExecutor(max_workers=4) as p:r=list(p.map(reserve,range(4)))
   self.assertEqual(sum(r),1)
 def test_adapter_payloads_mocked_http(self):
  for p,key in [('openai','OPENAI_API_KEY'),('claude','ANTHROPIC_API_KEY'),('groq','GROQ_API_KEY'),('gemini','GEMINI_API_KEY'),('deepseek','DEEPSEEK_API_KEY'),('grok','XAI_API_KEY')]:
   response={'content':[{'text':'test-shape'}]} if p=='claude' else {'choices':[{'message':{'content':'test-shape'}}]}
   with patch.dict(os.environ,{key:'TEST_ONLY','TITAN_FREE_PROVIDERS':p,'TITAN_DAILY_CALLS':'100','TITAN_DAILY_USD':'0'},clear=True),patch('titan.providers.request_json',return_value=response) as request:
    self.assertEqual(asyncio.run(Router(self.db).call(p,[{'role':'system','content':'RULE'},{'role':'user','content':'hello'}])),'test-shape')
    if p=='claude':self.assertEqual(request.call_args.args[2]['system'],'RULE')
 def test_secret_redaction(self):
  with patch.dict(os.environ,{'GROQ_API_KEY':'secret-value'}):self.assertEqual(redact('key secret-value Bearer abc123'),'key [REDACTED] Bearer [REDACTED]')
 def test_auth(self):
  self.assertFalse(authenticate(None,'x'));self.assertFalse(authenticate('Bearer bad','good'));self.assertTrue(authenticate('Bearer good','good'))
 def test_private_network_rejected(self):
  with self.assertRaises(PermissionError):public_https('http://example.com',['example.com'])
  with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
   with self.assertRaises(PermissionError):public_https('https://example.com',['example.com'])
 def test_approval_bound_exactly_and_one_use(self):
  t=ToolRegistry(self.db);a=t.request('job','github.read',{'repository':'x/y'});t.approve(a['id'])
  with patch.object(t,'dispatch',return_value={'ok':True}):
   with self.assertRaises(PermissionError):t.execute('job','github.read',{'repository':'x/z'})
   self.assertEqual(t.execute('job','github.read',{'repository':'x/y'}),{'ok':True})
   with self.assertRaises(PermissionError):t.execute('job','github.read',{'repository':'x/y'})
 def test_sandbox_fail_closed(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(ConfigurationError):ToolRegistry(self.db).sandbox({'code':'print(1)'})
 def test_benchmark_rejects_regression(self):
  i=Improvements(self.db);self.assertEqual(i.evaluate({'description':'baseline'})['status'],'benchmark_passed');self.assertEqual(i.evaluate({'description':'broken'},lambda x:{})['status'],'rejected');self.assertFalse(no_regression({'a':1},{'a':float('nan')}));self.assertFalse(no_regression({'a':1},{}))
 def test_no_code_promotion(self):
  with self.assertRaises(ValueError):Improvements(self.db).evaluate({'code':'print(1)'})
class HTTPTests(Base):
 def setUp(self):
  super().setUp();self.token='t'*40;self.server=Server(('127.0.0.1',0),self.db,self.token);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();super().tearDown()
 def req(self,path,data=None,auth=True,headers=None):
  h={'Authorization':'Bearer '+self.token} if auth else {}
  if data is not None:h['Content-Type']='application/json'
  h.update(headers or {})
  return urlopen(Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers=h),timeout=5)
 def test_api_requires_auth(self):
  with self.assertRaises(HTTPError) as e:self.req('/api/state',auth=False)
  self.assertEqual(e.exception.code,401)
 def test_http_end_to_end_analysis(self):
  r=json.load(self.req('/api/missions',{'objective':'HTTP demo','kind':'analysis','payload':{'values':[1,3,5]}}));Worker(self.db).once();state=json.load(self.req('/api/state'));self.assertEqual(state['missions'][0]['id'],r['id']);self.assertEqual(state['missions'][0]['result']['mean'],3)
 def test_origin_boundary(self):
  with self.assertRaises(HTTPError) as e:self.req('/api/memory',{'key':'x','value':'y'},headers={'Origin':'https://evil.example'})
  self.assertEqual(e.exception.code,403)
 def test_static_and_path_traversal(self):
  r=self.req('/',auth=False);self.assertIn(b'TITAN',r.read());self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
  with self.assertRaises(HTTPError):self.req('/../server.py',auth=False)
 def test_malformed_mission(self):
  with self.assertRaises(HTTPError) as e:self.req('/api/missions',{'objective':'x','payload':{'providers':['gemini','gemini']}})
  self.assertEqual(e.exception.code,400)
 def test_memory_benchmark_api(self):
  self.req('/api/memory',{'key':'project','value':'TITAN'}).close();r=json.load(self.req('/api/benchmark',{}));self.assertFalse(r['promoted']);self.assertEqual(r['status'],'benchmark_passed')
if __name__=='__main__':unittest.main()

class PolicyTests(Base):
 def test_promotion_and_rollback(self):
  from titan import policy
  weights=dict(policy.DEFAULT,reliability=2)
  r=policy.propose(self.db,weights);self.assertEqual(r['status'],'policy_passed')
  policy.promote(self.db,r['id']);self.assertEqual(policy.active(self.db),weights)
  policy.rollback(self.db,r['id']);self.assertEqual(policy.active(self.db),policy.DEFAULT)
 def test_rejected_policy_cannot_promote(self):
  from titan import policy
  r=policy.propose(self.db,{k:0 for k in policy.DEFAULT});self.assertEqual(r['status'],'rejected')
  with self.assertRaises(ValueError):policy.promote(self.db,r['id'])

class WorkflowTests(Base):
 def test_dependency_execution(self):
  mid=self.db.submit('workflow','workflow',{'steps':[{'id':'b','kind':'analysis','values':[3,5],'depends_on':['a']},{'id':'a','kind':'analysis','values':[1,2]}]});Worker(self.db).once();r=self.db.get(mid);self.assertEqual(list(r['result']['steps']),['a','b'])
 def test_cycle_rejected(self):
  mid=self.db.submit('cycle','workflow',{'steps':[{'id':'a','kind':'analysis','values':[1],'depends_on':['b']},{'id':'b','kind':'analysis','values':[2],'depends_on':['a']}]});Worker(self.db).once();self.assertIn('cycle',self.db.get(mid)['error'])
 def test_workflow_resume_checkpoint(self):
  mid=self.db.submit('approval workflow','workflow',{'steps':[{'id':'a','kind':'analysis','values':[1]},{'id':'b','kind':'tool','tool':'github.read','arguments':{'repository':'x/y'},'depends_on':['a']}]});Worker(self.db).once();r=self.db.get(mid);self.assertEqual(r['status'],'blocked');self.assertIn('a',r['checkpoint']['steps'])

class MCPTests(unittest.TestCase):
 def test_handshake_mocked(self):
  from titan.mcp import Client
  client=Client('https://example.com/mcp')
  with patch.object(client,'send',side_effect=[{'result':{'protocolVersion':'2025-03-26'}},None,{'result':{'content':[]}}]) as send:
   self.assertEqual(client.call('read',{}),{'content':[]});self.assertEqual(send.call_args_list[1].args[0]['method'],'notifications/initialized')

class RecoveryTests(Base):
 def test_actual_worker_process_exit(self):
  import subprocess,sys
  mid=self.db.submit('process crash')
  code="import sys,os;from titan.store import Database;d=Database(sys.argv[1]);j,l=d.claim(ttl=.2);d.checkpoint(j['id'],l,{'saved':True});os._exit(9)"
  r=subprocess.run([sys.executable,'-c',code,str(self.path)],capture_output=True)
  self.assertEqual(r.returncode,9);time.sleep(.25)
  job,lease=Database(self.path).claim();self.assertEqual(job['id'],mid);self.assertTrue(job['checkpoint']['saved'])
 def test_backup_reopens(self):
  from titan.backup import backup
  mid=self.db.submit('backup');target=Path(self.temp.name)/'backup.db';backup(str(self.path),str(target));self.assertEqual(Database(target).get(mid)['objective'],'backup')
 def test_cycle_has_no_partial_effects(self):
  mid=self.db.submit('cycle before actions','workflow',{'steps':[{'id':'safe','kind':'analysis','values':[1]},{'id':'a','kind':'analysis','values':[1],'depends_on':['b']},{'id':'b','kind':'analysis','values':[1],'depends_on':['a']}]});Worker(self.db).once();self.assertEqual(self.db.get(mid)['checkpoint'],{})
