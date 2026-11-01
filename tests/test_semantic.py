import os,time
from unittest.mock import patch
from test_platform import Base
from titan.workspace import Workspace
from titan.semantic import validate_vector,SemanticUnavailable

class SemanticTests(Base):
 def setUp(self):
  super().setUp();self.ws=Workspace(self.db);self.mode=patch.dict(os.environ,{'TITAN_MEMORY_MODE':'semantic'});self.mode.start()
 def tearDown(self):self.mode.stop();super().tearDown()
 def test_scope_expiry_cache_and_update(self):
  self.ws.remember('default','A','car repair');other=self.ws.create_project('other');self.ws.remember(other,'private','car repair')
  self.ws.remember('default','expired','car repair','short')
  with self.db.connect() as c:c.execute("UPDATE knowledge SET updated=0 WHERE key='expired'")
  with patch('titan.semantic.embed',side_effect=lambda texts:[[1.,0.] for _ in texts]) as encode:
   self.assertEqual([r['key'] for r in self.ws.retrieve('default','fix automobile')],['A'])
   self.assertEqual(encode.call_count,2)
   self.ws.retrieve('default','fix automobile');self.assertEqual(encode.call_count,3)
   self.ws.remember('default','A','changed');self.ws.retrieve('default','fix automobile');self.assertEqual(encode.call_count,5)
 def test_budget_and_long_entry(self):
  self.ws.remember('default','A','car '*2000)
  with patch('titan.semantic.embed',side_effect=lambda texts:[[1.,0.] for _ in texts]):r=self.ws.retrieve('default','automobile',max_chars=200)[0]
  self.assertTrue(r['truncated']);self.assertTrue(r['embedding_truncated']);self.assertEqual(len(r['key'])+len(r['value']),200)
 def test_malformed_vector(self):
  for vector in ([float('nan')],[0,0],[],[True],['secret']):
   with self.assertRaises(ValueError):validate_vector(vector)
 def test_unavailable_fails_explicitly(self):
  self.ws.remember('default','A','car')
  with patch('titan.semantic.embed',side_effect=SemanticUnavailable('unavailable')):
   with self.assertRaises(SemanticUnavailable):self.ws.retrieve('default','automobile')
 def test_bad_cache_rebuilt(self):
  self.ws.remember('default','A','car')
  with patch('titan.semantic.embed',side_effect=lambda texts:[[1.,0.] for _ in texts]) as encode:
   self.ws.retrieve('default','automobile')
   with self.db.connect() as c:c.execute("UPDATE embeddings SET vectors='[[0,0]]'")
   self.ws.retrieve('default','automobile');self.assertEqual(encode.call_count,4)
 def test_unknown_mode_rejected(self):
  with patch.dict(os.environ,{'TITAN_MEMORY_MODE':'typo'}):
   with self.assertRaises(ValueError):self.ws.retrieve('default','query')
