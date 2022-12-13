import hashlib

def get_md5(file_name):
    with open(file_name, 'rb') as fp:
        data = fp.read()
    return hashlib.md5(data).hexdigest()