"""Bounded multi-file Python packages. Build harness text; never execute on the host."""
import ast,json,re
from pathlib import PurePosixPath

MAX_CHARS=20000

def validate_files(files):
 if not isinstance(files,dict) or not 1<=len(files)<=16:raise ValueError('Project requires 1–16 Python files')
 total=0
 for name,source in files.items():
  if not isinstance(name,str) or len(name)>120 or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_/]*\.py',name):raise ValueError('Invalid project path')
  if str(PurePosixPath(name))!=name or name=='test__titan_acceptance.py':raise ValueError('Noncanonical/reserved path')
  parts=PurePosixPath(name).parts
  if any(p.startswith('_titan') for p in parts) or len(parts)>5:raise ValueError('Reserved/deep project path')
  if not isinstance(source,str):raise ValueError('File contents must be text')
  total+=len(source)
  if total>MAX_CHARS:raise ValueError('Project content limit exceeded')
  ast.parse(source,filename=name)
 if not any(PurePosixPath(name).name.startswith('test_') for name in files):raise ValueError('Project requires test_*.py tests')
 # Packages must be explicit so unittest discovery and imports behave consistently.
 for name in files:
  parent=PurePosixPath(name).parent
  while str(parent)!='.':
   if str(parent/'__init__.py') not in files:raise ValueError('Package requires __init__.py')
   parent=parent.parent
 return files

def normalize(candidate):
 if not isinstance(candidate,dict):raise ValueError('Invalid code candidate')
 if set(candidate)=={'source','tests'}:
  return validate_files({'solution.py':candidate['source'],'test_solution.py':candidate['tests']})
 if set(candidate)=={'files'}:return validate_files(candidate['files'])
 raise ValueError('Expected files map or source/tests')

def harness(files,acceptance_tests=None):
 files=dict(validate_files(files))
 if acceptance_tests is not None:
  if not isinstance(acceptance_tests,str) or not 1<=len(acceptance_tests)<=6000:raise ValueError('Invalid acceptance tests')
  ast.parse(acceptance_tests);files['test__titan_acceptance.py']=acceptance_tests
 # Data is safely repr-encoded; only an approved sandbox may run this harness.
 source='''import os,sys,tempfile,unittest,json
from pathlib import Path
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory)
 files=FILES
 for name,content in files.items():
  path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
 sys.path.insert(0,directory);os.chdir(directory)
 suite=unittest.defaultTestLoader.discover(directory,pattern='test_*.py')
 count=suite.countTestCases()
 if count==0:raise SystemExit('No tests discovered')
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 summary={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}
 print('TITAN_TEST_SUMMARY='+json.dumps(summary),flush=True)
 raise SystemExit(not result.wasSuccessful() or result.testsRun==len(result.skipped))
'''.replace('FILES',repr(files))
 if len(source)>30000:raise ValueError('Harness exceeds sandbox input limit')
 return source

def summary(result):
 if result.get('exit_code')!=0:return None
 lines=[x for x in result.get('output','').splitlines() if x.startswith('TITAN_TEST_SUMMARY=')]
 if len(lines)!=1:return None
 try:
  data=json.loads(lines[0].split('=',1)[1])
  if set(data)!={'tests_run','failures','errors','skipped'} or any(type(v) is not int or v<0 for v in data.values()):return None
  if data['tests_run']<=data['skipped'] or data['failures'] or data['errors']:return None
  return data
 except (ValueError,TypeError):return None
