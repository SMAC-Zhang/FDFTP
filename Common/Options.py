# this file defines some constants

import socket

# the size socket receives
BUF_SIZE = 1024 + 24

# socket buffer size
SEND_BUF_SIZE = 1024 * 64 # 64Bytes
RECV_BUF_SIZE = 1024 * 64 # 64Bytes

# for socket time out
TIME_OUT = 5

# read from file once
FILE_SIZE = 1024

# for congestion avoidance
CWND_THRESHOLD = 64
CWND_LOW_LIMIT = 8
RWND = 128
ESTIMATED_RTT = 0.2

# for RTT computation
ALPHA = 0.125

# IP and PORT
SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 45678
CLIENT_PORT = 12345

# for multiThread
DEFAULT_NUM_THREADS = 2
MAX_NUM_THREADS = 8