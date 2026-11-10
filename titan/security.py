import hashlib, json, os, re, secrets, socket, ipaddress, time
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


# Device-bound approval signatures. Cryptography is loaded lazily so the original
# stdlib-only worker remains usable when the optional API extra is not installed.
def register_device_public_key(db, device_id, algorithm, public_key):
    import re
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519
    if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", device_id):
        raise ValueError("Invalid device ID")
    if algorithm not in ("ECDSA_P256_SHA256", "ED25519"):
        raise ValueError("Unsupported device signature algorithm")
    if not isinstance(public_key, str) or not 32 <= len(public_key) <= 12000:
        raise ValueError("Invalid public key")
    try:
        raw = public_key.encode()
        key = serialization.load_pem_public_key(raw) if b"-----BEGIN" in raw else serialization.load_der_public_key(__import__("base64").b64decode(public_key, validate=True))
    except Exception as exc:
        raise ValueError("Invalid public key encoding") from exc
    if algorithm == "ECDSA_P256_SHA256":
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError("ECDSA P-256 public key required")
    elif not isinstance(key, ed25519.Ed25519PublicKey):
        raise ValueError("Ed25519 public key required")
    canonical = key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    with db.connect() as c:
        c.execute("INSERT INTO titan_devices(device_id,algorithm,public_key,created,revoked) VALUES(?,?,?,?,0) ON CONFLICT(device_id) DO UPDATE SET algorithm=excluded.algorithm,public_key=excluded.public_key,created=excluded.created,revoked=0",
                  (device_id, algorithm, canonical, time.time()))
    return {"device_id": device_id, "algorithm": algorithm, "registered": True}


def approval_signing_payload(device_id, approval_id, action_digest, expiry, nonce):
    return json.dumps({
        "domain": "TITAN_APPROVAL_V1",
        "device_id": device_id,
        "approval_id": approval_id,
        "action_digest": action_digest,
        "expiry": int(expiry),
        "nonce": nonce,
    }, sort_keys=True, separators=(",", ":")).encode()


def create_approval_challenge(db, approval_id, device_id, ttl=120):
    import re
    if not isinstance(approval_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", approval_id):
        raise ValueError("Invalid approval ID")
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("Invalid device ID")
    if type(ttl) is not int or not 30 <= ttl <= 300:
        raise ValueError("Challenge lifetime must be 30–300 seconds")
    now = int(time.time())
    expiry = now + ttl
    nonce = secrets.token_urlsafe(32)
    with db.connect() as c:
        device = c.execute("SELECT algorithm FROM titan_devices WHERE device_id=? AND revoked=0", (device_id,)).fetchone()
        approval = c.execute("SELECT digest,status FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not device:
            raise PermissionError("Device is not registered")
        if not approval or approval["status"] != "pending":
            raise ValueError("Approval is not pending")
        c.execute("INSERT INTO approval_challenges(nonce,approval_id,device_id,action_digest,expiry,used,created) VALUES(?,?,?,?,?,0,?)",
                  (nonce, approval_id, device_id, approval["digest"], expiry, time.time()))
    payload = approval_signing_payload(device_id, approval_id, approval["digest"], expiry, nonce)
    return {
        "device_id": device_id,
        "approval_id": approval_id,
        "action_digest": approval["digest"],
        "expiry": expiry,
        "nonce": nonce,
        "algorithm": device["algorithm"],
        "signed_payload": __import__("base64").b64encode(payload).decode(),
    }


def verify_approval_signature(db, device_id, approval_id, action_digest, expiry, nonce, signature):
    """Verify and consume a device challenge atomically; nonce replay is rejected."""
    import base64
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519
    if type(expiry) is not int or not isinstance(nonce, str) or not 32 <= len(nonce) <= 128:
        raise PermissionError("Invalid or expired approval challenge")
    if not isinstance(signature, str) or not 8 <= len(signature) <= 2048:
        raise PermissionError("Invalid approval signature")
    try:
        signature_bytes = base64.b64decode(signature, validate=True)
    except Exception as exc:
        raise PermissionError("Invalid approval signature encoding") from exc
    payload = approval_signing_payload(device_id, approval_id, action_digest, expiry, nonce)
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        challenge = c.execute("SELECT * FROM approval_challenges WHERE nonce=?", (nonce,)).fetchone()
        device = c.execute("SELECT algorithm,public_key FROM titan_devices WHERE device_id=? AND revoked=0", (device_id,)).fetchone()
        approval = c.execute("SELECT digest,status FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not challenge or not device or not approval:
            raise PermissionError("Approval challenge not found")
        if challenge["used"] or challenge["expiry"] <= int(time.time()) or expiry != challenge["expiry"]:
            raise PermissionError("Approval challenge expired or already used")
        if challenge["approval_id"] != approval_id or challenge["device_id"] != device_id:
            raise PermissionError("Approval challenge binding mismatch")
        if challenge["action_digest"] != action_digest or approval["digest"] != action_digest or approval["status"] != "pending":
            raise PermissionError("Approval action changed or is no longer pending")
        try:
            key = serialization.load_pem_public_key(device["public_key"].encode())
            if device["algorithm"] == "ECDSA_P256_SHA256":
                key.verify(signature_bytes, payload, ec.ECDSA(__import__("cryptography.hazmat.primitives.hashes", fromlist=["SHA256"]).SHA256()))
            elif device["algorithm"] == "ED25519":
                key.verify(signature_bytes, payload)
            else:
                raise PermissionError("Unsupported registered key algorithm")
        except InvalidSignature as exc:
            raise PermissionError("Approval signature verification failed") from exc
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError("Approval signature verification failed") from exc
        changed = c.execute("UPDATE approval_challenges SET used=1 WHERE nonce=? AND used=0", (nonce,)).rowcount
        approved = c.execute("UPDATE approvals SET status='approved' WHERE id=? AND status='pending' AND digest=?", (approval_id, action_digest)).rowcount
        if changed != 1 or approved != 1:
            raise PermissionError("Approval challenge was already consumed")
    db.event(None, "approval", "Device-signed operator approval " + approval_id)
    return {"approved": True, "approval_id": approval_id, "device_id": device_id}
