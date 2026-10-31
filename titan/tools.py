"""Explicit tools only. Model text cannot grant permissions or approve actions."""
import json,os,re,shutil,subprocess,tempfile,time,uuid
from pathlib import Path
from urllib.parse import quote
from .security import digest,public_https,redact
from .providers import request_json,ConfigurationError

class ToolRegistry:
    # External communication, reads that transmit data, and sandbox execution all require exact approval.
    names={'github.read','github.propose','web.read','drive.list','telegram.send','sandbox.python','mcp.call'}
    def __init__(self,db):self.db=db
    def request(self,job,tool,args):
        if tool not in self.names:raise ValueError('Tool not supported')
        d=digest(tool,args)
        with self.db.connect() as c:
            row=c.execute("SELECT id,status FROM approvals WHERE job=? AND tool=? AND digest=? AND status IN ('pending','approved') ORDER BY created DESC LIMIT 1",(job,tool,d)).fetchone()
            if row:return dict(row)
            aid=uuid.uuid4().hex
            c.execute('INSERT INTO approvals(id,job,tool,digest,status,created,arguments) VALUES(?,?,?,?,?,?,?)',(aid,job,tool,d,'pending',time.time(),redact(json.dumps(args))))
        return {'id':aid,'status':'pending'}
    def approve(self,aid):
        with self.db.connect() as c:
            n=c.execute("UPDATE approvals SET status='approved' WHERE id=? AND status='pending'",(aid,)).rowcount
            if not n:raise ValueError('Approval not pending')
        self.db.event(None,'approval','Operator approved '+aid)
    def execute(self,job,tool,args):
        approval=self.request(job,tool,args)
        if approval['status']!='approved':raise PermissionError('Exact tool invocation requires operator approval: '+approval['id'])
        # Consume before execution: crash/retry cannot blindly repeat external effects.
        with self.db.connect() as c:
            n=c.execute("UPDATE approvals SET status='consumed' WHERE id=? AND status='approved'",(approval['id'],)).rowcount
            if n!=1:raise PermissionError('Approval already consumed')
        self.db.event(job,'tool_started',tool)
        result=self.dispatch(tool,args)
        self.db.event(job,'tool_completed',tool)
        return json.loads(redact(json.dumps(result)))
    def dispatch(self,tool,a):
        if tool=='github.propose':
            from .github_tools import propose
            return propose(a)
        if tool=='github.read':
            repo=a['repository']
            if repo!=os.getenv('TITAN_GITHUB_REPOSITORY'):raise PermissionError('Repository outside configured scope')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid repository')
            return request_json('https://api.github.com/repos/'+repo,{'Authorization':'Bearer '+self.secret('GITHUB_TOKEN'),'Accept':'application/vnd.github+json'})
        if tool=='drive.list':
            return request_json('https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(id,name,mimeType)',{'Authorization':'Bearer '+self.secret('GOOGLE_ACCESS_TOKEN')})
        if tool=='telegram.send':
            text=a.get('text','')
            if not isinstance(text,str) or not 1<=len(text)<=4000:raise ValueError('Message length invalid')
            return request_json('https://api.telegram.org/bot'+self.secret('TELEGRAM_BOT_TOKEN')+'/sendMessage',{'Content-Type':'application/json'},{'chat_id':self.secret('TITAN_TELEGRAM_CHAT_ID'),'text':redact(text)})
        if tool=='web.read':
            # JSON research endpoints only; allowlist and egress firewall both required in production.
            url=public_https(a['url'],os.getenv('TITAN_WEB_HOSTS','').split(','))
            return request_json(url,{'Accept':'application/json'})
        if tool=='mcp.call':return self.mcp(a)
        if tool=='sandbox.python':return self.sandbox(a)
        raise ValueError('Unsupported tool')
    @staticmethod
    def secret(name):
        v=os.getenv(name)
        if not v:raise ConfigurationError('Missing '+name)
        return v
    def mcp(self,a):
        from .mcp import Client
        endpoint=self.secret('TITAN_MCP_URL')
        public_https(endpoint,os.getenv('TITAN_MCP_HOSTS','').split(','))
        tool=a['name']
        if tool not in os.getenv('TITAN_MCP_TOOLS','').split(','):raise PermissionError('MCP tool not allowlisted')
        return Client(endpoint,os.getenv('TITAN_MCP_TOKEN')).call(tool,a.get('arguments',{}))
    def sandbox(self,a):
        if os.getenv('TITAN_ENABLE_SANDBOX')!='1':raise ConfigurationError('Sandbox is disabled')
        if not shutil.which('docker'):raise ConfigurationError('Docker runtime unavailable; no host execution fallback')
        image=self.secret('TITAN_SANDBOX_IMAGE')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:-]*@sha256:[a-f0-9]{64}',image):raise ConfigurationError('Pin sandbox image by digest')
        code=a.get('code','')
        if not isinstance(code,str) or len(code)>30000:raise ValueError('Code too large')
        name='titan-'+uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as d:
            Path(d,'main.py').write_text(code)
            cmd=['docker','run','--rm','--pull=never','--name',name,'--network=none','--env','HTTP_PROXY=','--env','HTTPS_PROXY=','--env','ALL_PROXY=','--env','NO_PROXY=','--env','http_proxy=','--env','https_proxy=','--env','all_proxy=','--env','no_proxy=','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=128m','--cpus=0.5','--user=65534:65534','--log-driver=none','--ulimit','fsize=1048576:1048576','--tmpfs','/tmp:size=16m,noexec,nosuid','-v',d+':/work:ro',image,'python','-I','/work/main.py']
            os.chmod(d,0o755)
            # Bound pipe reads as well as wall time to avoid host disk/memory exhaustion.
            import selectors
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
            output=bytearray();deadline=time.monotonic()+20
            try:
                while time.monotonic()<deadline and len(output)<65536:
                    if sel.select(.1):
                        chunk=os.read(proc.stdout.fileno(),min(4096,65536-len(output)))
                        if not chunk:break
                        output.extend(chunk)
                    elif proc.poll() is not None:break
                if proc.poll() is None:raise TimeoutError('Sandbox time/output limit reached')
                return {'exit_code':proc.returncode,'output':redact(output.decode(errors='replace')),'verification':'sandbox_execution'}
            finally:
                try:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                finally:
                    if proc.poll() is None:proc.kill()
                    proc.wait(timeout=5);sel.close();proc.stdout.close()
