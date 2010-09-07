# Written by Andrea Reale
# see LICENSE.txt for license information


from time import time

class SimpleTokenBucket(object):
    """
    A simple implementation of a token bucket, to
    control the rate of subtitles being uploaded.
    
    1 token corresponds to 1 KB
    
    Not threadsafe!!
    """
    
    def __init__(self, fill_rate, capacity = -1):
        """
        Creates a token bucket initialy having 0 tokens,
        with the given fill_rate.
        
        @param fill_rate: number of tokens refilled per second.
                          a token corrisponds to 1KB
        @param capacity: maximum number of tokens in the bucket.
        """
        
        #infinite bucket! (well, really big at least)
        if capacity == -1:
            capacity = 2**30 # 1 TeraByte capacity
        self.capacity = float(capacity)
        
        self._tokens = float(0)
        
        self.fill_rate = float(fill_rate)
        self.timestamp = time()

    def consume(self, tokens):
        """Consume tokens from the bucket. Returns True if there were
        sufficient tokens otherwise False."""
        if tokens <= self.tokens:
            self._tokens -= tokens
        else:
            return False
        return True
    
    def _consume_all(self):
        """
        Consumes every token in the bucket
        """
        self._tokens = float(0)

    @property
    def tokens(self):
        if self._tokens < self.capacity:
            now = time()
            delta = self.fill_rate * (now - self.timestamp)
            self._tokens = min(self.capacity, self._tokens + delta)
            self.timestamp = now
        return self._tokens
    
    @property
    def upload_rate(self):
        return self.fill_rate