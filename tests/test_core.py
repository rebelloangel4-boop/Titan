import asyncio,json,unittest
from titan.core import Store,debate
class TestTitan(unittest.TestCase):
 def test_store(self):
  s=Store(':memory:');mid=s.create('hello');self.assertEqual(s.get(mid)['status'],'queued');s.update(mid,'completed','done');self.assertEqual(s.get(mid)['result'],'done')
 def test_debate(self):
  async def fake(p,msg):return f'{p} independently reviewed: '+msg[0]['content'][:35]
  s=Store(':memory:');mid=asyncio.run(debate('Build an app',['gemini','groq'],s,fake));r=json.loads(s.get(mid)['result']);self.assertEqual(len(r['proposals']),2);self.assertEqual(len(r['critiques']),2)
 def test_requires_independence(self):
  async def fake(p,msg):return 'ok'
  with self.assertRaises(ValueError):asyncio.run(debate('x',['gemini','gemini'],Store(':memory:'),fake))
 def test_failed_provider(self):
  async def fake(p,msg):raise RuntimeError('offline')
  s=Store(':memory:')
  with self.assertRaises(RuntimeError):asyncio.run(debate('x',['gemini','groq'],s,fake))
if __name__=='__main__':unittest.main()
