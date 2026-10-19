import random
import socket
import sys

from CongestionControl import CongestionControl
from slidingWindowCC import SlidingWindowCC
from socketUDP import SocketUDP

class SocketTCP:
    HEADER_SIZE = 7
    MAX_PAYLOAD = 16
    BUFFER_SIZE = HEADER_SIZE + MAX_PAYLOAD

    # Go-Back-N: segment data size and window size without congestion control
    MSS = 8
    GO_BACK_N_WINDOW_SIZE = 8

    # When True, prints how losses are being handled (to stderr)
    DEBUG = False
    # When True, prints how the congestion window evolves (to stderr)
    DEBUG_CC = False

    def __init__(self):
        # Go-Back-N uses SocketUDP's timers. The handshake, close and Stop & Wait
        # keep using the plain socket with settimeout. Both share the same UDP
        # socket, so the connection keeps a single port
        self.socketUDP = SocketUDP()
        self.udp_socket = self.socketUDP.socket_udp
        self.settimeout(1.0)

        self.dest_address = None
        self.bind_address = None

        self.seq_num = random.randint(0, 100)

        self.remaining = 0
        self.recv_buffer = b""

        # When True, Go-Back-N sizes its window with a CongestionControl object
        self.congestion_control_on = True

        # Data segments sent by send, retransmissions included
        self.number_of_sent_segments = 0

    def set_congestion_control_on(self, congestion_control_on):
        self.congestion_control_on = congestion_control_on

    def settimeout(self, timeout):
        """Sets the timeout of both the plain socket and SocketUDP's timers."""
        self.timeout = timeout
        self.socketUDP.settimeout(timeout)
        self.udp_socket.settimeout(timeout)

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

    def _debug_cc(self, event, congestion_controler, window_size):
        """
        Prints the congestion control variables after event, only when the
        congestion control debug mode is on.
        """
        if SocketTCP.DEBUG_CC:
            print(f"[CC] {event} | {congestion_controler.current_state} | cwnd={congestion_controler.get_cwnd()} B "
                  f"({congestion_controler.get_MSS_in_cwnd()} MSS) | ssthresh={congestion_controler.get_ssthresh()} "
                  f"| window_size={window_size}", file=sys.stderr, flush=True)

    def _send_ack(self, seq):
        """Sends an ACK segment carrying seq, without starting any SocketUDP timer."""
        ack_segment = self.create_segment({
            "seq": seq,
            "ack": True,
            "syn": False,
            "fin": False,
            "data": b""
        })
        self.udp_socket.sendto(ack_segment, self.dest_address)

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
                    new_socket.settimeout(self.timeout)
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
                    self._send_ack(self.seq_num)
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
        self.number_of_sent_segments += 1

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
                    self._send_ack(ack_segment["seq"] + 1)
            except socket.timeout:
                self._debug(f"send: timeout waiting for ACK of seq={self.seq_num}, retransmitting")
                self.udp_socket.sendto(segment, self.dest_address)
                self.number_of_sent_segments += 1

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
                self._send_ack(self.seq_num + 1)
                self.seq_num += 1
                return segment["data"]
            elif segment["seq"] < self.seq_num:
                self._debug(f"recv: duplicate segment seq={segment['seq']} (its ACK was lost), resending ACK")
                self._send_ack(segment["seq"] + 1)

    def _send_window(self, data_window, first_index, window_size):
        """
        Sends the segments of the window from first_index on. It stops at the
        first empty element: they are only at the end, once data_list runs out.
        SocketUDP starts timer 0 if it is not already running, so a single
        timer covers the whole window.
        """
        for i in range(first_index, window_size):
            data = data_window.get_data(i)
            if data is None:
                break
            segment = self.create_segment({
                "seq": data_window.get_sequence_number(i),
                "ack": False,
                "syn": False,
                "fin": False,
                "data": data
            })
            self.socketUDP.sendto(segment, self.dest_address, timer_index=0)
            self.number_of_sent_segments += 1

    @staticmethod
    def _acked_steps(data_window, window_size, ack_seq):
        """
        Returns how many elements of the window ack_seq acknowledges (cumulative
        ACK carrying the next expected byte), or 0 if it acknowledges none.
        """
        for i in range(window_size):
            data = data_window.get_data(i)
            if data is None:
                break
            if data_window.get_sequence_number(i) + len(data) == ack_seq:
                return i + 1
        return 0

    @staticmethod
    def _is_beyond_window(data_window, window_size, ack_seq):
        """
        True if ack_seq acknowledges segments past the last one in the window.
        It happens when the window shrinks after those segments were sent.
        """
        last_data = data_window.get_data(window_size - 1)
        if last_data is None:
            return False
        return ack_seq > data_window.get_sequence_number(window_size - 1) + len(last_data)

    def _recv_segment_go_back_n(self):
        """
        Receives the next in-order data segment using Go-Back-N, ACKs it and
        returns its data. ACKs are cumulative and carry the next expected byte.
        Out of order segments (a previous one was lost) and duplicated ones
        (their ACK was lost) are discarded, answering with the last ACK again.
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
                self.seq_num += len(segment["data"])
                self._send_ack(self.seq_num)
                return segment["data"]
            elif segment["seq"] > self.seq_num:
                self._debug(f"recv: out of order segment seq={segment['seq']} (expected {self.seq_num}), discarding it and resending ACK")
            else:
                self._debug(f"recv: duplicate segment seq={segment['seq']} (its ACK was lost), resending ACK")
            self._send_ack(self.seq_num)

    def send(self, message, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    def recv(self, buff_size, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    def send_using_stop_and_wait(self, message):
        """
        Sends message using Stop & Wait. The first segment carries the message
        length, the following ones carry the message in chunks of MAX_PAYLOAD bytes.
        """
        self._send_and_wait_ack(str(len(message)).encode())
        for i in range(0, len(message), self.MAX_PAYLOAD):
            self._send_and_wait_ack(message[i:i+self.MAX_PAYLOAD])

    def recv_using_stop_and_wait(self, buff_size):
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

    def send_using_go_back_n(self, message):
        """
        Sends message using Go-Back-N. As in Stop & Wait, the first segment
        carries the message length, the following ones carry chunks of MSS
        bytes. A single timer covers the window: on timeout every segment in
        the window is resent. Each ACK moves the window up to the segment it
        acknowledges and the segments that enter the window are sent.

        With congestion_control_on, the window size is the number of MSS that
        fit in cwnd and is updated after every new ACK and every timeout
        (TCP Tahoe: slow start and congestion avoidance). Otherwise it stays
        at GO_BACK_N_WINDOW_SIZE segments.
        """
        message_length = str(len(message)).encode()
        data_list = [message_length] + [message[i:i+self.MSS] for i in range(0, len(message), self.MSS)]

        congestion_controler = CongestionControl(self.MSS)
        if self.congestion_control_on:
            window_size = congestion_controler.get_MSS_in_cwnd()
            self._debug_cc("start", congestion_controler, window_size)
        else:
            window_size = self.GO_BACK_N_WINDOW_SIZE
        data_window = SlidingWindowCC(window_size, data_list, self.seq_num)

        # SocketUDP.recvfrom polls the socket, so it needs it in non-blocking mode.
        # The timeout used by the rest of the class is restored at the end
        self.udp_socket.setblocking(False)
        self._send_window(data_window, 0, window_size)

        while data_window.get_data(0) is not None:
            try:
                raw_bytes, _ = self.socketUDP.recvfrom(self.BUFFER_SIZE)
            except TimeoutError:
                self._debug(f"send: timeout waiting for ACK of seq={data_window.get_sequence_number(0)}, resending the window")
                # an expired Timer cannot be restarted, it has to be stopped before resending
                self.socketUDP.stop_timer(timer_index=0)
                if self.congestion_control_on:
                    congestion_controler.event_timeout()
                    window_size = congestion_controler.get_MSS_in_cwnd()
                    data_window.update_window_size(window_size)
                    self._debug_cc("timeout", congestion_controler, window_size)
                self._send_window(data_window, 0, window_size)
                continue

            segment = self.parse_segment(raw_bytes)
            if segment["syn"] or segment["fin"]:
                continue
            if not segment["ack"]:
                if segment["seq"] < self.seq_num:
                    # resend ACK for a previous segment of the other side
                    self._debug(f"send: duplicate segment seq={segment['seq']} received, resending its ACK")
                    self._send_ack(segment["seq"] + len(segment["data"]))
                continue

            # Edge case: if the window shrank after its segments were sent, the
            # ACK can fall past the window. The whole window is moved, as if
            # its last segment had been acknowledged, until the ACK falls inside
            moved = 0
            while self._is_beyond_window(data_window, window_size, segment["seq"]):
                self._debug(f"send: ACK seq={segment['seq']} past the window, moving the whole window")
                data_window.move_window(window_size)
                moved += window_size

            steps = self._acked_steps(data_window, window_size, segment["seq"])
            if steps == 0:
                self._debug(f"send: duplicate ACK seq={segment['seq']} ignored")
                continue

            self.seq_num = segment["seq"]
            data_window.move_window(steps)
            moved += steps

            # The elements already in the window were sent, the ones that
            # entered it (by moving or by growing) are sent now
            first_new_index = max(0, window_size - moved)
            if self.congestion_control_on:
                congestion_controler.event_ack_received()
                window_size = congestion_controler.get_MSS_in_cwnd()
                data_window.update_window_size(window_size)
                self._debug_cc(f"ACK seq={segment['seq']}", congestion_controler, window_size)

            # The timer is restarted by sending. If there is nothing new to send,
            # it keeps running for the segments still in the window
            if data_window.get_data(first_new_index) is not None or data_window.get_data(0) is None:
                self.socketUDP.stop_timer(timer_index=0)
            self._send_window(data_window, first_new_index, window_size)

        self.udp_socket.settimeout(self.timeout)

    def recv_using_go_back_n(self, buff_size):
        """
        Same as recv_using_stop_and_wait, but each segment is received with
        Go-Back-N. The receiver needs neither timers nor a sliding window: it
        only accepts the next in-order segment.
        """
        if self.remaining == 0 and not self.recv_buffer:
            self.remaining = int(self._recv_segment_go_back_n().decode())

        while len(self.recv_buffer) < buff_size and self.remaining > 0:
            data = self._recv_segment_go_back_n()
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

                    # Send the final ACK 3 times, waiting a timeout between sends
                    for i in range(3):
                        self._debug(f"close: sending final ACK ({i + 1}/3)")
                        self._send_ack(self.seq_num)
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
                # seq_num is the last ACK sent: seq + 1 in Stop & Wait, the next
                # expected byte in Go-Back-N
                self._send_ack(self.seq_num)
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