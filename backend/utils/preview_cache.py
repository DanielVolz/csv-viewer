import threading
import time

class PreviewCache:
    def __init__(self, max_age_seconds=300):
        self._cache = {}
        self._lock = threading.Lock()
        self.max_age = max_age_seconds

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            value, ts = entry
            if time.time() - ts > self.max_age:
                del self._cache[key]
                return None
            return value

    def set(self, key, value):
        with self._lock:
            self._cache[key] = (value, time.time())

    def invalidate(self, key_prefix=None):
        with self._lock:
            if key_prefix is None:
                self._cache.clear()
            else:
                to_del = [k for k in self._cache if k.startswith(key_prefix)]
                for k in to_del:
                    del self._cache[k]

preview_cache = PreviewCache(max_age_seconds=300)
