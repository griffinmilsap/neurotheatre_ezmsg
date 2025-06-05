import socket
import json

from ezmsg.util.messagecodec import MessageDecoder

# Configuration
udp_ip = "0.0.0.0"   # Listen on all interfaces
udp_port = 9001     # Port to listen on

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the address and port
sock.bind((udp_ip, udp_port))

print(f"Listening on UDP port {udp_port}...")

while True:
    data, addr = sock.recvfrom(4096)  # Buffer size is 1024 bytes
    print(f"Received message from {addr}: {json.loads(data.decode(), cls = MessageDecoder)}")