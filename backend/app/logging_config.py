import logging

from .config import settings
from .responses import request_id_var


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.actor_id = getattr(record, "actor_id", "-")
        record.action = getattr(record, "action", "-")
        record.object_id = getattr(record, "object_id", "-")
        return True


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format='{"timestamp":"%(asctime)s","level":"%(levelname)s","request_id":"%(request_id)s","actor_id":"%(actor_id)s","action":"%(action)s","object_id":"%(object_id)s","logger":"%(name)s","message":"%(message)s"}',
    )
    context_filter = RequestContextFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(context_filter)
