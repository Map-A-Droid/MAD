class NoopCache:
    def set(self, key, value, ex=None):
        pass

    def get(self, key):
        pass

    def exists(self, key):
        return False
