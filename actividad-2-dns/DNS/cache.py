class DNSCache:
    def __init__(self):
        self.history = []
        self.max_size = 20
        self.cache = {}

    def add_to_history(self, domain):
        if (len(self.history) >= self.max_size):
            self.history.pop(0)
        self.history.append(domain)

    def get_count(self):
        count = {}
        for domain in self.history:
            if domain in count:
                count[domain] += 1
            else:
                count[domain] = 1
        return count

    def get_top_k(self, k=3):
        count = self.get_count()
        sorted_domains = sorted(count.items(), key=lambda x: x[1], reverse=True)
        return sorted_domains[:k]

    def get_top_domains(self, k=3):
        return [domain for domain, _ in self.get_top_k(k)]

    def clean_cache(self):
        top = self.get_top_domains()
        clean = {}
        for domain in self.cache:
            if domain in top:
                clean[domain] = self.cache[domain]
        self.cache = clean

    def add(self, domain, answer=None):
        self.add_to_history(domain)
        self.clean_cache()
        if answer is not None and domain in self.get_top_domains():
            self.cache[domain] = answer

    def get_dominio(self, domain):
        return self.cache.get(domain, None)
