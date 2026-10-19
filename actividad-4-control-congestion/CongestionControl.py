class CongestionControl:
    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"

    def __init__(self, MSS: int):
        self.MSS = MSS
        self.current_state = CongestionControl.SLOW_START
        self.cwnd = MSS

        # Undefined until the first timeout
        self.ssthresh = None

        # ACKs received in congestion avoidance since cwnd last grew
        self.acks_in_cwnd = 0

    def get_cwnd(self) -> int:
        """
        Returns the congestion window size in bytes.
        """
        return self.cwnd

    def get_MSS_in_cwnd(self) -> int:
        """
        Returns how many complete MSS fit inside the congestion window.
        """
        return self.cwnd // self.MSS

    def get_ssthresh(self):
        return self.ssthresh

    def is_state_slow_start(self) -> bool:
        return self.current_state == CongestionControl.SLOW_START

    def is_state_congestion_avoidance(self) -> bool:
        return self.current_state == CongestionControl.CONGESTION_AVOIDANCE

    def event_ack_received(self):
        """
        Grows cwnd on a successful ACK: 1 MSS per ACK in slow start, and in
        congestion avoidance 1/MSS_in_cwnd of an MSS per ACK, applied as
        1 MSS once as many ACKs as MSS fit in cwnd have arrived.
        """
        if self.is_state_slow_start():
            self.cwnd += self.MSS
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = CongestionControl.CONGESTION_AVOIDANCE
                self.acks_in_cwnd = 0

        elif self.is_state_congestion_avoidance():
            self.acks_in_cwnd += 1
            if self.acks_in_cwnd == self.get_MSS_in_cwnd():
                self.cwnd += self.MSS
                self.acks_in_cwnd = 0

    def event_timeout(self):
        """
        Multiplicative decrease: ssthresh = cwnd/2, cwnd = 1 MSS and back
        to slow start, regardless of the current state.
        """
        self.ssthresh = self.cwnd // 2
        self.cwnd = self.MSS
        self.current_state = CongestionControl.SLOW_START
