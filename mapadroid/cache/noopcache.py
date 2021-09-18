from typing import Optional


class NoopCache:
    async def set(self, key, value, ex: Optional[int] = None):
        pass

    async def get(self, key):
        pass

    async def exists(self, key):
        return False

    async def close(self):
        pass
