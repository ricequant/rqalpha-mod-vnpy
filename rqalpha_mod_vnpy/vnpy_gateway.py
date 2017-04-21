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

from Queue import Empty
from .vnpy import *

EVENT_QRY_ORDER = 'eQryOrder'
EVENT_COMMISSION = 'eCommission'


def _id_gen(start=1):
    i = start
    while True:
        yield i
        i += 1


# ------------------------------------ 自定义或扩展数据类型 ------------------------------------
class RQPositionData(VtPositionData):
    def __init__(self):
        super(RQPositionData, self).__init__()

        self.todayPosition = EMPTY_FLOAT
        self.commission = EMPTY_FLOAT
        self.closeProfit = EMPTY_FLOAT
        self.openCost = EMPTY_FLOAT
        self.preSettlementPrice = EMPTY_FLOAT
        self.avgOpenPrice = EMPTY_FLOAT


class RQContractData(VtContractData):
    def __init__(self):
        super(RQContractData, self).__init__()

        self.openDate = EMPTY_STRING
        self.expireDate = EMPTY_STRING
        self.longMarginRatio = EMPTY_FLOAT
        self.shortMarginRatio = EMPTY_FLOAT


class RQCommissionData(VtBaseData):
    def __init__(self):
        super(RQCommissionData, self).__init__()

        self.symbol = EMPTY_STRING

        self.OpenRatioByMoney = EMPTY_FLOAT
        self.CloseRatioByMoney = EMPTY_FLOAT
        self.OpenRatioByVolume = EMPTY_FLOAT
        self.CloseRatioByVolume = EMPTY_FLOAT
        self.CloseTodayRatioByMoney = EMPTY_FLOAT
        self.CloseTodayRatioByVolume = EMPTY_FLOAT


class RQOrderReq(VtOrderReq):
    def __init__(self):
        super(RQOrderReq, self).__init__()
        self.orderID = EMPTY_INT


# ------------------------------------ 扩展事件引擎 ------------------------------------
class RQVNEventEngine(EventEngine2):
    def __init__(self):
        super(RQVNEventEngine, self).__init__()

    def __run(self):
        """引擎运行"""
        print('event_engine run')
        while self.__active == True:
            try:
                event = self.__queue.get(block=True, timeout=10)  # 获取事件的阻塞时间设为1秒
                print(str(event))
                self.__process(event)
            except Empty:
                pass
            except Exception as e:
                system_log.exception("event engine process fail")
                system_log.error("We can not handle this exception exiting.")
                os._exit(-1)
