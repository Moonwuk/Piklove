import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


def validate_init_data(
    init_data: str, bot_token: str, max_age: int = 300, now: int | None = None
) -> dict:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received = values.pop("hash", None)
    if not received:
        raise InitDataError("missing hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InitDataError("invalid hash")
    try:
        auth_date = int(values["auth_date"])
    except (KeyError, ValueError):
        raise InitDataError("invalid auth_date") from None
    if abs((now or int(time.time())) - auth_date) > max_age:
        raise InitDataError("expired auth_date")
    try:
        return json.loads(values["user"])
    except (KeyError, json.JSONDecodeError):
        raise InitDataError("invalid user") from None
