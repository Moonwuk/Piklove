import logging

from app.main import configure_logging
from app.services.logging import logger, safe_log_event


def test_raw_text_never_logged(caplog):
    secret = "very private message"
    caplog.set_level(logging.INFO, logger="piklove")
    safe_log_event("message_received", message_text=secret, telegram_message_id=7)
    assert secret not in caplog.text
    assert '"telegram_message_id": 7' in caplog.text


def test_structured_events_actually_reach_a_handler():
    """Regression: uvicorn never configures "piklove", so INFO events vanished.

    Every safe_log_event call in the service was a silent no-op in production —
    the default effective level is WARNING and no handler was attached.
    """
    configure_logging()
    assert logger.handlers, "no handler attached: structured events go nowhere"
    assert logger.isEnabledFor(logging.INFO)
