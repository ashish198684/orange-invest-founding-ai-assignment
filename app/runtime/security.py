"""Synthetic local password login; signed expiring sessions and cookie-route CSRF."""
import hashlib
import hmac
import secrets
import os
from urllib.parse import urlsplit
from datetime import datetime,timedelta,timezone
from app.runtime.pg import PgStore
from app.runtime.provider_client import settings

def hashed(value):return hashlib.sha256(value.encode()).hexdigest()
def login(username,password):
    store=PgStore(username)
    with store.connect(write=True) as db:
        user=db.execute('SELECT * FROM users WHERE user_id=?',(username,)).fetchone()
        if not user:raise PermissionError('invalid_credentials')
        trial=hashlib.scrypt(password.encode(),salt=bytes.fromhex(user['salt']),n=16384,r=8,p=1).hex()
        if not hmac.compare_digest(trial,user['password_hash']):raise PermissionError('invalid_credentials')
        sid=secrets.token_hex(32);csrf=secrets.token_hex(32)
        signature=hmac.new(bytes.fromhex(settings()['session_secret']),sid.encode(),'sha256').hexdigest()
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashed(sid),username,hashed(csrf),datetime.now(timezone.utc)+timedelta(hours=2)))
    return sid+'.'+signature,csrf

def authenticate(cookie):
    from http.cookies import SimpleCookie,CookieError
    try:
        cookies=SimpleCookie();cookies.load(cookie)
        sid,sig=cookies['orange_session'].value.split('.')
        expected=hmac.new(bytes.fromhex(settings()['session_secret']),sid.encode(),'sha256').hexdigest()
        if not hmac.compare_digest(sig,expected):raise ValueError()
        with PgStore('auth').connect() as db:
            session=db.execute('SELECT * FROM sessions WHERE session_hash=? AND expires_at>clock_timestamp()',(hashed(sid),)).fetchone()
        if not session:raise ValueError()
        return dict(session)
    except (ValueError,KeyError,TypeError,CookieError):raise PermissionError('unauthenticated') from None

def allowed_origin(origin):
    """Exact local origin allowlist; optional extra origin is loopback-only for isolated tests."""
    allowed={'http://127.0.0.1:8080','http://127.0.0.1:8081','http://127.0.0.1:8082','http://localhost:8080'}
    if origin in allowed:return True
    configured=os.getenv('ORANGE_ADDITIONAL_LOOPBACK_ORIGIN','')
    if not configured or origin!=configured:return False
    try:
        parsed=urlsplit(configured)
        return (parsed.scheme=='http' and parsed.hostname=='127.0.0.1'
                and parsed.port is not None and 1024<=parsed.port<=65535
                and not parsed.username and not parsed.password
                and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:return False

def check_csrf(session,token,origin):
    if not allowed_origin(origin) or not token or not hmac.compare_digest(session['csrf_hash'],hashed(token)):
        raise PermissionError('csrf_denied')
