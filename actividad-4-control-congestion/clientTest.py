import sys
import time
import SocketTCP

# Usage: python3 clientTest.py [--gbn]
mode = "go_back_n" if "--gbn" in sys.argv[1:] else "stop_and_wait"
address = ("127.0.0.1", 8080)

# CLIENT
client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)
# test 1
message = "Mensje de len=16".encode()
client_socketTCP.send(message, mode)
# test 2
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode)
# test 3
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode)
# close
start = time.time()
client_socketTCP.close()
print(f"close finished in {time.time() - start:.2f}s")
if client_socketTCP.udp_socket.fileno() == -1: print("Close: Passed")
else: print("Close: Failed")