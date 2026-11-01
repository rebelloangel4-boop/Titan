"""Google refresh-token support. Initial consent remains an operator setup step."""
import hashlib,json,os,threading,time
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from .providers import ConfigurationError,ProviderError,NoRedirect

_lock=threading.Lock()
_cache=None

def exchange(client_id,client_secret,refresh_token):
 request=Request('https://oauth2.googleapis.com/token',data=urlencode({'client_id':client_id,'client_secret':client_secret,'refresh_token':refresh_token,'grant_type':'refresh_token'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 try:
  with build_opener(NoRedirect).open(request,timeout=20) as response:
   raw=response.read(65537)
   if len(raw)>65536:raise ValueError()
   data=json.loads(raw)
  token=data.get('access_token');expires=data.get('expires_in')
  if not isinstance(token,str) or not token or len(token)>8192 or any(c.isspace() for c in token):raise ValueError()
  if type(expires) not in (int,float) or not 60<=expires<=86400 or data.get('token_type','Bearer').lower()!='bearer':raise ValueError()
  return token,expires
 except Exception:
  # OAuth responses and exception URLs can contain credentials; return no body.
  raise ProviderError('Google token refresh failed; check consent and credentials') from None

def access_token():
 global _cache
 refresh=os.getenv('GOOGLE_REFRESH_TOKEN')
 if not refresh:
  token=os.getenv('GOOGLE_ACCESS_TOKEN')
  if not token:raise ConfigurationError('Google OAuth credentials are not configured')
  return token
 client_id=os.getenv('GOOGLE_CLIENT_ID');secret=os.getenv('GOOGLE_CLIENT_SECRET')
 if not client_id or not secret:raise ConfigurationError('Refresh requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET')
 identity=hashlib.sha256(json.dumps([client_id,secret,refresh]).encode()).digest()
 with _lock:
  if _cache and _cache[0]==identity and time.monotonic()<_cache[2]:return _cache[1]
  token,expires=exchange(client_id,secret,refresh)
  _cache=(identity,token,time.monotonic()+expires-30)
  return token
