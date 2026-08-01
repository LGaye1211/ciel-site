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

    def prune(self, max_bytes):
        """Drop the least recently used entries down to a size budget.

        Company facts run to about a megabyte each, so an unbounded cache
        reaches a gigabyte in a single deep scan. That still works, but
        actions/cache has to save and restore it on every CI run, and a
        multi-gigabyte round trip costs more time than the requests it saves.
        """
        entries = []
        total = 0
        for root, _dirs, files in os.walk(self.root):
            for name in files:
                path = os.path.join(root, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                entries.append((stat.st_mtime, stat.st_size, path))
                total += stat.st_size
        if total <= max_bytes:
            return 0, total

        entries.sort()  # oldest first
        freed = 0
        for _mtime, size, path in entries:
            if total - freed <= max_bytes:
                break
            try:
                os.remove(path)
                freed += size
            except OSError:
                continue
        return freed, total - freed


class NullCache:
    def get(self, url, ttl=None):
        return None

    def put(self, url, payload):
        pass
