# -*- coding: utf-8 -*-
from .mod import VNPYMod


def load_mod():
    return VNPYMod()


__config__ = {
    "gateway_type": 'CTP',
    "vn_trader_path": None,
    "all_day": True,
    "CTP": {
        'userID': None,
        'password': None,
        'brokerID': '9999',
        'tdAddress': 'tcp://180.168.146.187:10030',
        'mdAddress': 'tcp://180.168.146.187:10031'
    }
}
