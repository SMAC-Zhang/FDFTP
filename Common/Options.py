# this file defines some constants

import socket

# the size socket receives
BUF_SIZE = 1024 + 24

# socket buffer size
SEND_BUF_SIZE = 1024 * 1024 # 1MBytes
RECV_BUF_SIZE = 1024 * 1024 # 1MBytes

# for socket time out
TIME_OUT = 5

# read from file once
FILE_SIZE = 1024

# for congestion avoidance
CWND_THRESHOLD = 1024
CWND_LOW_LIMIT = 16
RWND = 2048
ESTIMATED_RTT = 0.2

# for RTT computation
ALPHA = 0.125

# IP and PORT
# you should change them depends on your environment
# e.g. CLIENT_IP = '127.0.0.1'
#      SERVER_IP = '127.0.0.1'
CLIENT_IP = socket.gethostbyname(socket.gethostname())
SERVER_IP = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 45678

# for multiThread
DEFAULT_NUM_THREADS = 8
MAX_NUM_THREADS = 16