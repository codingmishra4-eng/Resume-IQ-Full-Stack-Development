"""Bounded process-local abuse controls; verified identities, never token text."""
from collections import OrderedDict
from threading import Lock
from time import monotonic
from backend.api_v1.errors import APIError


class UserRateLimit:
    def __init__(self, requests=120, writes=12, clock=monotonic, capacity=4096):
        self.requests, self.writes, self.clock, self.capacity = requests, writes, clock, capacity
        self.entries, self.lock = OrderedDict(), Lock()

    def check(self, owner, write=False):
        now = self.clock()
        with self.lock:
            # Insertion order follows the most recent fixed-window reset. Never
            # evict an active window: churn must not reset an existing quota.
            while self.entries and next(iter(self.entries.values()))[0] + 60 <= now:
                self.entries.popitem(last=False)
            if owner not in self.entries:
                if len(self.entries) >= self.capacity:
                    self.deny()
                self.entries[owner] = [now, 0, 0]
            entry = self.entries[owner]
            if entry[1] >= self.requests or (write and entry[2] >= self.writes):
                self.deny()
            entry[1] += 1
            entry[2] += int(write)

    @staticmethod
    def deny():
        error = APIError('rate_limited', 'Too many requests. Try again shortly.', 429)
        error.headers = {'Retry-After': '60'}
        raise error
