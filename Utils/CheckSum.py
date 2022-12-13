import binascii

def generate_checksum(data: bytes) -> int:
    return (binascii.crc32(data) & 0xffffffff)

def check_checksum(data: bytes, checksum) -> bool:
    return (binascii.crc32(data) & 0xffffffff) == checksum