"""Real HTTP adapters only. Test doubles are injected by tests, never by server config."""
import asyncio,json,os,time,math
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler
from urllib.parse import urlsplit
from urllib.error import HTTPError,URLError
from .core import PROVIDERS

class ConfigurationError(RuntimeError):pass
class ProviderError(RuntimeError):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def request_json(url, headers, payload=None, timeout=45):
    req=Request(url,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
    try:
        parsed=urlsplit(url)
        opener=build_opener(NoRedirect,ProxyHandler({})) if parsed.hostname in ('127.0.0.1','localhost','::1') else build_opener(NoRedirect)
        with opener.open(req,timeout=timeout) as r:
            data=r.read(2_000_001)
            if len(data)>2_000_000:raise ProviderError('Response exceeded limit')
            return json.loads(data)
    except HTTPError as e:raise ProviderError('Remote HTTP '+str(e.code)) from None
    except (URLError,TimeoutError,OSError):raise ProviderError('Remote connection failed') from None
    except (ValueError,KeyError,TypeError):raise ProviderError('Invalid remote response') from None

class Router:
    def __init__(self, db):self.db=db
    def catalog(self):
        free=set(os.getenv('TITAN_FREE_PROVIDERS','').split(','))
        catalog=[{'provider':p,'model':os.getenv('TITAN_MODEL_'+p.upper(),default),'configured':bool(os.getenv(env)), 'operator_confirmed_free':p in free} for p,(_,env,default) in PROVIDERS.items()]
        if os.getenv('TITAN_LOCAL_ENABLED')=='1':catalog.append({'provider':'local','model':os.getenv('TITAN_MODEL_LOCAL',''),'configured':bool(os.getenv('TITAN_MODEL_LOCAL')),'operator_confirmed_free':True})
        return catalog
    def rank(self):
        metrics={r['provider']:r for r in self.metrics()}
        from .policy import score as policy_score,active
        policy=active(self.db)
        def score(p):
            return policy_score(metrics.get(p['provider'],{}),policy)
        return [p['provider'] for p in sorted(self.catalog(),key=score,reverse=True) if p['configured'] and (p['operator_confirmed_free'] or float(os.getenv('TITAN_DAILY_USD','0'))>0)]
    def metrics(self):
        with self.db.connect() as c:
            rows=[dict(r) for r in c.execute("SELECT provider,COUNT(*) calls,AVG(status='ok') success_rate,AVG(latency) latency,AVG(cost) cost,AVG(quality) quality FROM calls GROUP BY provider")]
            exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_quality'").fetchone()
            if exists:
                from .evaluation import SUITE_HASH
                for row in rows:
                    provider=row['provider'];model=os.getenv('TITAN_MODEL_'+provider.upper(),PROVIDERS[provider][2] if provider in PROVIDERS else '')
                    quality=c.execute('SELECT score FROM provider_quality WHERE provider=? AND model=? AND suite=?',(provider,model,SUITE_HASH)).fetchone()
                    if quality:row['quality']=quality[0];row['quality_scope']='Frozen exact-answer suite only'
            return rows
    def reserve(self,p,model,messages):
        free=p=='local' or p in os.getenv('TITAN_FREE_PROVIDERS','').split(',')
        # Charge a conservative operator-configured ceiling per request. Failed calls retain reservation.
        cost=0 if free else float(os.getenv('TITAN_MAX_CALL_USD_'+p.upper(),'0'))
        budget=float(os.getenv('TITAN_DAILY_USD','0'))
        if not math.isfinite(cost) or not math.isfinite(budget) or cost<0 or budget<0:raise ConfigurationError('Invalid spending configuration')
        if not free and (cost<=0 or budget<=0):raise ConfigurationError('Provider disabled by zero-spend policy')
        if sum(len(m['content']) for m in messages)>48000:raise ConfigurationError('Prompt exceeds 48000 character ceiling')
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            start=int(time.time()//86400)*86400
            n,total=c.execute('SELECT COUNT(*),COALESCE(SUM(cost),0) FROM calls WHERE ts>=?',(start,)).fetchone()
            if n>=int(os.getenv('TITAN_DAILY_CALLS','50')) or total+cost>budget:raise ConfigurationError('Daily quota exhausted')
            cur=c.execute('INSERT INTO calls(provider,model,ts,status,cost) VALUES(?,?,?,?,?)',(p,model,time.time(),'reserved',cost))
            return cur.lastrowid
    async def call(self,p,messages):
        if p=='local':
            url=os.getenv('TITAN_LOCAL_URL','http://127.0.0.1:11434/v1/chat/completions');u=urlsplit(url)
            if os.getenv('TITAN_LOCAL_ENABLED')!='1' or u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.query or u.fragment or not u.port or u.port<1024:raise ConfigurationError('Local inference requires explicit loopback configuration')
            key='local';default=os.getenv('TITAN_MODEL_LOCAL','')
            if not default:raise ConfigurationError('Select a local model')
        else:
            if p not in PROVIDERS:raise ConfigurationError('Unknown provider')
            url,env,default=PROVIDERS[p];key=os.getenv(env)
            if not key:raise ConfigurationError('Missing '+env)
        model=os.getenv('TITAN_MODEL_'+p.upper(),default)
        cid=self.reserve(p,model,messages);start=time.monotonic()
        try:
            if p=='claude':
                payload={'model':model,'max_tokens':1200,'system':'\n'.join(m['content'] for m in messages if m['role']=='system'),'messages':[m for m in messages if m['role']!='system']}
                headers={'x-api-key':key,'anthropic-version':'2023-06-01','Content-Type':'application/json'}
            else:
                payload={'model':model,'messages':messages,'max_tokens':1200}
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
            data=await asyncio.to_thread(request_json,url,headers,payload)
            content=''.join(x.get('text','') for x in data['content']) if p=='claude' else data['choices'][0]['message']['content']
            if not isinstance(content,str) or not content.strip():raise ProviderError('Empty model response')
            from .security import redact
            content=redact(content)
            with self.db.connect() as c:c.execute("UPDATE calls SET status='ok',latency=? WHERE id=?",(time.monotonic()-start,cid))
            return content[:20000]
        except Exception as e:
            with self.db.connect() as c:c.execute("UPDATE calls SET status='failed',latency=? WHERE id=?",(time.monotonic()-start,cid))
            if isinstance(e,(ConfigurationError,ProviderError)):raise
            raise ProviderError('Invalid provider response') from None

    async def call_any(self,messages,providers=None):
        candidates=providers if providers is not None else self.rank()
        if not isinstance(candidates,list) or not candidates or len(candidates)>7 or any(not isinstance(p,str) or p not in {*PROVIDERS,'local'} for p in candidates):raise ConfigurationError('No usable providers configured')
        messages=compact_context(messages)
        failures=[]
        for provider in dict.fromkeys(candidates):
            # Brief circuit breaker on repeated observed failures; no synthetic success is inserted.
            with self.db.connect() as c:
                recent=c.execute('SELECT status FROM calls WHERE provider=? AND ts>? ORDER BY id DESC LIMIT 3',(provider,time.time()-60)).fetchall()
            if len(recent)==3 and all(r[0]=='failed' for r in recent):
                failures.append({'provider':provider,'reason':'circuit_open'});continue
            try:
                content=await self.call(provider,messages)
                return {'provider':provider,'content':content,'failover':failures}
            except (ConfigurationError,ProviderError) as error:
                failures.append({'provider':provider,'reason':str(error)})
        raise ConfigurationError('No provider succeeded: '+json.dumps(failures))

def compact_context(messages,limit=28000):
    if not isinstance(messages,list) or not messages:raise ValueError('Messages required')
    if any(not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),str) for m in messages):raise ValueError('Invalid messages')
    system=[dict(m) for m in messages if m['role']=='system']
    if sum(len(m['content']) for m in system)>limit//2:raise ValueError('System instructions exceed context budget')
    tail=[dict(m) for m in messages if m['role']!='system']
    budget=limit-sum(len(m['content']) for m in system)
    chosen=[]
    for m in reversed(tail):
        if not chosen and len(m['content'])>budget:raise ValueError('Latest request exceeds context budget')
        if len(m['content'])>budget:break
        chosen.append(m);budget-=len(m['content'])
    return system+list(reversed(chosen))
