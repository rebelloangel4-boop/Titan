"""MCP 2025-03-26 JSON HTTP subset with initialization, session headers, and notification.
SSE/stdio, newer protocols, and server-initiated requests are explicitly unsupported.
"""
import json
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from .providers import NoRedirect,ProviderError

class Client:
 def __init__(self,url,token=None):
  self.url=url;self.headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
  if token:self.headers['Authorization']='Bearer '+token
 def send(self,body):
  try:
   with build_opener(NoRedirect).open(Request(self.url,data=json.dumps(body).encode(),headers=self.headers),timeout=30) as r:
    session=r.headers.get('Mcp-Session-Id')
    if session:self.headers['Mcp-Session-Id']=session
    if r.status==202:return None
    if 'application/json' not in r.headers.get('Content-Type',''):raise ProviderError('MCP SSE transport unsupported; JSON HTTP server required')
    raw=r.read(2_000_001)
    if len(raw)>2_000_000:raise ProviderError('MCP response too large')
    result=json.loads(raw)
    if result.get('error'):raise ProviderError('MCP remote error')
    if result.get('id')!=body.get('id'):raise ProviderError('MCP response ID mismatch')
    return result
  except HTTPError as e:raise ProviderError('MCP HTTP '+str(e.code)) from None
  except (URLError,OSError,ValueError):raise ProviderError('MCP connection or decoding error') from None
 def call(self,name,args):
  init=self.send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'titan','version':'0.2'}}})
  if not init or init.get('result',{}).get('protocolVersion')!='2025-03-26':raise ProviderError('MCP negotiated unsupported protocol')
  self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
  result=self.send({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':args}})
  if not result or 'result' not in result:raise ProviderError('MCP tool returned no result')
  if result['result'].get('isError'):raise ProviderError('MCP tool execution failed')
  return result['result']
