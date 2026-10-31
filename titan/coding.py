"""Single-file Python coding/repair loop. Execution only through approved Docker tool."""
import ast,io,json,zipfile
from .workspace import Workspace
from .tools import ToolRegistry

async def run_coding(db,job,lease,router):
 state=job['checkpoint'];workspace=Workspace(db);project=job.get('project') or 'default'
 for attempt in range(state.get('repair',0),3):
  if 'candidate' not in state:
   response=await router.call_any([{'role':'system','content':'Return JSON with source (one Python module) and tests (unittest tests importing module solution). No network, subprocess, secrets, installs or file mutation outside temporary scratch. Do not claim tests passed. Maximum 24000 characters total.'},{'role':'user','content':json.dumps({'goal':job['objective'],'last_failure':state.get('failure')})}],job['payload'].get('providers'))
   candidate=json.loads(response['content'])
   if not isinstance(candidate,dict) or set(candidate)!={'source','tests'} or any(not isinstance(v,str) for v in candidate.values()) or sum(map(len,candidate.values()))>24000:raise ValueError('Invalid code candidate')
   ast.parse(candidate['source']);ast.parse(candidate['tests'])
   state['candidate']=candidate;state['repair']=attempt;state['provider']=response['provider'];db.checkpoint(job['id'],lease,state)
  candidate=state['candidate']
  # Untrusted source executes only in the pinned restricted container, never on the host.
  harness="import sys,types,unittest\nsolution=types.ModuleType('solution')\nsys.modules['solution']=solution\nexec("+repr(candidate['source'])+",solution.__dict__)\ntests=types.ModuleType('tests')\nexec("+repr(candidate['tests'])+",tests.__dict__)\nsuite=unittest.defaultTestLoader.loadTestsFromModule(tests)\nif suite.countTestCases()==0:raise SystemExit('No tests supplied')\nr=unittest.TextTestRunner(verbosity=2).run(suite)\nraise SystemExit(not r.wasSuccessful())\n"
  if len(harness)>30000:raise ValueError('Harness exceeds sandbox input limit')
  result=ToolRegistry(db).execute(job['id'],'sandbox.python',{'code':harness})
  state['test_result']=result
  if result.get('exit_code')==0:
   buffer=io.BytesIO()
   with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('solution.py',candidate['source']);z.writestr('test_solution.py',candidate['tests']);z.writestr('verification.json',json.dumps({'provider':state['provider'],'test_result':result,'warning':'Model-generated tests are not an independent correctness proof'}))
   artifact=workspace.artifact(project,job['id'],'python-project.zip',buffer.getvalue(),'application/zip')
   return {**artifact,'verification':'Generated tests passed in approved sandbox; independent acceptance review still needed','attempt':attempt+1}
  state['failure']=result;state.pop('candidate');state['repair']=attempt+1;db.checkpoint(job['id'],lease,state)
 raise ValueError('Code repair exhausted three candidates; inspect checkpoint')
