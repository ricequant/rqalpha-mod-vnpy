#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017 Ricequant, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__config__ = {
    "gateway_type": 'CTP',
    "vn_trader_path": None,
    "all_day": True,
    "query_interval": 2,
    "CTP": {
        'userID': None,
        'password': None,
        'brokerID': '9999',
        'tdAddress': 'tcp://180.168.146.187:10030',
        'mdAddress': 'tcp://180.168.146.187:10031'
    }
}


def load_mod():
    from .mod import VNPYMod
    return VNPYMod()
