import asyncio,json,os,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from titan.store import Database
from titan.workspace import Workspace
from titan.engine import Worker
from titan.providers import Router,ProviderError,ConfigurationError,compact_context
from titan.agents import validate_plan
from titan.domains import backtest
from test_platform import Base
import test_platform as platform_tests

class Extended(Base):
 def setUp(self):super().setUp();self.ws=Workspace(self.db)
 def test_project_search_isolation(self):
  a=self.ws.create_project('A');b=self.ws.create_project('B');self.ws.remember(a,'alpha','hello world');self.ws.remember(b,'beta','secret')
  self.assertEqual(len(self.ws.search(a,'world')),1);self.assertEqual(self.ws.search(a,'secret'),[]);self.assertEqual(self.ws.search(a,'%'),[])
 def test_artifact_integrity_and_path(self):
  a=self.ws.artifact('default','job','hello.txt',b'hello','text/plain');self.assertEqual(self.ws.read_artifact(a['artifact_id'])[1],b'hello')
  with self.assertRaises(ValueError):self.ws.artifact('default','job','../x',b'bad')
  (self.ws.root/a['artifact_id']).write_bytes(b'wrong')
  with self.assertRaises(ValueError):self.ws.read_artifact(a['artifact_id'])
 def test_artifact_symlink(self):
  a=self.ws.artifact('default','j','x.txt',b'ok');p=self.ws.root/a['artifact_id'];p.unlink();p.symlink_to(self.path)
  with self.assertRaises(OSError):self.ws.read_artifact(a['artifact_id'])
 def test_artifact_quota(self):
  with patch.dict(os.environ,{'TITAN_ARTIFACT_BYTES':'3'}):
   with self.assertRaises(ValueError):self.ws.artifact('default','j','x.txt',b'1234')
 def test_scheduler_atomic_coalesced(self):
  sid=self.ws.schedule('default','scheduled','analysis',{'values':[1,2]},60)
  with self.db.connect() as c:c.execute('UPDATE schedules SET next_run=0')
  with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:self.ws.tick(),range(6)))
  self.assertEqual(sum(map(len,results)),1)
  with self.db.connect() as c:c.execute('UPDATE schedules SET next_run=0')
  self.assertEqual(self.ws.tick(),[]);self.ws.toggle_schedule(sid,False)
 def test_team_durable_children(self):
  mid=self.db.submit('team','team',{'tasks':[{'objective':'a','kind':'analysis','payload':{'values':[1,2]}},{'objective':'b','kind':'document','payload':{'text':'deliverable'}}]})
  w=Worker(self.db);w.once();self.assertEqual(self.db.get(mid)['status'],'waiting');w.once();w.once();w.once();self.assertTrue(self.db.get(mid)['result']['all_succeeded'])
  self.assertEqual(len(self.db.list()),3)
 def test_team_cancel_children(self):
  mid=self.db.submit('team','team',{'tasks':[{'objective':'a','kind':'analysis','payload':{'values':[1]}}]});Worker(self.db).once();self.db.control(mid,'cancel');self.assertTrue(all(j['status']=='cancelled' for j in self.db.list()))
 def test_failover_mocked(self):
  r=Router(self.db)
  async def call(p,m):
   if p=='gemini':raise ProviderError('offline')
   return 'answer'
  with patch.object(r,'call',side_effect=call):
   result=asyncio.run(r.call_any([{'role':'user','content':'hi'}],['gemini','groq']));self.assertEqual(result['provider'],'groq');self.assertEqual(len(result['failover']),1)
 def test_context_preserves_system_and_latest(self):
  m=compact_context([{'role':'system','content':'RULE'},{'role':'user','content':'a'*50},{'role':'assistant','content':'b'*50},{'role':'user','content':'NEW'}],60)
  self.assertEqual(m[0]['content'],'RULE');self.assertEqual(m[-1]['content'],'NEW');self.assertLessEqual(sum(len(x['content']) for x in m),60)
 def test_local_provider_fail_closed(self):
  with patch.dict(os.environ,{'TITAN_LOCAL_ENABLED':'1','TITAN_LOCAL_URL':'http://evil.example:11434/v1','TITAN_MODEL_LOCAL':'test'},clear=True):
   with self.assertRaises(ConfigurationError):asyncio.run(Router(self.db).call('local',[{'role':'user','content':'x'}]))
 def test_plan_forbidden_actions(self):
  for kind in ('shell','tool','publish','trade'):
   with self.assertRaises(ValueError):validate_plan({'steps':[{'id':'x','kind':kind}]})
  with self.assertRaises(ValueError):validate_plan({'steps':[{'id':'x','kind':'document','command':'rm -rf /'}]})
 def test_agent_actual_artifact_mocked_planner(self):
  class Fake:
   async def call_any(self,*a):return {'provider':'TEST_DOUBLE','content':json.dumps({'steps':[{'id':'report','kind':'document','title':'Demo','text':'Created by fixture'}]})}
  mid=self.db.submit('Create report','agent');Worker(self.db,Fake()).once();r=self.db.get(mid);self.assertEqual(r['status'],'completed');self.assertEqual(len(self.ws.artifacts()),1)
 def test_chat_mocked_provider(self):
  class Fake:
   async def call_any(self,*a):return {'provider':'TEST_DOUBLE','content':'test response','failover':[]}
  mid=self.db.submit('hello','chat');Worker(self.db,Fake()).once();self.assertEqual([m['role'] for m in self.ws.history('default')],['user','assistant'])
 def test_paper_backtest_flat_and_fees(self):
  r=backtest({'prices':[100]*10,'window':3});self.assertEqual(r['final_equity'],100000);self.assertEqual(r['trades'],0)
  nofee=backtest({'prices':list(range(100,110)),'window':3,'fee_bps':0});fee=backtest({'prices':list(range(100,110)),'window':3,'fee_bps':10});self.assertGreater(nofee['final_equity'],fee['final_equity'])
 def test_backtest_future_does_not_change_past(self):
  a=backtest({'prices':[100,101,102,103,104,105],'window':3});b=backtest({'prices':[100,101,102,103,1,1],'window':3});self.assertEqual(a['curve'][0],b['curve'][0])
 def test_document_worker(self):
  mid=self.db.submit('Document','document',{'text':'Actual output'});Worker(self.db).once();r=self.db.get(mid);self.assertEqual(r['status'],'completed');self.assertIn(b'Actual output',self.ws.read_artifact(r['result']['artifact_id'])[1])
 def test_video_real_ffmpeg(self):
  import shutil
  if not shutil.which('ffmpeg'):self.skipTest('FFmpeg unavailable')
  mid=self.db.submit('Video','video',{'title':'TITAN test','seconds':1});Worker(self.db).once();r=self.db.get(mid);self.assertEqual(r['status'],'completed',r['error']);self.assertGreaterEqual(r['result']['duration'],1);self.assertEqual(r['result']['width'],360)
 def test_coding_approval_required_mocked_model(self):
  class Fake:
   async def call_any(self,*a):return {'provider':'TEST_DOUBLE','content':json.dumps({'source':'def add(a,b): return a+b','tests':'import unittest\nfrom solution import add\nclass T(unittest.TestCase):\n def test_add(self):self.assertEqual(add(1,2),3)'})}
  mid=self.db.submit('Create add','code');Worker(self.db,Fake()).once();self.assertEqual(self.db.get(mid)['status'],'blocked')
  with self.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM approvals').fetchone()[0],1)

