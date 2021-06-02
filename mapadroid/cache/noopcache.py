from typing import Optional


class NoopCache:
    async def set(self, key, value, expire: Optional[int] = None):
        pass

    async def get(self, key):
        pass

    async def exists(self, key):
        return False
