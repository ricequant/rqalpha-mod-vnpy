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


"""
__config__ = {"mod": {"vnpy": {
    "gateways: {
        "FUTURE": {
            "name": "CTP",
            "app": "vnpy.gateway.ctp:CtpGateway",
            "settings": {
                "用户名": "",
                "密码": "",
                "经纪商代码": "9999",
                "交易服务器": "tcp://180.168.146.187:10100",
                "行情服务器": "tcp://180.168.146.187:10110",
                "产品名称": "simnow_client_test",
                "授权编码": "0000000000000000"
            }
        },
        "STOCK": {}
    }
}}}
"""

__config__ = {
    "gateways": {},
}


def load_mod():
    from .mod import VNPYMod
    return VNPYMod()