class ExtendedHTTP(platform_tests.HTTPTests):
 def test_project_artifact_api(self):
  project=json.load(self.req('/api/projects',{'name':'Project'}))['id']
  self.req('/api/knowledge',{'project':project,'key':'research','value':'verified fixture'}).close();self.assertEqual(len(json.load(self.req('/api/knowledge?project='+project+'&q=fixture'))),1)
  mid=json.load(self.req('/api/missions',{'objective':'doc','kind':'document','project':project,'payload':{'text':'Hello'}}))['id'];Worker(self.db).once();aid=self.db.get(mid)['result']['artifact_id'];r=self.req('/api/artifacts/'+aid);self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn(b'Hello',r.read())
 def test_health(self):self.assertEqual(json.load(self.req('/healthz',auth=False)),{'status':'ok'})
# Avoid reporting the inherited tests twice.
for name in platform_tests.HTTPTests.__dict__:
 if name.startswith('test_') and name not in ExtendedHTTP.__dict__:setattr(ExtendedHTTP,name,None)

class Hardening(Base):
 def test_github_public_repo_refused_mocked(self):
  from titan.github_tools import propose
  args={'repository':'owner/repo','branch':'titan/test','files':{'a.py':'x=1'}}
  with patch.dict(os.environ,{'TITAN_GITHUB_REPOSITORY':'owner/repo','GITHUB_TOKEN':'TEST_ONLY'}),patch('titan.github_tools.request_json',return_value={'private':False}):
   with self.assertRaises(PermissionError):propose(args)
 def test_github_draft_only_mocked(self):
  from titan.github_tools import propose
  responses=[{'private':True},{'object':{'sha':'base'}},{'tree':{'sha':'tree'}},{'sha':'newtree'},{'sha':'newcommit'},{},{'html_url':'https://github.com/owner/repo/pull/1','number':1}]
  with patch.dict(os.environ,{'TITAN_GITHUB_REPOSITORY':'owner/repo','GITHUB_TOKEN':'TEST_ONLY'}),patch('titan.github_tools.request_json',side_effect=responses) as request:
   r=propose({'repository':'owner/repo','branch':'titan/test','files':{'src/a.py':'x=1'}});self.assertTrue(r['draft']);self.assertTrue(request.call_args.args[2]['draft'])
 def test_github_critical_path_refused(self):
  from titan.github_tools import propose
  with patch.dict(os.environ,{'TITAN_GITHUB_REPOSITORY':'owner/repo'}):
   for path in ['../a','.github/workflows/ci.yml','.git/config','/root/x']:
    with self.assertRaises(ValueError):propose({'repository':'owner/repo','branch':'titan/test','files':{path:'x'}})
 def test_secret_file_source(self):
  from titan.security import load_secret_files
  p=Path(self.temp.name)/'token';p.write_text('test-fixture-value')
  with patch.dict(os.environ,{'TITAN_TOKEN_FILE':str(p)},clear=True):load_secret_files();self.assertEqual(os.environ['TITAN_TOKEN'],'test-fixture-value')
 def test_secret_symlink_rejected(self):
  from titan.security import load_secret_files
  p=Path(self.temp.name)/'link';p.symlink_to(self.path)
  with patch.dict(os.environ,{'TITAN_TOKEN_FILE':str(p)},clear=True):
   with self.assertRaises(OSError):load_secret_files()
 def test_artifact_retry_deduplicates(self):
  ws=Workspace(self.db);a=ws.artifact('default','j','a.txt',b'x');b=ws.artifact('default','j','a.txt',b'x');self.assertEqual(a,b);self.assertEqual(len(ws.artifacts()),1)
 def test_project_short_memory_expiry(self):
  ws=Workspace(self.db);ws.remember('default','short','x','short')
  with self.db.connect() as c:c.execute('UPDATE knowledge SET updated=0')
  self.assertEqual(ws.search('default'),[])
 def test_worker_health_stale(self):
  from titan.health import healthy
  Worker(self.db).once();self.assertTrue(healthy(str(self.path)))
  with self.db.connect() as c:c.execute("UPDATE settings SET value='0' WHERE key='worker_heartbeat'")
  self.assertFalse(healthy(str(self.path)))

