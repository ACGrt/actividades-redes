TYPE_A = b'\x00\x01'
TYPE_NS = b'\x00\x02'


def ip_to_str(rdata):
    return ".".join(str(byte) for byte in rdata)


def find_type(records, rr_type):
    for rr in records:
        if rr["rr_type"] == rr_type:
            return rr
    return None


class DNSMessage:
    def __init__(self, transaction_id, flags, qdcount, ancount, nscount, arcount,
                 qname, question_section, answers, authority, additional):
        self.transaction_id = transaction_id
        self.flags = flags
        self.qdcount = qdcount
        self.ancount = ancount
        self.nscount = nscount
        self.arcount = arcount
        self.qname = qname
        self.question_section = question_section
        self.answers = answers
        self.authority = authority
        self.additional = additional

    def to_bytes(self):
        return (self.transaction_id
                + self.flags
                + self.qdcount.to_bytes(2, byteorder='big')
                + self.ancount.to_bytes(2, byteorder='big')
                + self.nscount.to_bytes(2, byteorder='big')
                + self.arcount.to_bytes(2, byteorder='big')
                + self.question_section)

    def has_type_A(self):
        return find_type(self.answers, TYPE_A) is not None

    def get_answer(self):
        rr = find_type(self.answers, TYPE_A)
        return ip_to_str(rr["rr_rdata"]) if rr else None

    def get_authority(self):
        return self.authority

    def get_ns_name(self):
        rr = find_type(self.authority, TYPE_NS)
        return rr["rr_rdata"] if rr else None

    def get_additional(self):
        return self.additional

    def get_additional_ns(self):
        rr = find_type(self.additional, TYPE_A)
        return (rr["rr_name"], ip_to_str(rr["rr_rdata"])) if rr else (None, None)


def build_query(nombre, transaction_id=b'\x00\x2a'):
    qname = b"".join(bytes([len(l)]) + l.encode('ascii') for l in nombre.split('.')) + b'\x00'
    return (transaction_id
            + b'\x00\x00'
            + (1).to_bytes(2, byteorder='big')
            + b'\x00\x00' * 3
            + qname + TYPE_A + b'\x00\x01')
