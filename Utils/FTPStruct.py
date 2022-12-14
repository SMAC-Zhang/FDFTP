import struct

class DataStruct():
    def __init__(self, seq: int, ack: int, length: int, final_flag: bool, data: bytes, checksum: int):
        self.seq = seq
        self.ack = ack
        self.length = length
        self.final_flag = final_flag
        self.data = data
        self.checksum = checksum
    
    def pack(self) -> bytes:
        return struct.pack('iii?1024sq', self.seq, self.ack, self.length, self.final_flag, self.data, self.checksum)

    def unpack(ftp_struct):
        seq, ack, length, final_flag, data, checksum = struct.unpack('iii?1024sq', ftp_struct)
        return DataStruct(seq, ack, length, final_flag, data, checksum)

class AckStruct():
    def __init__(self, port: int, ack: int, checksum: int):
        self.port = port
        self.ack = ack
        self.checksum = checksum

    def pack(self) -> bytes:
        return struct.pack('iiq', self.port, self.ack, self.checksum)

    def unpack(ftp_struct):
        port, ack, checksum = struct.unpack('iiq', ftp_struct)
        return AckStruct(port, ack, checksum)

