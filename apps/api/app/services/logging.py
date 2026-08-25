import json
import logging
logger=logging.getLogger("piklove")
_ALLOWED={"request_id","user_id","conversation_id","telegram_message_id","event_type","latency","error_code"}
def safe_log_event(event_type:str,**fields):
    payload={"event_type":event_type}; payload.update({k:v for k,v in fields.items() if k in _ALLOWED}); logger.info(json.dumps(payload,default=str))
