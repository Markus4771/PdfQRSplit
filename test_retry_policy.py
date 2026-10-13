"""Tests for automatic PDF retry policy."""
import datetime
import unittest
from retry_policy import MAX_ATTEMPTS, BACKOFF_MINUTES, should_retry, next_retry

class RetryPolicyTest(unittest.TestCase):
    def test_transient_retries_stop_at_limit(self):
        for count in range(1,MAX_ATTEMPTS):
            self.assertTrue(should_retry(OSError("temporarily unavailable"),count))
        self.assertFalse(should_retry(OSError("unavailable"),MAX_ATTEMPTS))
    def test_permanent_errors_not_retried(self):
        for error in (FileExistsError("collision"), PermissionError("denied"),ValueError("invalid"),RuntimeError("invalid")):
            self.assertFalse(should_retry(error,1))
    def test_backoff_schedule(self):
        base=datetime.datetime(2026,10,13,tzinfo=datetime.timezone.utc)
        for count,minutes in enumerate(BACKOFF_MINUTES,1):
            self.assertEqual(datetime.datetime.fromisoformat(next_retry(count,base)),base+datetime.timedelta(minutes=minutes))
    def test_backoff_limit(self):
        with self.assertRaises(ValueError):next_retry(MAX_ATTEMPTS)
if __name__=="__main__":
    unittest.main()
