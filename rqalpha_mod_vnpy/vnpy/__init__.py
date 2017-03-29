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

import sys
from ..mod import vn_trader_path
sys.path.append(vn_trader_path)

from vtConstant import *
from eventEngine import EventEngine2, Event
from vtGateway import VtOrderReq, VtCancelOrderReq, VtSubscribeReq, VtBaseData, VtTradeData, VtOrderData
from eventType import EVENT_CONTRACT, EVENT_ORDER, EVENT_TRADE, EVENT_TICK, EVENT_LOG, EVENT_ACCOUNT, EVENT_POSITION, EVENT_ERROR
from ctpGateway.ctpGateway import CtpGateway, CtpMdApi, CtpTdApi, posiDirectionMapReverse

__all__ = [
    'EXCHANGE_SHFE',
    'OFFSET_OPEN',
    'OFFSET_CLOSE',
    'OFFSET_CLOSETODAY',
    'DIRECTION_LONG',
    'DIRECTION_SHORT',
    'PRICETYPE_LIMITPRICE',
    'PRICETYPE_MARKETPRICE',
    'STATUS_NOTTRADED',
    'STATUS_PARTTRADED',
    'STATUS_ALLTRADED',
    'STATUS_CANCELLED',
    'STATUS_UNKNOWN',
    'CURRENCY_CNY',
    'PRODUCT_FUTURES',
    'EMPTY_FLOAT',
    'EMPTY_STRING',
    'EventEngine2',
    'Event',
    'VtCancelOrderReq',
    'VtOrderReq',
    'VtBaseData',
    'VtOrderData',
    'VtTradeData',
    'VtSubscribeReq',
    'EVENT_POSITION',
    'EVENT_ACCOUNT',
    'EVENT_CONTRACT',
    'EVENT_LOG',
    'EVENT_ORDER',
    'EVENT_TICK',
    'EVENT_TRADE',
    'EVENT_ERROR',
    'CtpGateway',
    'CtpMdApi',
    'CtpTdApi',
    'posiDirectionMapReverse',
]
