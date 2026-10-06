import random
import socket

class SocketTCP:
    HEADER_SIZE = 7
    MAX_PAYLOAD = 16
    BUFFER_SIZE = HEADER_SIZE + MAX_PAYLOAD

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

                    # Wait for ACK
                    try: 
                        raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
                        ack_segment = self.parse_segment(raw_bytes)

                        if ack_segment["ack"] and ack_segment["seq"] == self.seq_num + 1:
                            new_socket.seq_num = ack_segment["seq"]
                            return new_socket, new_socket.bind_address
                    except socket.timeout:
                        pass
                    new_socket.udp_socket.close()

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
            "seq": self.seq_num, # x
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
                    self.seq_num = syn_ack_segment["seq"] + 1 # x+2
                    new_port = int(syn_ack_segment["data"].decode())
                    ack_segment = self.create_segment({
                        "seq": self.seq_num,
                        "ack": True,
                        "syn": False,
                        "fin": False,
                        "data": b""
                    })
                    self.udp_socket.sendto(ack_segment, address)
                    self.dest_address = (address[0], new_port)
                    return
            except socket.timeout:
                # Resend SYN if timeout occurs
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
            except socket.timeout:
                self.udp_socket.sendto(segment, self.dest_address)

    def _recv_segment(self):
        while True:
            try:
                raw_bytes, _ = self.udp_socket.recvfrom(self.BUFFER_SIZE)
            except socket.timeout:
                continue
            segment = self.parse_segment(raw_bytes)
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
                ack_segment = self.create_segment({
                    "seq": segment["seq"] + 1,
                    "ack": True,
                    "syn": False,
                    "fin": False,
                    "data": b""
                })
                self.udp_socket.sendto(ack_segment, self.dest_address)

    def send(self, message):
        self._send_and_wait_ack(str(len(message)).encode())
        for i in range(0, len(message), self.MAX_PAYLOAD):
            self._send_and_wait_ack(message[i:i+self.MAX_PAYLOAD])

    def recv(self, buff_size):
        if self.remaining == 0 and not self.recv_buffer:
            self.remaining = int(self._recv_segment().decode())

        while len(self.recv_buffer) < buff_size and self.remaining > 0:
            data = self._recv_segment()
            self.recv_buffer += data
            self.remaining -= len(data)

        result = self.recv_buffer[:buff_size]
        self.recv_buffer = self.recv_buffer[buff_size:]
        return result