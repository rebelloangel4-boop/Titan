import hashlib, json, os, re, secrets, socket, ipaddress
from urllib.parse import urlsplit

SECRET_NAMES=('GEMINI_API_KEY','GROQ_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','XAI_API_KEY','GITHUB_TOKEN','TELEGRAM_BOT_TOKEN','TITAN_TOKEN','GOOGLE_ACCESS_TOKEN','GOOGLE_REFRESH_TOKEN','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','TITAN_MCP_TOKEN')
def redact(text):
    for key in SECRET_NAMES:
        val=os.getenv(key)
        if val:text=text.replace(val,'[REDACTED]')
    return re.sub(r'(?i)(bearer\s+)[A-Za-z0-9_.-]+',r'\1[REDACTED]',text)
def digest(tool,args):return hashlib.sha256(json.dumps([tool,args],sort_keys=True,separators=(',',':')).encode()).hexdigest()
def authenticate(header,token):return bool(token) and secrets.compare_digest(header or '', 'Bearer '+token)
def public_https(url,allowed):
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.hostname not in allowed:raise PermissionError('Destination is not explicitly allowed')
    addresses=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise PermissionError('Private destinations are forbidden')
    return url

def load_secret_files():
    """Load explicitly configured Docker/systemd secret files; never discover or log secrets."""
    from pathlib import Path
    import stat
    for name in SECRET_NAMES:
        path=os.getenv(name+'_FILE')
        if not path:continue
        if os.getenv(name):raise ValueError('Configure only one source for '+name)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'r') as f:
            mode=os.fstat(f.fileno()).st_mode
            if not stat.S_ISREG(mode):raise ValueError('Secret source must be a regular file')
            value=f.read(8193).strip()
        if not value or len(value)>8192 or '\n' in value:raise ValueError('Invalid secret file for '+name)
        os.environ[name]=value
