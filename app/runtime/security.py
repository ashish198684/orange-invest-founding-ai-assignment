"""Synthetic local password login; signed expiring sessions and cookie-route CSRF."""
import hashlib
import hmac
import secrets
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
    try:
        from http.cookies import SimpleCookie
        cookies=SimpleCookie();cookies.load(cookie)
        sid,sig=cookies['orange_session'].value.split('.')
        expected=hmac.new(bytes.fromhex(settings()['session_secret']),sid.encode(),'sha256').hexdigest()
        if not hmac.compare_digest(sig,expected):raise ValueError()
        with PgStore('auth').connect() as db:
            session=db.execute('SELECT * FROM sessions WHERE session_hash=? AND expires_at>clock_timestamp()',(hashed(sid),)).fetchone()
        if not session:raise ValueError()
        return dict(session)
    except Exception:raise PermissionError('unauthenticated') from None

def check_csrf(session,token,origin):
    allowed={'http://127.0.0.1:8080','http://127.0.0.1:8081','http://127.0.0.1:8082','http://localhost:8080'}
    if origin not in allowed or not token or not hmac.compare_digest(session['csrf_hash'],hashed(token)):
        raise PermissionError('csrf_denied')
