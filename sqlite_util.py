"""Shared SQLite helpers.

sqlite3's own context manager only commits or rolls back a transaction; the
connection and its file descriptor stay open. Long-running services that open
one connection per request or per job would therefore accumulate open file
descriptors. `session` yields a connection and always closes it.
"""
import contextlib
import sqlite3

@contextlib.contextmanager
def session(database, timeout=10, uri=False, isolation_level=""):
    """Yield a SQLite connection that is closed when the block ends.

    Like sqlite3's own context manager, the block commits on success and rolls
    back on error. The connection itself is closed in every case.
    """
    # isolation_level="" is the sqlite3 default. The sentinel keeps the caller's
    # choice distinguishable from an explicit "no transaction" request.
    level=isolation_level if isolation_level else ""
    if uri:
        con=sqlite3.connect(database,timeout=timeout,uri=True,isolation_level=level)
    else:
        con=sqlite3.connect(database,timeout=timeout,isolation_level=level)
    try:
        with con:
            yield con
    finally:
        con.close()
