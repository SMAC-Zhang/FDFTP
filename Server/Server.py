import threading
import socket
import sys
import os
from queue import Queue
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Utils.FDFTPsocket import Task
from Utils.FTPStruct import *
from Utils.CheckSum import *
from Utils.MD5 import *
from Common.Options import *
from Common.Receiver import Receiver
from Common.Sender import Sender

class Server():
    def __init__(self, address):
        #create a socket
        self.s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.s.bind(address)
        # set BUF size
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUF_SIZE)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE)

        # for multiThread!!!
        # socket_buf is a dictionary,
        # which contains a key with type: tuple(ip, port)
        # and a value with type: Queue
        # should it be protected by a lock? Or it's operation is atomic
        self.socket_buf: dict(tuple, Queue) = {}

    def add_to_buffer(self, data, client_addr):
        # add data received from socket to the buffer
        if client_addr in self.socket_buf:
            self.socket_buf[client_addr].put(data)
        else:
            self.socket_buf[client_addr] = Queue()
            self.socket_buf[client_addr].put(data)
            thread = ServerThread(client_addr)
            print("connect with " + str(client_addr))
            thread.start()
    
    def recv_from_buffer(self, client_addr, timeout = TIME_OUT) -> bytes:
        # thread get data from responding buffer
        buffer: Queue = self.socket_buf[client_addr]    
        try:
            data = buffer.get(timeout = timeout)
        except Exception:
            raise TimeoutError

        return data

    def remove_from_buffer(self, client_addr):
        self.socket_buf.pop(client_addr)

    def run(self):
        while True:
            data, client_addr = self.s.recvfrom(BUF_SIZE)
            self.add_to_buffer(data, client_addr)

class ServerThread(threading.Thread):
    def __init__(self, client_addr):
        threading.Thread.__init__(self)
        self.client_addr = client_addr
        self.inst = ''
        self.task = None
        self.file_name = ''

        # for multithread
        self.socket_addr = []
        self.thread_array = []
        self.num_thread = 0
        self.file_buf = []

    def recv(self, timeout = TIME_OUT):
        global myserver
        try:
            data = myserver.recv_from_buffer(self.client_addr, timeout)
            return data
        except Exception:
            raise TimeoutError

    def send(self, data):
        global myserver
        myserver.s.sendto(data, self.client_addr)

    # the entry function of the server thread
    def run(self):
        try:
            self.process_cmd()
        except Exception as e:
            print(e)
            self.reset()
            return
        
        try:
            if self.inst == 'download':
                self.download()
            elif self.inst == 'upload':
                self.upload()
            else:
                print('illegal instruction')
                self.reset()
                return
        except TimeoutError:
            print('Time out!')
            self.reset()
            return
        except Exception as e:
            print(e)
            self.reset()
            return
        
        self.reset()

    def process_cmd(self):
        # recv cmd
        while True:
            try:
                data = self.recv()
            except TimeoutError:
                raise Exception("timeout")

            recv_pack: DataStruct = DataStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('iii?1024s', *(recv_pack.seq, recv_pack.ack, recv_pack.length, recv_pack.final_flag, recv_pack.data)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            break
        
        # parse cmd
        data = recv_pack.data.strip(b'\x00').decode('utf-8')
        args = data.split(' ')
        if args[0] == 'download':
            self.inst = 'download'
            self.file_name = args[1]
            if os.path.exists(self.file_name) is False:
                raise Exception("File Not Exist")
            self.num_thread = recv_pack.length
            ip = self.client_addr[0]
            for i in range(self.num_thread):
                port = int(args[i + 2])
                self.socket_addr.append((ip, port))
            print(str(self.client_addr) + " download " + self.file_name + ' using threads: ' + str(self.num_thread))

        elif args[0] == 'upload':
            self.file_name = args[1]
            self.inst = 'upload'
            print(str(self.client_addr) + " upload " + self.file_name)
        
        else:
            raise Exception("illegal instruction")

    def prepare(self):
        if self.inst == 'download':
            # prepare socket buffer
            global myserver
            for i in range(self.num_thread):
                myserver.socket_buf[self.socket_addr[i]] = Queue()
            
            #prepare file buffer
            f = open(self.file_name, 'rb')
            size = os.path.getsize(self.file_name)
            average_size = int(size / self.num_thread)
            left_size = size - self.num_thread * average_size

            for i in range(self.num_thread):
                if i == 0:
                    sz = average_size + left_size
                else:
                    sz = average_size
                data = f.read(sz)
                self.file_buf.append(Queue())
                p = 0
                while p < sz:
                    end = p + FILE_SIZE
                    if end > sz:
                        end = sz
                    self.file_buf[i].put(data[p : end])
                    p += FILE_SIZE
            f.close()

    def download(self):
        self.prepare()
        global myserver

        data = 'Ready'.encode('utf-8')
        checksum = generate_checksum(struct.pack('iii?1024s', *(-1, -1, -1, False, data)))
        send_pack = DataStruct(-1, -1, -1, False, data, checksum)
        self.send(send_pack.pack())
        time.sleep(0.1)
        self.task = Task(self.file_name)

        for i in range(self.num_thread):
            thread = Sender(self.socket_addr[i], self.task, self.file_buf[i], myserver.s, myserver.socket_buf[self.socket_addr[i]], True)
            self.thread_array.append(thread)

        for i in range(self.num_thread):
            self.thread_array[i].start()
        
        for i in range(self.num_thread):
            self.thread_array[i].join()

        self.task.finish()
        print(str(self.client_addr) + ' ' + self.inst + ' ' + self.file_name + ' successfully!')
        # send md5 to check
        md5 = get_md5(self.file_name)
        md5 = md5.encode('utf-8')
        checksum = generate_checksum(struct.pack('iii?1024s', *(-2, -2, -2, False, md5)))
        send_pack = DataStruct(-2, -2, -2, False, md5, checksum)
        self.send(send_pack.pack())

    def upload(self):
        global myserver
        thread = Receiver(self.client_addr, self.file_name, myserver.s, myserver.socket_buf[self.client_addr], True)
        thread.start()
        thread.join()
        try:
            if self.check_md5() is False:
                print('file seems error. retransmission may be required...')
            else:
                print(str(self.client_addr) + ' ' + self.inst + ' ' + self.file_name + ' successfully!')
        except TimeoutError:
            raise Exception('check md5 timeout, the file may not be right!')

    def check_md5(self) -> bool:
        # recv md5
        while True:
            try:
                data, addr = self.recv()
            except Exception:
                raise TimeoutError
            recv_pack = DataStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('iii?1024s', *(recv_pack.seq, recv_pack.ack, recv_pack.length, recv_pack.final_flag, recv_pack.data)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            data = recv_pack.data.strip(b'\x00')
            data = data.decode('utf-8')
            if recv_pack.seq != -2:
                continue
            if data != get_md5(self.file_name):
                return False
            return True

    def timeout_handler(self):
        timer = threading.Timer(1.5 * ESTIMATED_RTT, self.timeout_handler)
        self.send(self.resend_buffer[0].pack())
        self.resend_buffer[1] = timer
        timer.start()

    def reset(self):
        global myserver
        for i in range(self.num_thread):
            myserver.remove_from_buffer(self.socket_addr[i])
        myserver.remove_from_buffer(self.client_addr)
        print("disconnect with " + str(self.client_addr))

if __name__ == '__main__':
    global myserver
    myserver = Server((SERVER_IP, SERVER_PORT))
    try:
        myserver.run()
    except KeyboardInterrupt:
        exit(0)