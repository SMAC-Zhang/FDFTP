import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Common.Options import *

class Task():
    def __init__(self, file_path):
        self.start_time = time.time()
        self.file_size = os.path.getsize(file_path)
        self.byte_count = 0
        self.pack_count = 0
        self.pack_size = int(self.file_size / FILE_SIZE) + 1

    def sendto(self, s, data, addr):
        self.byte_count += len(data)
        s.sendto(data, addr)
        self.pack_count += 1
        
    def finish(self):
        time_consume = time.time() - self.start_time
        goodput = self.file_size / (time_consume * 1000)
        print("goodput:" + str(goodput) + "KB/s")
        rate = self.file_size / self.byte_count
        print("score:" + str(goodput * rate))
        print('Packet loss rate: ' + str((self.pack_count / self.pack_size - 1) * 100) + "%")
