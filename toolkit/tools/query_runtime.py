"""Request-scoped cancellation for read-only SQLite and DuckDB cursors."""
import threading

_local = threading.local()


class QueryCancelled(Exception):
    pass


class QueryRuntime:
    def __init__(self):
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.connections = set()

    def __enter__(self):
        self.previous = getattr(_local, 'runtime', None)
        _local.runtime = self
        return self

    def __exit__(self, *exc):
        _local.runtime = self.previous

    def register(self, connection):
        if connection is None:return
        with self.lock:self.connections.add(connection)
        if hasattr(connection, 'set_progress_handler'):
            connection.set_progress_handler(lambda: int(self.stopped.is_set()), 5000)
        self.check()

    def unregister(self, connection):
        with self.lock:self.connections.discard(connection)

    def check(self):
        if self.stopped.is_set():raise QueryCancelled('Query cancelled')

    def cancel(self):
        self.stopped.set()
        with self.lock:
            for connection in tuple(self.connections):
                try:connection.interrupt()
                except Exception:pass


def current_runtime():
    return getattr(_local, 'runtime', None)


def check_cancelled():
    runtime = current_runtime()
    if runtime:runtime.check()
