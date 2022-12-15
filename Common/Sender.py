import threading
import sys
import time
import socket
import struct
import os
from queue import Queue

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Common.Options import *
from Utils.FDFTPsocket import Task
from Utils.FTPStruct import *
from Utils.CheckSum import *

class Sender(threading.Thread):
    def __init__(self, recv_addr, task: Task, file_buf: Queue, s:socket, socket_buf: Queue, is_server: bool):
        threading.Thread.__init__(self)
        # for SR
        self.seq = 0
        self.window = []
        self.send_base = 0
        
        # for congestion avoid 
        self.cwnd = 1
        self.RTT = ESTIMATED_RTT
        self.firstRTT = True
        self.ssthresh = CWND_THRESHOLD

        # for concurrency safety
        self.lock = threading.Lock()

        # for socket
        self.is_server = is_server
        self.s = s
        self.task = task
        self.recv_addr = recv_addr
        self.socket_buf = socket_buf

        # file buffer
        self.file_buf = file_buf
    
    def run(self):
        if self.recv_ready() is False:
            print('Failed connection')
            return
        try:
            self.send_file()
        except TimeoutError:
            print('recv ack timeout!!!')
            return

    def send(self, data):
        self.task.sendto(self.s, data, self.recv_addr)

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

    def recv_ready(self) -> bool:
        while True:
            try:
                data = self.recv()
            except TimeoutError:
                print('recv_ready timeout')
                return False
            if len(data) != ACK_LEN:
                continue
            # check
            recv_pack: AckStruct = AckStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('ii', *(recv_pack.port, recv_pack.ack)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            if recv_pack.ack == -1:
                if self.is_server:
                    self.recv_addr = (self.recv_addr[0], recv_pack.port)
                return True

    def send_file(self):
        self.end_flag = False
        fwnd = 0
        while True:
            self.lock.acquire()
            cnt = max(0, int(self.cwnd - fwnd))
            while cnt > 0 and self.end_flag is False:
                cnt -= 1
                fwnd += 1
                if self.file_buf.qsize() > 1:
                    data = self.file_buf.get()
                    checksum = generate_checksum(struct.pack('iii?1024s', *(self.seq, 0, len(data), False, data)))
                    send_pack = DataStruct(self.seq, 0, len(data), False, data, checksum)
                    self.send(send_pack.pack())
                    timer = threading.Timer(1.5 * self.RTT, self.timeout_handler, (self.seq,))
                    self.window.append([send_pack, timer, False, time.time()])
                    self.seq += 1
                    timer.start()
                else:
                    data = self.file_buf.get()
                    checksum = generate_checksum(struct.pack('iii?1024s', *(self.seq, 0, len(data), True, data)))
                    send_pack = DataStruct(self.seq, 0, len(data), True, data, checksum)
                    self.send(send_pack.pack())
                    timer = threading.Timer(1.5 * self.RTT, self.timeout_handler, (self.seq,))
                    self.window.append([send_pack, timer, False, time.time()])
                    self.seq += 1
                    self.end_flag = True
                    timer.start()
                    break
            self.lock.release()

            # recv ack
            while True:
                try:
                    data = self.recv()
                except TimeoutError:
                    raise TimeoutError
                if len(data) == ACK_LEN:
                    break
            # check
            recv_pack: AckStruct = AckStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('ii', *(recv_pack.port, recv_pack.ack)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            
            ack = recv_pack.ack
            self.lock.acquire()
            if self.send_base <= ack and ack < self.seq:
                idx = ack - self.send_base
                if self.window[idx][2] != True:
                    # window increase
                    fwnd -= 1
                    if self.cwnd < self.ssthresh:
                        self.cwnd += 1
                    else:
                        self.cwnd += 1.0 / int(self.cwnd)
                    # compute RTT
                    if self.window[idx][3] > 0:
                        sample_RTT = time.time() - self.window[idx][3]
                        if sample_RTT > 0:
                            if self.firstRTT:
                                self.RTT = sample_RTT
                                self.firstRTT = False
                            else:
                                self.RTT = (1 - ALPHA) * self.RTT + ALPHA * sample_RTT

                self.window[idx][1].cancel()
                self.window[idx][2] = True

            # window slides
            while True:
                if len(self.window) > 0 and self.window[0][2] is True:
                    self.window.pop(0)
                    self.send_base += 1
                else:
                    break
                
            if len(self.window) == 0 and self.end_flag == True:
                self.lock.release()
                break
            self.lock.release()

    def timeout_handler(self, seq):
        self.lock.acquire()
        idx = seq - self.send_base
        if idx < 0:
            self.lock.release()
            return
        timer = threading.Timer(1.5 * self.RTT, self.timeout_handler, (seq,))
        self.send(self.window[idx][0].pack())
        self.window[idx][1] = timer
        self.window[idx][2] = False
        self.window[idx][3] = -1
        self.ssthresh = self.cwnd / 2
        if self.ssthresh < CWND_LOW_LIMIT:
            self.ssthresh = CWND_LOW_LIMIT
        self.cwnd = 1
        timer.start()
        self.lock.release()