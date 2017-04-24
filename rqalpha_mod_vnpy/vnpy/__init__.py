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
from vtGateway import VtOrderReq, VtCancelOrderReq, VtSubscribeReq, VtBaseData, VtTradeData, VtOrderData, VtPositionData, VtContractData, VtTickData
from eventType import EVENT_CONTRACT, EVENT_ORDER, EVENT_TRADE, EVENT_TICK, EVENT_ACCOUNT, EVENT_POSITION
from gateway.ctpGateway.ctpGateway import CtpGateway, CtpMdApi, CtpTdApi, posiDirectionMapReverse, exchangeMapReverse, productClassMapReverse, MdApi, TdApi, directionMapReverse, offsetMapReverse, statusMapReverse, priceTypeMap, directionMap, offsetMap
from gateway.ctpGateway.ctpDataType import defineDict



__all__ = [
    'DIRECTION_LONG',
    'DIRECTION_SHORT',
    'DIRECTION_UNKNOWN',
    'PRICETYPE_MARKETPRICE',
    'PRICETYPE_LIMITPRICE',
    'PRICETYPE_FAK',
    'PRICETYPE_FOK',
    'OFFSET_OPEN',
    'OFFSET_CLOSE',
    'OFFSET_CLOSETODAY',
    'OFFSET_UNKNOWN',
    'STATUS_UNKNOWN',
    'STATUS_PARTTRADED',
    'STATUS_NOTTRADED',
    'STATUS_ALLTRADED',
    'STATUS_CANCELLED',
    'EMPTY_STRING',
    'EMPTY_FLOAT',
    'EMPTY_INT',
    'PRODUCT_FUTURES',
    'PRODUCT_UNKNOWN',
    'CURRENCY_CNY',
    'EXCHANGE_SHFE',
    'EXCHANGE_UNKNOWN',
    'OPTION_CALL',
    'OPTION_PUT',

    'EventEngine2',
    'Event',

    'VtCancelOrderReq',
    'VtOrderReq',
    'VtBaseData',
    'VtOrderData',
    'VtTradeData',
    'VtPositionData',
    'VtContractData',
    'VtSubscribeReq',
    'VtTickData',

    'EVENT_POSITION',
    'EVENT_ACCOUNT',
    'EVENT_CONTRACT',
    'EVENT_ORDER',
    'EVENT_TICK',
    'EVENT_TRADE',
    
    'MdApi',
    'TdApi',
    'CtpGateway',
    'CtpMdApi',
    'CtpTdApi',
    'posiDirectionMapReverse',
    'exchangeMapReverse',
    'productClassMapReverse',
    'directionMapReverse',
    'offsetMapReverse',
    'statusMapReverse',
    'priceTypeMap',
    'directionMap',
    'offsetMap',

    'defineDict',
]
