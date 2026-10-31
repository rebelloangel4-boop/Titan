import asyncio,time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from test_platform import Base
from titan.workspace import Workspace
from titan.agents import chat,run_agent

class RetrievalTests(Base):
 def setUp(self):
  super().setUp();self.ws=Workspace(self.db)
 def test_goal_finds_partial_terms(self):
  self.ws.remember('default','render settings','Use vertical video and subtitle safe area')
  self.ws.remember('default','unrelated','Bananas and apples')
  result=self.ws.retrieve('default','Create a vertical video with subtitles for our project')
  self.assertEqual([r['key'] for r in result],['render settings'])
  self.assertEqual(result[0]['retrieval'],'lexical_bm25')
 def test_isolation_and_expiry(self):
  other=self.ws.create_project('private');self.ws.remember(other,'private','video secret')
  self.ws.remember('default','expired','video old','short')
  with self.db.connect() as c:c.execute('UPDATE knowledge SET updated=0 WHERE key=?',('expired',))
  self.assertEqual(self.ws.retrieve('default','video'),[])
 def test_budget_and_truncation(self):
  self.ws.remember('default','video','video '*300)
  r=self.ws.retrieve('default','video',max_chars=200)
  self.assertEqual(sum(len(x['key'])+len(x['value']) for x in r),200)
  self.assertTrue(r[0]['truncated'])
 def test_empty_and_unmatched(self):
  self.ws.remember('default','hello','world')
  for q in ('','the and our','%%','unmatched'):
   self.assertEqual(self.ws.retrieve('default',q),[])
 def test_validation_and_literal_search_preserved(self):
  self.ws.remember('default','video','vertical render')
  self.assertEqual(self.ws.search('default','video render'),[])
  for kwargs in ({'limit':True},{'max_chars':0},{'limit':100}):
   with self.assertRaises(ValueError):self.ws.retrieve('default','video',**kwargs)
 def test_chat_receives_memory_as_data(self):
  self.ws.remember('default','video settings','vertical output')
  router=SimpleNamespace(call_any=AsyncMock(return_value={'content':'fixture','provider':'fixture'}))
  asyncio.run(chat(self.db,{'objective':'make a video','payload':{},'project':'default'},router))
  messages=router.call_any.call_args.args[0]
  self.assertIn('reference_memory',messages[-1]['content']);self.assertIn('vertical output',messages[-1]['content'])
  self.assertNotIn('vertical output',messages[0]['content'])
 def test_planner_receives_memory(self):
  self.ws.remember('default','video settings','vertical output')
  mid=self.db.submit('make a video','agent',{});job,lease=self.db.claim()
  router=SimpleNamespace(call_any=AsyncMock(return_value={'content':'{"steps":[{"id":"one","kind":"analysis","values":[1,2]}]}','provider':'fixture'}))
  result=asyncio.run(run_agent(self.db,job,lease,router))
  self.assertIn('vertical output',router.call_any.call_args.args[0][-1]['content'])
  self.assertIn('one',result['results'])
