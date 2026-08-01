"""Content-addressed disk cache.

Immutable resources (a filed document, a published quarterly dataset) are cached
forever; mutable ones take a TTL. Nothing here is ever committed - the whole
directory is gitignored and restored in CI by actions/cache.
"""

import hashlib
import os
import time


class Cache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, url):
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        bucket = os.path.join(self.root, digest[:2])
        os.makedirs(bucket, exist_ok=True)
        return os.path.join(bucket, digest[2:] + ".bin")

    def get(self, url, ttl=None):
        path = self._path(url)
        if not os.path.exists(path):
            return None
        if ttl is not None and (time.time() - os.path.getmtime(path)) > ttl:
            return None
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def put(self, url, payload):
        path = self._path(url)
        tmp = path + ".tmp"
        try:
            with open(tmp, "wb") as handle:
                handle.write(payload)
            os.replace(tmp, path)
        except OSError:
            pass


class NullCache:
    def get(self, url, ttl=None):
        return None

    def put(self, url, payload):
        pass
