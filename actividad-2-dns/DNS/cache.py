class DNSCache:
    """
    Caches the answers of the most frequent domains of the last queries.

    The history is a sliding window of max_size queries, and only the top k
    domains inside that window are kept in the cache.
    """
    def __init__(self):
        self.history = []
        self.max_size = 20
        self.cache = {}

    def add_to_history(self, domain):
        """Records a query, dropping the oldest one once the window is full."""
        if (len(self.history) >= self.max_size):
            self.history.pop(0)
        self.history.append(domain)

    def get_count(self):
        """How many times each domain appears in the window."""
        count = {}
        for domain in self.history:
            if domain in count:
                count[domain] += 1
            else:
                count[domain] = 1
        return count

    def get_top_k(self, k=3):
        """The k most frequent (domain, count) pairs, most frequent first."""
        count = self.get_count()
        sorted_domains = sorted(count.items(), key=lambda x: x[1], reverse=True)
        return sorted_domains[:k]

    def get_top_domains(self, k=3):
        """Just the names of get_top_k, without the counts."""
        return [domain for domain, _ in self.get_top_k(k)]

    def clean_cache(self):
        """Drops the entries whose domain fell out of the top k."""
        top = self.get_top_domains()
        clean = {}
        for domain in self.cache:
            if domain in top:
                clean[domain] = self.cache[domain]
        self.cache = clean

    def add(self, domain, answer=None):
        """Registers the query and stores its answer if the domain is in the top k."""
        self.add_to_history(domain)
        self.clean_cache()
        if answer is not None and domain in self.get_top_domains():
            self.cache[domain] = answer

    def get_dominio(self, domain):
        """The stored response for domain, or None if it is not cached."""
        return self.cache.get(domain, None)
