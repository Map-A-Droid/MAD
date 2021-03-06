class NoopCache:
    async def set(self, key, value, ex=None):
        pass

    async def get(self, key):
        pass

    async def exists(self, key):
        return False
