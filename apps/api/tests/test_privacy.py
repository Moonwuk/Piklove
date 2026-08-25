import logging
from app.services.logging import safe_log_event
def test_raw_text_never_logged(caplog):
 secret="very private message";caplog.set_level(logging.INFO,logger="piklove");safe_log_event("message_received",message_text=secret,telegram_message_id=7);assert secret not in caplog.text;assert '"telegram_message_id": 7' in caplog.text
