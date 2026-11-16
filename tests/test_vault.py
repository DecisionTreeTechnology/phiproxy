import time

from phiveil import EntityType as T
from phiveil import InMemoryVault, RedisVault


class FakeRedis:
    """Just the commands RedisVault uses."""

    def __init__(self):
        self.h: dict[str, dict[str, str]] = {}
        self.s: dict[str, str] = {}

    def hget(self, k, f):
        return self.h.get(k, {}).get(f)

    def hset(self, k, f, v):
        self.h.setdefault(k, {})[f] = str(v)

    def hsetnx(self, k, f, v):
        if f in self.h.get(k, {}):
            return 0
        self.hset(k, f, v)
        return 1

    def hincrby(self, k, f, n):
        cur = int(self.h.get(k, {}).get(f, 0)) + n
        self.hset(k, f, cur)
        return cur

    def hgetall(self, k):
        return dict(self.h.get(k, {}))

    def expire(self, k, ttl):
        return 1

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.s:
            return None
        self.s[k] = str(v)
        return True

    def get(self, k):
        return self.s.get(k)

    def delete(self, *keys):
        for k in keys:
            self.h.pop(k, None)
            self.s.pop(k, None)


def _contract(v):
    t1 = v.token_for("s", T.PHONE, "416-555-0142")
    assert t1 == "[PHONE_1]"
    assert v.token_for("s", T.PHONE, "(416) 555 0142") == t1  # normalized
    assert v.token_for("s", T.PHONE, "647-555-0199") == "[PHONE_2]"
    assert v.token_for("s", T.NAME, "Sarah") == "[NAME_1]"
    assert v.token_for("s", T.NAME, "sarah") == "[NAME_1]"
    assert v.value_for("s", t1) == "416-555-0142"
    assert v.mapping("s")["[NAME_1]"] == "Sarah"
    off = v.date_offset("s")
    assert off != 0 and v.date_offset("s") == off and 7 <= abs(off) <= 60
    v.forget("s")
    assert v.value_for("s", t1) is None


def test_in_memory_contract():
    _contract(InMemoryVault())


def test_redis_contract():
    _contract(RedisVault(client=FakeRedis()))


def test_in_memory_ttl():
    v = InMemoryVault(ttl_seconds=0.01)
    v.token_for("s", T.NAME, "Sarah")
    time.sleep(0.02)
    assert v.value_for("s", "[NAME_1]") is None
