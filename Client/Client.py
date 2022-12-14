import socket
import sys
import threading
import os
import time
from queue import Queue

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Utils.FDFTPsocket import Task
from Utils.FTPStruct import *
from Utils.CheckSum import *
from Utils.MD5 import *
from Common.Options import *
from Common.Receiver import Receiver
from Common.Sender import Sender

class Client():
    def __init__(self, addr, server_addr):
        #create a socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(addr)
        # set BUF size
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUF_SIZE)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE)
        self.server_addr = server_addr

        self.resend_buffer = []

        # for multithread
        self.num_thread = DEFAULT_NUM_THREADS
        self.thread_socket = []
        self.socket_port = []
        self.thread_array = []

        # for file
        self.inst = ''
        self.file_name = ''
        self.file_buf = Queue()
        self.task = None

    def run(self):
        while True:
            self.reset()
           
            # parse_cmd
            if self.parse_cmd() is False:
                continue
            if self.inst == 'exit':
                break
            
            self.prepare()
            try:
                self.send_cmd()
            except Exception as e:
                continue
            
            # start task
            try:
                if self.inst == 'download':
                    self.download()
                else:
                    self.upload()
            except Exception as e:
                print(e)

        self.s.close()
    
    def parse_cmd(self) -> bool:
        cmd = input("please enter your command:")
        args = cmd.split(' ')
        if args[0] == 'exit':
            self.inst = 'exit'
            return True
        if args[0] != 'download' and args[0] != 'upload':
            print('illegal instruction')
            return False

        # upload
        if args[0] == 'upload': 
            if len(args) != 2:
                print('illegal instruction')
                return False
            else:
                self.inst = 'upload'
                self.file_name = args[1]
                self.num_thread = 1
            if os.path.exists(self.file_name) is False:
                print('File Not Exist')
                return False
            else:
                return True
        
        # download
        if args[0] == 'download':
            if len(args) != 2 and len(args) != 3:
                print('illegal instruction')
                return False
            self.inst = args[0]
            self.file_name = args[1]
            if len(args) == 3:
                try:
                    self.num_thread = int(args[2])
                    if (self.num_thread > MAX_NUM_THREADS):
                        print('too many threads')
                        return False
                    if (self.num_thread < 1):
                        print('at least one thread')
                        return False
                except Exception:
                    print('illegal instruction')
                    return False
        return True

    def prepare(self):
        if self.inst == 'download':
            for i in range(self.num_thread):
                ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                ss.bind((CLIENT_IP, 0))
                ss.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE)
                ss.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE)
                self.thread_socket.append(ss)
                self.socket_port.append(ss.getsockname()[1])
        else:
            #prepare file buffer
            f = open(self.file_name, 'rb')
            size = os.path.getsize(self.file_name)
            data = f.read()
            f.close()
            p = 0
            while p < size:
                end = p + FILE_SIZE
                if end > size:
                    end = size
                self.file_buf.put(data[p : end])
                p += FILE_SIZE

    def send_cmd(self):
        # send instruction
        data = self.inst + ' ' + self.file_name + ' '
        if self.inst == 'download':
            for i in range(self.num_thread):
                data += str(self.socket_port[i]) + ' '
        data = data.encode('utf-8')
        checksum = generate_checksum(struct.pack('iii?1024s', *(-1, -1, self.num_thread, False, data)))
        send_pack = DataStruct(-1, -1, self.num_thread, False, data, checksum)
        self.s.sendto(send_pack.pack(), self.server_addr)
        timer = threading.Timer(2 * ESTIMATED_RTT, self.timeout_handler)
        self.resend_buffer = [send_pack, timer]
        timer.start()

        # recv Ready
        while True:
            self.s.settimeout(TIME_OUT)
            try:
                data, addr = self.s.recvfrom(BUF_SIZE)
            except Exception:
                print('send cmd timeout! please try again')
                raise TimeoutError
            recv_pack = DataStruct.unpack(data)
            isok: bool = check_checksum(struct.pack('iii?1024s', *(recv_pack.seq, recv_pack.ack, recv_pack.length, recv_pack.final_flag, recv_pack.data)), recv_pack.checksum)
            if isok is False:
                print("checksum error!")
                continue
            data = recv_pack.data.strip(b'\x00')
            data = data.decode('utf-8')
            if recv_pack.seq == -1 and recv_pack.ack == -1 and data == 'Ready':
                self.resend_buffer[1].cancel()
                self.resend_buffer = []
                print('Ready, begin to ' + self.inst)
                break
    
    def download(self):
        for i in range(self.num_thread):
            thread = Receiver(self.server_addr, self.file_name + '_' + str(i), self.thread_socket[i], None, False)
            self.thread_array.append(thread)
        
        for i in range(self.num_thread):
            self.thread_array[i].start()

        for i in range(self.num_thread):
            self.thread_array[i].join()

        for i in range(self.num_thread):
            self.thread_socket[i].close()

        self.make_file()
        try:
            if self.check_md5() is False:
                print('file seems error. retransmission may be required...')
            else:
                print('successfully!')
        except TimeoutError:
            raise Exception('check md5 timeout, the file may not be right!')

    def upload(self):
        self.task = Task(self.file_name)
        upload_thread = Sender(self.server_addr, self.task, self.file_buf, self.s, None, False)
        upload_thread.start()
        upload_thread.join()
        self.task.finish()
        print(self.inst + ' ' + self.file_name + ' ' + 'successfully!')
        time.sleep(2)
        # send md5 to check
        md5 = get_md5(self.file_name)
        md5 = md5.encode('utf-8')
        checksum = generate_checksum(struct.pack('iii?1024s', *(-2, -2, -2, False, md5)))
        send_pack = DataStruct(-2, -2, -2, False, md5, checksum)
        self.s.sendto(send_pack.pack(), self.server_addr)

    def make_file(self):
        print('download finished, checking file...')

        file = open(self.file_name + '_' + str(0), 'ab')
        for i in range(1, self.num_thread):
            rfile = open(self.file_name + '_' + str(i), 'rb')
            data = rfile.read()
            file.write(data)
            rfile.close()
            os.remove(self.file_name + '_' + str(i))
        file.close()

        if os.path.exists(self.file_name) is True:
            os.remove(self.file_name)
        os.rename(self.file_name + '_' + str(0), self.file_name)     

    def check_md5(self) -> bool:
        # recv md5
        while True:
            self.s.settimeout(TIME_OUT)
            try:
                data, addr = self.s.recvfrom(BUF_SIZE)
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
        timer = threading.Timer(2 * ESTIMATED_RTT, self.timeout_handler)
        self.s.sendto(self.resend_buffer[0].pack(), self.server_addr)
        self.resend_buffer[1] = timer
        timer.start()

    def reset(self):
        if len(self.resend_buffer) > 0:
            self.resend_buffer[1].cancel()
            self.resend_buffer = []

        # for multithread
        self.num_thread = DEFAULT_NUM_THREADS
        self.thread_socket = []
        self.socket_port = []
        self.thread_array = []

        # for file
        self.inst = ''
        self.file_name = ''
        self.task = None
        self.file_buf = Queue()

if __name__ == "__main__":
    myclient = Client((CLIENT_IP, 0), (SERVER_IP, SERVER_PORT))
    try:
        myclient.run()
    except KeyboardInterrupt:
        exit(0)