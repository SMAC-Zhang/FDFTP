import threading
import sys
import socket
import struct
import os
from queue import Queue

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Common.Options import *
from Utils.FTPStruct import *
from Utils.CheckSum import *

class Receiver(threading.Thread):
    def __init__(self, send_addr, file_name, s: socket, socket_buf: Queue, is_server: bool):
        threading.Thread.__init__(self)

        # for SR
        self.ack = 0
        self.window = []
        self.rwnd = RWND
        self.recv_base = 0

        # for file
        self.file = open(file_name, 'wb')
        self.file_name = file_name

        # for socket
        self.is_server = is_server
        self.s:socket = s
        self.socket_buf = socket_buf
        self.send_addr = send_addr
        self.resend_buffer = []

    def run(self):
        self.send_ready()
        self.recv_file()

        if len(self.resend_buffer) > 0:
            self.resend_buffer[1].cancel()
    
    def send_ready(self):
        data = 'Ready'.encode('utf-8')
        checksum = generate_checksum(struct.pack('iii?1024s', *(-1, -1, -1, False, data)))
        send_pack = DataStruct(-1, -1, -1, False, data, checksum)
        self.send(send_pack.pack())
        timer = threading.Timer(2 * ESTIMATED_RTT, self.timeout_handler)
        self.resend_buffer = [send_pack, timer]
        timer.start()

    def send(self, data):
        self.s.sendto(data, self.send_addr)

    def recv(self, timeout = TIME_OUT) -> bytes:
        if self.is_server is False:
            self.s.settimeout(timeout)
            try:
                data, addr = self.s.recvfrom(BUF_SIZE)
            except Exception:
                raise TimeoutError
            return data

        try:
            data = self.socket_buf.get(timeout = timeout)
        except Exception:
            raise TimeoutError
        
        return data

    def recv_file(self):
        #init receive window
        for i in range(self.rwnd):
            self.window.append(None)
        end_seq = -999
        out = False

        while True:
            try:
                data = self.recv(timeout = 2)
            except Exception:
                if end_seq + 1 == self.recv_base:
                    break
                else:
                    print('recv Timeout!')
                    self.file.close()
                    return

            # check
            recv_pack: DataStruct = DataStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('iii?1024s', *(recv_pack.seq, recv_pack.ack, recv_pack.length, recv_pack.final_flag, recv_pack.data)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            if len(self.resend_buffer) > 0:
                self.resend_buffer[1].cancel()
                self.resend_buffer = []
            # recv data
            idx = recv_pack.seq - self.recv_base
            if idx >= 0 and idx < self.rwnd:
                if self.window[idx] == None:
                    self.window[idx] = recv_pack
                    self.rwnd -= 1
                if recv_pack.final_flag == True:
                    end_seq = recv_pack.seq
            if idx < self.rwnd:
                # send ack 
                data = ''.encode('utf-8')
                checksum = generate_checksum(struct.pack('iii?1024s', *(0, recv_pack.seq, self.rwnd, False, data)))
                send_pack = DataStruct(0, recv_pack.seq, self.rwnd, False, data, checksum)
                self.send(send_pack.pack())

            # window slides
            while True:
                if self.window[0] != None:
                    data = self.window[0].data
                    length = self.window[0].length
                    self.file.write(data[0 : length])
                    self.rwnd += 1
                    self.window.pop(0)
                    self.window.append(None)
                    self.recv_base += 1
                else:
                    break
            
            if end_seq + 1 == self.recv_base:
                if self.is_server is False and out is False:
                    id = self.file_name.split('_')[-1]
                    print('thread ' + id + ' download finished!')
                    out = True
                self.file.close()

    def timeout_handler(self):
        timer = threading.Timer(2 * ESTIMATED_RTT, self.timeout_handler)
        self.send(self.resend_buffer[0].pack())
        self.resend_buffer[1] = timer
        timer.start()