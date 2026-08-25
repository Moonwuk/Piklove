import hashlib
import hmac
import json
import pytest
from urllib.parse import urlencode
from app.security.telegram_init_data import InitDataError,validate_init_data
def build(now=1000,token="token"):
 d={"auth_date":str(now),"query_id":"q","user":json.dumps({"id":123,"first_name":"A"},separators=(",",":"))}; check="\n".join(f"{k}={v}" for k,v in sorted(d.items())); secret=hmac.new(b"WebAppData",token.encode(),hashlib.sha256).digest();d["hash"]=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest();return urlencode(d)
def test_valid(): assert validate_init_data(build(),"token",300,1000)["id"]==123
def test_invalid_hash():
 with pytest.raises(InitDataError,match="invalid hash"):validate_init_data(build()+"x","token",300,1000)
def test_expired():
 with pytest.raises(InitDataError,match="expired"):validate_init_data(build(),"token",300,2000)
