import base64
import hashlib
import hmac
import time
from app.config import get_settings
def create_session(user_id:str)->str:
    body=base64.urlsafe_b64encode(f"{user_id}:{int(time.time())}".encode()).decode(); sig=hmac.new(get_settings().session_secret.encode(),body.encode(),hashlib.sha256).hexdigest(); return f"{body}.{sig}"
def read_session(token:str)->str|None:
    try:
        body,sig=token.rsplit(".",1); expected=hmac.new(get_settings().session_secret.encode(),body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return None
        raw=base64.urlsafe_b64decode(body).decode(); user_id,created=raw.rsplit(":",1)
        return user_id if int(time.time())-int(created)<2_592_000 else None
    except Exception: return None
