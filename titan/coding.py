"""Bounded multi-file Python coding/repair loop. Execution only through approved Docker tool."""
import ast,io,json,zipfile
from .workspace import Workspace
from .tools import ToolRegistry
from .python_project import normalize,harness as build_harness,summary

async def run_coding(db,job,lease,router):
 state=job['checkpoint'];workspace=Workspace(db);project=job.get('project') or 'default'
 for attempt in range(state.get('repair',0),3):
  if 'candidate' not in state:
   response=await router.call_any([{'role':'system','content':'Return JSON with files mapping relative Python paths to source strings. Include test_*.py unittest files and __init__.py for packages. Maximum 16 files. No network, subprocess, secrets, installs or file mutation outside temporary scratch. Do not claim tests passed. Maximum 20000 characters total.'},{'role':'user','content':json.dumps({'goal':job['objective'],'last_failure':state.get('failure')})}],job['payload'].get('providers'))
   candidate=json.loads(response['content'])
   normalize(candidate)
   state['candidate']=candidate;state['repair']=attempt;state['provider']=response['provider'];db.checkpoint(job['id'],lease,state)
  candidate=state['candidate']
  files=normalize(candidate)
  harness=build_harness(files,job['payload'].get('acceptance_tests'))
  result=ToolRegistry(db).execute(job['id'],'sandbox.python',{'code':harness})
  state['test_result']=result
  test_summary=summary(result)
  if test_summary is not None:
   buffer=io.BytesIO()
   with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
    for name,source in files.items():z.writestr(name,source)
    if job['payload'].get('acceptance_tests'):z.writestr('test__titan_acceptance.py',job['payload']['acceptance_tests'])
    z.writestr('verification.json',json.dumps({'provider':state['provider'],'test_result':result,'test_summary':test_summary,'warning':'Untrusted code and tests share a container; reported tests are not an independent correctness proof'}))
   artifact=workspace.artifact(project,job['id'],'python-project.zip',buffer.getvalue(),'application/zip')
   return {**artifact,'verification':'Sandbox reported passing tests; independent acceptance review still needed','files':len(files),'tests':test_summary,'attempt':attempt+1}
  if result.get('exit_code')==0:result={**result,'verification_error':'Missing or invalid test summary; no success accepted'}
  state['failure']=result;state.pop('candidate');state['repair']=attempt+1;db.checkpoint(job['id'],lease,state)
 raise ValueError('Code repair exhausted three candidates; inspect checkpoint')
