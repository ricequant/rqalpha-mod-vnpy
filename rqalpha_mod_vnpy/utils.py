import uuid
import socket


def get_ip_address() -> str:
    return socket.gethostbyname(socket.gethostname())


def get_mac_address() -> str:
    return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
