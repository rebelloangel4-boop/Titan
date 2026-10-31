"""Repository-scoped draft PR changes; no merge, delete, force-push or public repo writes."""
import os,re
from pathlib import PurePosixPath
from urllib.parse import quote
from .providers import request_json,ConfigurationError

def propose(a):
 repo=a.get('repository');base=a.get('base','main');branch=a.get('branch');files=a.get('files');title=a.get('title','TITAN proposed change')
 if repo!=os.getenv('TITAN_GITHUB_REPOSITORY') or not isinstance(repo,str) or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise PermissionError('Repository outside configured scope')
 if not isinstance(branch,str) or not re.fullmatch(r'titan/[a-z0-9][a-z0-9-]{0,50}',branch):raise ValueError('Use a new titan/<lowercase-name> branch')
 if not isinstance(base,str) or not re.fullmatch('[A-Za-z0-9_/-]{1,100}',base) or base==branch:raise ValueError('Invalid base branch')
 if not isinstance(title,str) or not 1<=len(title)<=200 or not isinstance(files,dict) or not 1<=len(files)<=20:raise ValueError('Invalid title/files')
 total=0
 for path,content in files.items():
  if not isinstance(path,str) or not re.fullmatch('[A-Za-z0-9_./-]{1,200}',path) or path.startswith('/') or any(p in ('..','.git','.github') or p.startswith('.') for p in path.split('/')):raise ValueError('Unsafe or security-critical path')
  if not isinstance(content,str):raise ValueError('Only UTF-8 text files supported')
  total+=len(content.encode())
 if total>200000:raise ValueError('Patch exceeds 200 KB')
 key=os.getenv('GITHUB_TOKEN')
 if not key:raise ConfigurationError('Missing GITHUB_TOKEN')
 url='https://api.github.com/repos/'+repo;headers={'Authorization':'Bearer '+key,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'}
 metadata=request_json(url,headers)
 if metadata.get('private') is not True:raise PermissionError('Draft writes require a private repository')
 ref=request_json(url+'/git/ref/heads/'+quote(base,safe=''),headers);head=ref['object']['sha']
 commit=request_json(url+'/git/commits/'+head,headers)
 tree=request_json(url+'/git/trees',headers,{'base_tree':commit['tree']['sha'],'tree':[{'path':p,'mode':'100644','type':'blob','content':v} for p,v in files.items()]})
 new=request_json(url+'/git/commits',headers,{'message':title,'tree':tree['sha'],'parents':[head]})
 # Creating, never updating, means an existing branch is a safe error.
 request_json(url+'/git/refs',headers,{'ref':'refs/heads/'+branch,'sha':new['sha']})
 pr=request_json(url+'/pulls',headers,{'title':title,'head':branch,'base':base,'body':'TITAN proposed change. Review diff and CI before merging. No automatic merge is enabled.','draft':True})
 return {'pull_request':pr['html_url'],'number':pr['number'],'commit':new['sha'],'draft':True,'verification':'GitHub API accepted draft; CI success not implied'}