class BenchmarkAndSecurity(Base):
 def test_exact_benchmark_mocked_models(self):
  class Fake:
   async def call(self,p,m):return '42' if p=='gemini' else 'wrong'
  mid=self.db.submit('benchmark','model_benchmark',{'providers':['gemini','groq']});Worker(self.db,Fake()).once();r=self.db.get(mid)['result'];self.assertEqual(r['scores']['gemini'],1/3);self.assertEqual(r['scores']['groq'],0)
 def test_circuit_breaker(self):
  with self.db.connect() as c:
   for _ in range(3):c.execute('INSERT INTO calls(provider,model,ts,status,cost) VALUES(?,?,?,?,?)',('groq','test',time.time(),'failed',0))
  with self.assertRaises(ConfigurationError):asyncio.run(Router(self.db).call_any([{'role':'user','content':'x'}],['groq']))
 def test_typed_debate_response(self):
  from titan.engine import structured
  self.assertFalse(structured('{"plan":"not a list"}',['plan'])['schema_valid'])
 def test_chat_commit_fenced(self):
  mid=self.db.submit('hello','chat');j,l=self.db.claim();self.db.control(mid,'cancel')
  from titan.store import LostLease
  with self.assertRaises(LostLease):self.db.finish(mid,l,{'content':'stale','provider':'test'})
  self.assertEqual(Workspace(self.db).history('default'),[])

class RateLimitHTTP(platform_tests.HTTPTests):
 def test_auth_rate_limit(self):
  from urllib.error import HTTPError
  for _ in range(20):
   with self.assertRaises(HTTPError) as error:self.req('/api/state',auth=False)
   self.assertEqual(error.exception.code,401)
  with self.assertRaises(HTTPError) as error:self.req('/api/state',auth=False)
  self.assertEqual(error.exception.code,429)
for name in platform_tests.HTTPTests.__dict__:
 if name.startswith('test_') and name not in RateLimitHTTP.__dict__:setattr(RateLimitHTTP,name,None)

class QualityRouting(Base):
 def test_quality_uses_current_model_and_suite(self):
  from titan.evaluation import SUITE_HASH
  Workspace(self.db)
  with self.db.connect() as c:
   c.execute('INSERT INTO calls(provider,model,ts,status,cost) VALUES(?,?,?,?,?)',('groq','test',time.time(),'ok',0))
   c.execute('INSERT INTO provider_quality VALUES(?,?,?,?,?,?)',('groq','test',SUITE_HASH,'fixture',.75,time.time()))
  with patch.dict(os.environ,{'TITAN_MODEL_GROQ':'test'}):self.assertEqual(Router(self.db).metrics()[0]['quality'],.75)
  with patch.dict(os.environ,{'TITAN_MODEL_GROQ':'different'}):self.assertIsNone(Router(self.db).metrics()[0]['quality'])
 def test_large_peer_record_is_explicitly_truncated(self):
  from titan.engine import compact_record
  r=json.loads(compact_record({'peer':'x'*50000}));self.assertTrue(r['truncated']);self.assertLess(len(r['excerpt']),18000)

class Watchdog(Base):
 def test_slow_model_cannot_commit_after_deadline(self):
  class Slow:
   async def call_any(self,*a):await asyncio.sleep(.15);return {'provider':'TEST_DOUBLE','content':'late'}
  mid=self.db.submit('slow','chat');Worker(self.db,Slow(),mission_seconds=.03,heartbeat_seconds=.01).once()
  self.assertEqual(self.db.get(mid)['status'],'blocked');self.assertIn('deadline',self.db.get(mid)['error']);self.assertEqual(Workspace(self.db).history('default'),[])
