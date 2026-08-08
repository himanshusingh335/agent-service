import json
import logging
import sys
from datetime import datetime, timezone

_RESERVED_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    DIM = "\033[2m"

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        prefix = f"{self.DIM}{timestamp}{self.RESET} {color}{record.levelname:<8}{self.RESET}"
        line = f"{prefix} {record.name}: {record.getMessage()}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(ColorFormatter() if sys.stdout.isatty() else JsonFormatter())
    root.addHandler(stream_handler)
