import random
import socket
import sys

class SocketTCP:
    HEADER_SIZE = 7
    MAX_PAYLOAD = 16
    BUFFER_SIZE = HEADER_SIZE + MAX_PAYLOAD

    # When True, prints how losses are being handled (to stderr)
    DEBUG = False

    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.dest_address = None
        self.bind_address = None

        self.seq_num = random.randint(0, 100)

        self.timeout = 1.0
        self.udp_socket.settimeout(self.timeout)

        self.remaining = 0
        self.recv_buffer = b""

    @staticmethod
    def parse_segment(raw_bytes):
        """
        Takes the raw bytes received via UDP and transforms them into an
        easy-to-access dictionary.
        """
        header = raw_bytes[:SocketTCP.HEADER_SIZE]
        data = raw_bytes[SocketTCP.HEADER_SIZE:]

        return {
            "seq": int.from_bytes(header[0:4], "big"),
            "ack": bool(header[4]),
            "syn": bool(header[5]),
            "fin": bool(header[6]),
            "data": data
        }

    @staticmethod
    def create_segment(segment_dict):
        """
        Takes a dictionary with the segment parameters and returns the bytes
        ready to be sent via UDP.
        Structure: {"seq": int, "ack": bool, "syn": bool, "fin": bool, "data": bytes}
        """
        header = segment_dict.get("seq", 0).to_bytes(4, "big") + bytes([
            1 if segment_dict.get("ack", False) else 0,
            1 if segment_dict.get("syn", False) else 0,
            1 if segment_dict.get("fin", False) else 0,
        ])

        data = segment_dict.get("data", b"")

        return header + data

    def bind(self, address):
        """Binds the socket to a specific (IP, port) address."""
        self.bind_address = address
        self.udp_socket.bind(address)

    def _debug(self, message):
        """Prints message to stderr only when debug mode is on."""
        if SocketTCP.DEBUG:
            print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

    def accept(self):
        """
        Waits for a SYN request.
        It implements the 3-way handshake from the server side.
        """
        while True:
            try:
                raw_bytes, client_address = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                segment = self.parse_segment(raw_bytes)

                if segment["syn"]:
                    self._debug(f"accept: SYN received (seq={segment['seq']})")
                    #Prepare new socket
                    new_socket = SocketTCP()
                    new_socket.dest_address = client_address
                    new_socket.bind((self.bind_address[0], self.bind_address[1]+1))

                    # Send SYN-ACK
                    self.seq_num = segment["seq"] + 1 # x + 1
                    syn_ack_segment = self.create_segment({
                        "seq": self.seq_num,
                        "ack": True,
                        "syn": True,
                        "fin": False,
                        "data": str(new_socket.bind_address[1]).encode()
                    })
                    self.udp_socket.sendto(syn_ack_segment, client_address)

                    # Wait for ACK on the new port
                    expected_seq = self.seq_num + 1 # x + 2
                    while True:
                        try:
                            raw_bytes, _ = new_socket.udp_socket.recvfrom(new_socket.BUFFER_SIZE)
                            ack_segment = new_socket.parse_segment(raw_bytes)

                            # ACK, or first data segment if the ACK was lost (implicit ACK)
                            if ack_segment["seq"] == expected_seq and not ack_segment["syn"]:
                                if not ack_segment["ack"]:
                                    self._debug("accept: handshake ACK lost, data segment taken as implicit ACK")
                                self._debug(f"accept: connection established on port {new_socket.bind_address[1]}")
                                new_socket.seq_num = expected_seq
                                return new_socket, new_socket.bind_address
                        except socket.timeout:
                            self._debug("accept: timeout waiting for ACK, resending SYN-ACK")
                            self.udp_socket.sendto(syn_ack_segment, client_address)

            except socket.timeout:
                continue

    def connect(self, address):
        """
        Initiates a connection to the server at the specified address.
        It implements the 3-way handshake from the client side.
        """
        self.dest_address = address

        # Send SYN
        syn_segment = self.create_segment({
            "seq": self.seq_num,
            "ack": False,
            "syn": True,
            "fin": False,
            "data": b""
        })
        self.udp_socket.sendto(syn_segment, address)

        # Wait for SYN-ACK
        while True:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                syn_ack_segment = self.parse_segment(raw_bytes)

                if syn_ack_segment["syn"] and syn_ack_segment["ack"] and syn_ack_segment["seq"] == self.seq_num + 1:
                    # Send ACK
                    self.seq_num = syn_ack_segment["seq"] + 1
                    new_port = int(syn_ack_segment["data"].decode())
                    self.dest_address = (address[0], new_port)
                    ack_segment = self.create_segment({
                        "seq": self.seq_num,
                        "ack": True,
                        "syn": False,
                        "fin": False,
                        "data": b""
                    })
                    self.udp_socket.sendto(ack_segment, self.dest_address)
                    self._debug(f"connect: connection established with port {new_port}")
                    return
            except socket.timeout:
                # Resend SYN if timeout occurs
                self._debug("connect: timeout waiting for SYN-ACK, resending SYN")
                self.udp_socket.sendto(syn_segment, address)

    def _send_and_wait_ack(self, data):
        """
        Sends a single data segment using Stop & Wait: retransmits it on every
        timeout until an ACK with seq_num + 1 arrives, then advances seq_num.
        """
        segment = self.create_segment({
            "seq": self.seq_num,
            "ack": False,
            "syn": False,
            "fin": False,
            "data": data
        })
        self.udp_socket.sendto(segment, self.dest_address)

        while True:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                ack_segment = self.parse_segment(raw_bytes)

                if ack_segment["ack"] and ack_segment["seq"] == self.seq_num + 1:
                    self.seq_num += 1
                    return
                elif not ack_segment["ack"] and ack_segment["seq"] < self.seq_num:
                    # resend ACK for previous segment
                    self._debug(f"send: duplicate segment seq={ack_segment['seq']} received, resending its ACK")
                    ack_segment = self.create_segment({
                        "seq": ack_segment["seq"] + 1,
                        "ack": True,
                        "syn": False,
                        "fin": False,
                        "data": b""
                    })
                    self.udp_socket.sendto(ack_segment, self.dest_address)
            except socket.timeout:
                self._debug(f"send: timeout waiting for ACK of seq={self.seq_num}, retransmitting")
                self.udp_socket.sendto(segment, self.dest_address)

    def _recv_segment(self):
        """
        Receives the next in-order data segment using Stop & Wait, ACKs it and
        returns its data. Duplicated segments are ACKed again and discarded.
        """
        while True:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
            except socket.timeout:
                continue
            segment = self.parse_segment(raw_bytes)
            if segment["ack"]:
                continue
            if segment["seq"] == self.seq_num:
                ack_segment = self.create_segment({
                    "seq": self.seq_num + 1,
                    "ack": True,
                    "syn": False,
                    "fin": False,
                    "data": b""
                })
                self.udp_socket.sendto(ack_segment, self.dest_address)
                self.seq_num += 1
                return segment["data"]
            elif segment["seq"] < self.seq_num:
                self._debug(f"recv: duplicate segment seq={segment['seq']} (its ACK was lost), resending ACK")
                ack_segment = self.create_segment({
                    "seq": segment["seq"] + 1,
                    "ack": True,
                    "syn": False,
                    "fin": False,
                    "data": b""
                })
                self.udp_socket.sendto(ack_segment, self.dest_address)

    def send(self, message):
        """
        Sends message using Stop & Wait. The first segment carries the message
        length, the following ones carry the message in chunks of MAX_PAYLOAD bytes.
        """
        self._send_and_wait_ack(str(len(message)).encode())
        for i in range(0, len(message), self.MAX_PAYLOAD):
            self._send_and_wait_ack(message[i:i+self.MAX_PAYLOAD])

    def recv(self, buff_size):
        """
        Receives at most buff_size bytes of the incoming message. If the message
        is longer, the rest can be read with further calls to recv.
        """
        if self.remaining == 0 and not self.recv_buffer:
            self.remaining = int(self._recv_segment().decode())

        while len(self.recv_buffer) < buff_size and self.remaining > 0:
            data = self._recv_segment()
            self.recv_buffer += data
            self.remaining -= len(data)

        result = self.recv_buffer[:buff_size]
        self.recv_buffer = self.recv_buffer[buff_size:]
        return result

    def close(self):
        """
        Closes the connection from Host A's side: sends FIN, waits for FIN+ACK
        (up to 3 timeouts) and answers with the final ACK, sent 3 times with a
        timeout between each send.
        """
        fin_segment = self.create_segment({
            "seq": self.seq_num,
            "ack": False,
            "syn": False,
            "fin": True,
            "data": b""
        })
        self.udp_socket.sendto(fin_segment, self.dest_address)
        timeouts = 0
        while timeouts < 3:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                fin_ack_segment = self.parse_segment(raw_bytes)
                if fin_ack_segment["ack"] and fin_ack_segment["fin"] and fin_ack_segment["seq"] == self.seq_num + 1:
                    self.seq_num += 2

                    ack_segment = self.create_segment({
                        "seq": self.seq_num,
                        "ack": True,
                        "syn": False,
                        "fin": False,
                        "data": b""
                    })
                    # Send the final ACK 3 times, waiting a timeout between sends
                    for i in range(3):
                        self._debug(f"close: sending final ACK ({i + 1}/3)")
                        self.udp_socket.sendto(ack_segment, self.dest_address)
                        if i < 2:
                            try:
                                self.udp_socket.recvfrom(self.BUFFER_SIZE)
                            except socket.timeout:
                                pass
                    break

            except socket.timeout:
                timeouts += 1
                self._debug(f"close: timeout waiting for FIN+ACK ({timeouts}/3), resending FIN")
                self.udp_socket.sendto(fin_segment, self.dest_address)

        if timeouts == 3:
            self._debug("close: no FIN+ACK after 3 timeouts, assuming the other side closed")
        self.udp_socket.close()

    def recv_close(self):
        """
        Closes the connection from Host B's side: waits for FIN, answers with
        FIN+ACK and waits for the final ACK (up to 3 timeouts).
        """
        while True:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
            except socket.timeout:
                continue

            segment = self.parse_segment(raw_bytes)

            if segment["fin"] and segment["seq"] == self.seq_num:
                break
            elif not segment["ack"] and segment["seq"] < self.seq_num:
                self._debug(f"recv_close: duplicate segment seq={segment['seq']} (its ACK was lost), resending ACK")
                ack_segment = self.create_segment({
                    "seq": segment["seq"] + 1,
                    "ack": True,
                    "syn": False,
                    "fin": False,
                    "data": b""
                })
                self.udp_socket.sendto(ack_segment, self.dest_address)
        self.seq_num += 1
        fin_ack_segment = self.create_segment({
            "seq": self.seq_num,
            "ack": True,
            "syn": False,
            "fin": True,
            "data": b""
        })
        self.udp_socket.sendto(fin_ack_segment, self.dest_address)

        timeouts = 0
        while timeouts < 3:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                segment = self.parse_segment(raw_bytes)
                if segment["ack"] and not segment["fin"] and segment["seq"] == self.seq_num + 1:
                    self.seq_num += 1
                    break
                elif segment["fin"]:
                    self._debug("recv_close: FIN received again (FIN+ACK was lost), resending FIN+ACK")
                    self.udp_socket.sendto(fin_ack_segment, self.dest_address)
            except socket.timeout:
                timeouts += 1
                self._debug(f"recv_close: timeout waiting for final ACK ({timeouts}/3)")

        if timeouts == 3:
            self._debug("recv_close: no final ACK after 3 timeouts, assuming the other side closed")
        self.udp_socket.close()