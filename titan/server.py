"""Single-operator private API. Deploy behind TLS reverse proxy; bind loopback by default."""
import argparse,json,mimetypes,os,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .store import Database
from .providers import Router
from .engine import Worker
from .security import authenticate,redact
from .improvement import Improvements
from .tools import ToolRegistry

WEB=Path(__file__).parent/'web'
class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,db,token):
        if len(token)<32:raise ValueError('TITAN_TOKEN must have at least 32 characters')
        from .workspace import Workspace
        self.workspace=Workspace(db)
        self.slots=threading.BoundedSemaphore(32);self.auth_failures={};self.auth_lock=threading.Lock()
        self.db=db;self.token=token
        super().__init__(address,Handler)
    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            try:request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:self.shutdown_request(request)
            return
        try:super().process_request(request,client_address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.slots.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass # Never log headers, URL parameters, prompts, or keys.
    def setup(self):
        super().setup();self.connection.settimeout(10)
    def send(self,status,payload,ctype='application/json',filename=None):
        body=payload if isinstance(payload,bytes) else json.dumps(payload,allow_nan=False).encode()
        self.send_response(status)
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.handle_request(False)
    def do_POST(self):self.handle_request(True)
    def handle_request(self,post):
        path=urlsplit(self.path).path;db=self.server.db;workspace=self.server.workspace
        query=parse_qs(urlsplit(self.path).query)
        try:
            if path=='/healthz' and not post:return self.send(200,{'status':'ok'})
            if not path.startswith('/api/'):
                names={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/manifest.json':'manifest.json','/sw.js':'sw.js','/icon.svg':'icon.svg','/icon-192.png':'icon-192.png','/icon-512.png':'icon-512.png'}
                if post or path not in names:return self.send(404,{'error':'Not found'})
                file=WEB/names[path]
                return self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
            ip=self.client_address[0];auth_status=200
            with self.server.auth_lock:
                if len(self.server.auth_failures)>4096:
                    self.server.auth_failures={k:v for k,v in self.server.auth_failures.items() if v and time.monotonic()-v[-1]<60}
                    if len(self.server.auth_failures)>4096:self.server.auth_failures.pop(next(iter(self.server.auth_failures)))
                misses=[t for t in self.server.auth_failures.get(ip,[]) if time.monotonic()-t<60]
                if len(misses)>=20:auth_status=429
                elif not authenticate(self.headers.get('Authorization'),self.server.token):
                    self.server.auth_failures[ip]=misses+[time.monotonic()];auth_status=401
                else:self.server.auth_failures.pop(ip,None)
            if auth_status!=200:return self.send(auth_status,{'error':'Authentication attempts limited' if auth_status==429 else 'Authentication required'})
            # Browser cross-origin requests cannot mutate state even if a token leaks into an extension.
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):return self.send(403,{'error':'Cross-origin request rejected'})
            data={}
            if post:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,{'error':'JSON required'})
                length=int(self.headers.get('Content-Length','0'))
                if length<1 or length>1_000_000:return self.send(413,{'error':'Request size invalid'})
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Object required')
            if path=='/api/health' and not post:
                from .health import healthy
                return self.send(200,{'api':'ok','worker_recent':healthy(db.path)})
            if path=='/api/projects':
                if post:return self.send(201,{'id':workspace.create_project(data['name'])})
                return self.send(200,workspace.projects())
            if path=='/api/knowledge':
                if post:
                    workspace.remember(data.get('project','default'),data['key'],data['value'],data.get('scope','long'));return self.send(200,{'saved':True})
                return self.send(200,workspace.search(query.get('project',['default'])[0],query.get('q',[''])[0]))
            if path=='/api/chat' and not post:return self.send(200,workspace.history(query.get('project',['default'])[0]))
            if path=='/api/schedules':
                if post:
                    if 'id' in data:workspace.toggle_schedule(data['id'],data['enabled']);return self.send(200,{'updated':True})
                    return self.send(201,{'id':workspace.schedule(data.get('project','default'),data['objective'],data['kind'],data.get('payload',{}),data['interval_seconds'])})
                return self.send(200,workspace.schedules())
            if path.startswith('/api/artifacts/') and not post:
                meta,raw=workspace.read_artifact(path.split('/')[-1])
                return self.send(200,raw,'application/octet-stream',meta['name'])
            if path=='/api/state' and not post:
                with db.connect() as c:
                    approvals=[dict(r) for r in c.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY created DESC LIMIT 100")]
                    used=dict(c.execute('SELECT COUNT(*) calls,COALESCE(SUM(cost),0) reserved_usd FROM calls WHERE ts>=?',(int(time.time()//86400)*86400,)).fetchone())
                return self.send(200,{'missions':db.list(),'models':Router(db).catalog(),'metrics':Router(db).metrics(),'memory':db.memories(),'events':db.events(),'approvals':approvals,'improvements':Improvements(db).list(),'failure_analysis':Improvements(db).propose(),'budget':{'daily_usd':float(os.getenv('TITAN_DAILY_USD','0')),'daily_calls':int(os.getenv('TITAN_DAILY_CALLS','50')),**used},'tools':sorted(ToolRegistry.names),'projects':workspace.projects(),'artifacts':workspace.artifacts(),'schedules':workspace.schedules(),'runtime':'single-operator; live providers require credentials'})
            if path=='/api/missions' and post:
                kind=data.get('kind','debate');payload=data.get('payload',{})
                if not isinstance(payload,dict):raise ValueError('Payload must be an object')
                from .core import PROVIDERS
                if kind=='debate' and 'providers' in payload:
                    ps=payload['providers']
                    if not isinstance(ps,list) or not 2<=len(ps)<=7 or any(p not in {*PROVIDERS,'local'} for p in ps) or len(set(ps))!=len(ps):raise ValueError('Select 2–7 distinct known providers')
                if kind=='tool' and payload.get('tool') not in ToolRegistry.names:raise ValueError('Unsupported tool')
                due=data.get('due')
                if due is not None and (not isinstance(due,(int,float)) or not time.time()-1<=due<=time.time()+31536000):raise ValueError('Schedule must be within one year')
                mid=db.submit(redact(data['objective']),kind,json.loads(redact(json.dumps(payload))),due,project=data.get('project','default'))
                return self.send(201,{'id':mid})
            if path.startswith('/api/missions/') and post:
                mid=path.split('/')[-1];db.control(mid,data['action']);return self.send(200,db.get(mid))
            if path=='/api/memory' and post:
                db.remember(data['key'],data['value'],data.get('scope','long'));return self.send(200,{'saved':True})
            if path=='/api/approve' and post:
                ToolRegistry(db).approve(data['id']);return self.send(200,{'approved':True,'next':'Resume the blocked mission'})
            if path=='/api/policy' and post:
                from . import policy
                action=data.get('action')
                if action=='evaluate':return self.send(200,policy.propose(db,data['weights']))
                if action=='promote':policy.promote(db,data['id'])
                elif action=='rollback':policy.rollback(db,data['id'])
                else:raise ValueError('Unknown action')
                return self.send(200,{'action':action,'active':policy.active(db)})
            if path=='/api/benchmark' and post:return self.send(200,Improvements(db).evaluate({'description':data.get('description','Current deterministic baseline')}))
            return self.send(404,{'error':'Not found'})
        except KeyError:return self.send(400,{'error':'Missing field or mission'})
        except (ValueError,TypeError):return self.send(400,{'error':'Invalid request fields'})
        except PermissionError:return self.send(403,{'error':'Permission denied'})
        except Exception:return self.send(500,{'error':'Internal error; inspect operator diagnostics'})

def main():
    from .security import load_secret_files
    load_secret_files()
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8787);parser.add_argument('--db',default=os.getenv('TITAN_DB','titan.db'));parser.add_argument('--no-worker',action='store_true');args=parser.parse_args()
    db=Database(args.db);server=Server((args.host,args.port),db,os.getenv('TITAN_TOKEN',''))
    worker=Worker(db)
    if not args.no_worker:threading.Thread(target=worker.run,daemon=True).start()
    print('TITAN listening; authentication required for API',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:worker.stop.set();server.server_close()
if __name__=='__main__':main()
