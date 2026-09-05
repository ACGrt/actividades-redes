TYPE_NS = b'\x00\x02'
TYPE_CNAME = b'\x00\x05'


class DNSParser:
    """
    Walks a raw DNS message field by field, turning it into a dict.

    Keeps an offset with how much of the message has been read, so the
    sections are parsed one after another.
    """
    def __init__(self, dns_data):
        self.dns_data = dns_data
        self.offset = 0

    def parseName(self, index):
        """
        Reads the domain name at index, following compression pointers.

        Returns the dotted name and the index right after it: for a compressed
        name that is past the pointer, not past the labels it jumps to.
        """
        labels = []
        end_index = None
        jumps = 0
        while True:
            length = self.dns_data[index]
            if length == 0:
                index += 1
                break
            if length & 0xC0 == 0xC0:
                pointer = int.from_bytes(self.dns_data[index:index + 2], 'big') & 0x3FFF
                if end_index is None:
                    end_index = index + 2
                jumps += 1
                index = pointer
                continue
            labels.append(self.dns_data[index + 1:index + 1 + length].decode('ascii'))
            index += 1 + length
        if end_index is None:
            end_index = index
        return ".".join(labels), end_index
    
    def parseHeader(self):
        """Reads the 12 bytes of the header and leaves the offset at the question."""
        transaction_id = self.dns_data[0:2]
        flags = self.dns_data[2:4]
        qdcount = int.from_bytes(self.dns_data[4:6], byteorder='big')
        ancount = int.from_bytes(self.dns_data[6:8], byteorder='big')
        nscount = int.from_bytes(self.dns_data[8:10], byteorder='big')
        arcount = int.from_bytes(self.dns_data[10:12], byteorder='big')
        self.offset = 12
        return {
            'transaction_id': transaction_id,
            'flags': flags,
            'qdcount': qdcount,
            'ancount': ancount,
            'nscount': nscount,
            'arcount': arcount
        }
    
    def parseQuestionSection(self):
        """
        Reads the question, returning the queried name and the raw bytes of the
        section, kept verbatim so a reply can echo them back unchanged.
        """
        qname, index = self.parseName(self.offset)
        question_section = self.dns_data[self.offset:index + 4]
        self.offset = index + 4
        return {
            "qname": qname,
            "question_section": question_section
        }

    def parseRR(self, start_index):
        """
        Reads one resource record starting at start_index.

        NS and CNAME rdata is decoded as a name, since it can itself contain
        compression pointers; any other type is left as raw bytes.
        """
        rr_name, index = self.parseName(start_index)
        rr_type = self.dns_data[index:index + 2]
        rr_class = self.dns_data[index + 2:index + 4]
        rr_ttl = int.from_bytes(self.dns_data[index + 4:index + 8], byteorder='big')
        rr_rdlength = int.from_bytes(self.dns_data[index + 8:index + 10], byteorder='big')
        rdata_start = index + 10
        rr_rdata = self.dns_data[rdata_start:rdata_start + rr_rdlength]
        if rr_type in (TYPE_NS, TYPE_CNAME):
            rr_rdata = self.parseName(rdata_start)[0]
        self.offset = rdata_start + rr_rdlength
        return {
            "rr_name": rr_name,
            "rr_type": rr_type,
            "rr_class": rr_class,
            "rr_ttl": rr_ttl,
            "rr_rdlength": rr_rdlength,
            "rr_rdata": rr_rdata,
        }

    def parseRRs(self, count):
        """Reads count consecutive records from the current offset."""
        records = []
        for _ in range(count):
            records.append(self.parseRR(self.offset))
        return records

    def parse(self):
        """Parses the whole message into a dict, ready for DNSMessage(**...)."""
        header = self.parseHeader()
        question_section = self.parseQuestionSection()
        return {
            **header,
            **question_section,
            "answers": self.parseRRs(header["ancount"]),
            "authority": self.parseRRs(header["nscount"]),
            "additional": self.parseRRs(header["arcount"]),
        }
