"""Real Docker acceptance tests; intentionally run explicitly by container CI."""
import os,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from titan.store import Database
from titan.tools import ToolRegistry

class SandboxAcceptance(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.db=Database(Path(self.temp.name)/'db');self.tools=ToolRegistry(self.db)
 def tearDown(self):self.temp.cleanup()
 def run_code(self,code):
  return self.tools.sandbox({'code':code})
 def test_actual_execution_and_isolation(self):
  code='''import os,socket,json
checks={"nonroot":os.getuid()==65534,"secret_absent":os.getenv("TITAN_TEST_SECRET") is None,"proxy_empty":not os.getenv("HTTPS_PROXY")}
try:
 open('/forbidden-write','w').write('x');checks['root_readonly']=False
except OSError:checks['root_readonly']=True
try:
 open('/work/main.py','w').write('x');checks['source_readonly']=False
except OSError:checks['source_readonly']=True
s=socket.socket();s.settimeout(1)
try:s.connect(('1.1.1.1',443));checks['network_disabled']=False
except OSError:checks['network_disabled']=True
print(json.dumps(checks))
assert all(checks.values()),checks
'''
  with patch.dict(os.environ,{'TITAN_TEST_SECRET':'synthetic-secret-not-for-container'}):r=self.run_code(code)
  self.assertEqual(r['exit_code'],0,r);self.assertIn('"network_disabled": true',r['output'])
 def test_nonzero_exit(self):
  self.assertEqual(self.run_code('raise SystemExit(7)')['exit_code'],7)
 def test_output_bound(self):
  before=subprocess.check_output(['docker','ps','-aq','--filter','name=titan-']).split()
  with self.assertRaises(TimeoutError):self.run_code('while True: print("x"*4096,flush=True)')
  after=subprocess.check_output(['docker','ps','-aq','--filter','name=titan-']).split()
  self.assertEqual(after,before,'Sandbox container leaked after output limit')
 def test_exact_approval_before_real_execution(self):
  mid=self.db.submit('sandbox acceptance');args={'code':'print(6*7)'}
  with self.assertRaises(PermissionError):self.tools.execute(mid,'sandbox.python',args)
  approval=self.tools.request(mid,'sandbox.python',args);self.tools.approve(approval['id'])
  result=self.tools.execute(mid,'sandbox.python',args);self.assertEqual(result['output'].strip(),'42')
  with self.assertRaises(PermissionError):self.tools.execute(mid,'sandbox.python',args)

if __name__=='__main__':
 if os.getenv('TITAN_ENABLE_SANDBOX')!='1' or not os.getenv('TITAN_SANDBOX_IMAGE'):raise SystemExit('Explicit sandbox enable and digest image required')
 unittest.main(verbosity=2)
