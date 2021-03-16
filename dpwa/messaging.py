import logging
import pickle
import struct
import time
import sys

LOGGER = logging.getLogger(__name__)


#
# The header consists of
#   message_type(2)
#   msg_length(4)
#   payload_length(4)
#
HEADER_LEN = 2 + 4 + 4
HEADER_FMT = '<HLL'
CHUNK_SIZE = 8 * (1024 ** 2)


class MessageError(Exception):
    pass


def _header_encode(message_type, message=None, payload=None):
    message_type = int(message_type)
    message_len = len(message) if message is not None else 0
    payload_len = len(payload) if payload is not None else 0
    return struct.pack(HEADER_FMT, message_type, message_len, payload_len)


def _header_decode(header):
    message_type, message_len, payload_len = struct.unpack(HEADER_FMT, header)
    return message_type, message_len, payload_len


def recv_message(sock):
    # Block until the header arrives
    #recv_buf = bytearray(600*1024**2)
    first_chunk = sock.recv(CHUNK_SIZE + HEADER_LEN)
    if len(first_chunk) == 0:
        raise MessageError("recv() failed, connection closed. fd={}".format(sock.fileno()))

    hdr = first_chunk[:HEADER_LEN]
    message_type, message_len, payload_len = _header_decode(hdr)
    total_len = message_len + payload_len

    # Read the message
    blob = first_chunk[HEADER_LEN:]
    count = len(blob)
    recv_buf = bytearray(total_len)
    recv_buf[:count-1] = blob
    view = memoryview(recv_buf)
    #t_start = time.time()
    while count < total_len:
        #chunk = sock.recv(CHUNK_SIZE)
        remain_len = total_len - count
        #nbytes = sock.recv_into(recv_buf[count:], remain_len)
        #chunk = sock.recv(remain_len)
        #nbytes = len(chunk)
        nbytes,_ = sock.recvfrom_into(view[count:], remain_len)
        if nbytes == 0:
            raise MessageError("recv() failed, connection closed. fd={}".format(sock.fileno()))
        count += nbytes

    if count > total_len:
        raise MessageError("Message bigger than specified! {} > {} (fd={})" \
                           .format(count, total_len, sock.fileno()))
    #t_end = time.time()
    #td = t_end- t_start
    #print('Receiving size: {0} MB'.format(float(count)/1000000.0))
    #print('Receiving throughput: {0} MB/s'.format(float(count/td)/1000000.0))
    if message_len == 0:
        message = None
    else:
        message_raw = recv_buf[:message_len]
        message = pickle.loads(message_raw)

    if payload_len == 0:
        payload = None
    else:
        payload = recv_buf[message_len:total_len]
    return message_type, message, payload


def send_message(sock, message_type, message=None, payload=None):
    if message is None:
        message_raw = bytes()
    else:
        message_raw = pickle.dumps(message)

    if payload is None:
        payload = bytes()

    hdr = _header_encode(message_type, message_raw, payload)
    blob = hdr + message_raw + payload

    count = 0
    view = memoryview(blob)
    #t_start = time.time()
    while count < len(blob):
        sent = sock.send(view[count:])
        if sent == 0:
            raise MessageError("send() failed, connection closed. fd={}" \
                               .format(sock.fileno()))
        count += sent
  
    #t_end = time.time()
    #td = t_end - t_start 
    #print('Sending size: {0} MB'.format(float(count)/1000000.0))
    #print('Sending throughput: {0} MB/s'.format(float(count/td)/1000000.0))
    

