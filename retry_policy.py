"""Bounded automatic retries for temporary PDF processing failures."""
import datetime

MAX_ATTEMPTS = 5
# Delays after attempts 1, 2, 3 and 4 (minutes).
BACKOFF_MINUTES = (1, 2, 5, 10)

def should_retry(error, attempts):
    """Permanent errors (including output collisions) never enter a retry loop."""
    return (isinstance(error, (OSError, TimeoutError))
            and not isinstance(error, (FileExistsError, PermissionError, IsADirectoryError))
            and attempts < MAX_ATTEMPTS)

def next_retry(attempts, now=None):
    if not 1 <= attempts < MAX_ATTEMPTS:
        raise ValueError("Retry limit reached")
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    return (now + datetime.timedelta(minutes=BACKOFF_MINUTES[attempts - 1])).isoformat()
