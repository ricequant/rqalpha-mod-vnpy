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

from time import sleep, time
from Queue import Queue, Empty
from threading import Thread
from functools import wraps
from .vnpy import CtpGateway, CtpTdApi, CtpMdApi, posiDirectionMapReverse
from .vnpy import VtBaseData
from .vnpy import EMPTY_FLOAT, EMPTY_STRING
from .vnpy import Event
from .vnpy import EventEngine2

EVENT_POSITION_EXTRA = 'ePositionExtra'
EVENT_CONTRACT_EXTRA = 'eContractExtra'
EVENT_COMMISSION = 'eCommission'


def _id_gen(start=1):
    i = start
    while True:
        yield i
        i += 1


class QueryExecutor(object):

    que = Queue()
    query_dict = {}
    arg_dict = {}
    ret_dict = {}

    activate = False
    interval = 2

    execution_thread = None

    id_gen = _id_gen()

    @classmethod
    def process(cls):
        while cls.activate:
            try:
                query_id = cls.que.get(block=True, timeout=1)
            except Empty:
                continue

            query = cls.query_dict[query_id]
            print(str(query))
            args, kwargs = cls.arg_dict[query_id]
            cls.ret_dict[query_id] = query(*args, **kwargs)

            sleep(cls.interval)

    @classmethod
    def wait_until_query_empty(cls, timeout=600):
        start_time = time()
        while True:
            if cls.que.empty():
                break
            elif time() - start_time > timeout:
                break

    @classmethod
    def start(cls):
        cls.activate = True
        cls.execution_thread = Thread(target=cls.process)
        cls.execution_thread.start()

    @classmethod
    def stop(cls):
        cls.activate = False

    @classmethod
    def linear_execution(cls, timeout=20):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                query_id = next(cls.id_gen)
                block = True
                if 'block' in kwargs:
                    block = kwargs.pop('block')
                cls.query_dict[query_id] = func
                cls.arg_dict[query_id] = (args, kwargs)

                cls.que.put(query_id)

                if block:
                    start_time = time()
                    while True:
                        if query_id in cls.ret_dict:
                            break
                        else:
                            if timeout is not None:
                                if time() - start_time > timeout:
                                    break
            return wrapper
        return decorator


# ------------------------------------ 自定义或扩展数据类型 ------------------------------------
class PositionExtra(VtBaseData):
    def __init__(self):
        super(PositionExtra, self).__init__()
        self.symbol = EMPTY_STRING
        self.direction = EMPTY_STRING

        self.commission = EMPTY_FLOAT
        self.closeProfit = EMPTY_FLOAT
        self.openCost = EMPTY_FLOAT
        self.preSettlementPrice = EMPTY_FLOAT


class ContractExtra(VtBaseData):
    def __init__(self):
        super(ContractExtra, self).__init__()

        self.symbol = EMPTY_STRING

        self.openDate = EMPTY_STRING
        self.expireDate = EMPTY_STRING
        self.longMarginRatio = EMPTY_FLOAT
        self.shortMarginRatio = EMPTY_FLOAT


class CommissionData(VtBaseData):
    def __init__(self):
        super(CommissionData, self).__init__()

        self.symbol = EMPTY_STRING

        self.OpenRatioByMoney = EMPTY_FLOAT
        self.CloseRatioByMoney = EMPTY_FLOAT
        self.OpenRatioByVolume = EMPTY_FLOAT
        self.CloseRatioByVolume = EMPTY_FLOAT
        self.CloseTodayRatioByMoney = EMPTY_FLOAT
        self.CloseTodayRatioByVolume = EMPTY_FLOAT


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


# ------------------------------------ 扩展CTPApi ------------------------------------
class RQCTPTdApi(CtpTdApi):
    def __init__(self, gateway):
        super(RQCTPTdApi, self).__init__(gateway)
        self.posExtraDict = {}

    def onRspQryTradingAccount(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryTradingAccount(data, error, n, last)

    def onRspQryInvestorPosition(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryInvestorPosition(data, error, n, last)

        positionName = '.'.join([data['InstrumentID'], data['PosiDirection']])
        posExtra = PositionExtra()
        posExtra.symbol = data['InstrumentID']
        posExtra.direction = posiDirectionMapReverse.get(data['PosiDirection'])
        posExtra.commission = data['Commission']
        posExtra.closeProfit = data["CloseProfit"]
        posExtra.openCost = data["OpenCost"]
        posExtra.preSettlementPrice = data['PreSettlementPrice']

        self.posExtraDict[positionName] = posExtra

        if last:
            for posExtra in self.posExtraDict.values():
                self.gateway.onPositionExtra(posExtra)

    def onRspQryInstrument(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryInstrument(data, error, n, last)

        contractExtra = ContractExtra()
        contractExtra.symbol = data['InstrumentID']

        contractExtra.expireDate = data['ExpireDate']
        contractExtra.openDate = data['OpenDate']
        contractExtra.longMarginRatio = data['LongMarginRatio']
        contractExtra.shortMarginRatio = data['ShortMarginRatio']

        self.gateway.onContractExtra(contractExtra)

    @QueryExecutor.linear_execution()
    def connect(self, *args, **kwargs):
        super(RQCTPTdApi, self).connect(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def login(self, *args, **kwargs):
        super(RQCTPTdApi, self).login(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def reqSettlementInfoConfirm(self, *args, **kwargs):
        super(RQCTPTdApi, self).reqSettlementInfoConfirm(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def reqQryInstrument(self, *args, **kwargs):
        super(RQCTPTdApi, self).reqQryInstrument(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def qryAccount(self, *args, **kwargs):
        super(RQCTPTdApi, self).qryAccount(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def qryPosition(self, *args, **kwargs):
        super(RQCTPTdApi, self).qryPosition(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def reqCommission(self, instrumentId, exchangeId, userId, brokerId):
        self.reqID += 1
        req = {
            'InstrumentID': instrumentId,
            'InvestorID': userId,
            'BrokerID': brokerId,
            'ExchangeID': exchangeId
        }
        self.reqQryInstrumentCommissionRate(req, self.reqID)

    def onRspQryInstrumentCommissionRate(self, data, error, n, last):
        commissionData = CommissionData()
        commissionData.symbol = data['InstrumentID']

        commissionData.OpenRatioByMoney = data['OpenRatioByMoney']
        commissionData.OpenRatioByVolume = data['OpenRatioByVolume']
        commissionData.CloseRatioByMoney = data['CloseRatioByMoney']
        commissionData.CloseRatioByVolume = data['CloseRatioByVolume']
        commissionData.CloseTodayRatioByMoney = data['CloseTodayRatioByMoney']
        commissionData.CloseTodayRatioByVolume = data['CloseTodayRatioByVolume']

        self.gateway.onCommission(commissionData)


class RQCTPMdApi(CtpMdApi):
    def __init__(self, gateway):
        super(RQCTPMdApi, self).__init__(gateway)

    @QueryExecutor.linear_execution()
    def connect(self, *args, **kwargs):
        super(RQCTPMdApi, self).connect(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def login(self, *args, **kwargs):
        super(RQCTPMdApi, self).login(*args, **kwargs)

    @QueryExecutor.linear_execution()
    def subscribe(self, *args, **kwargs):
        super(RQCTPMdApi, self).subscribe(*args, **kwargs)


# ------------------------------------ 扩展gateway ------------------------------------
class RQVNCTPGateway(CtpGateway):
    def __init__(self, event_engine, gateway_name, login_dict):
        super(CtpGateway, self).__init__(event_engine, gateway_name)

        self.mdApi = RQCTPMdApi(self)
        self.tdApi = RQCTPTdApi(self)

        self.mdConnected = False
        self.tdConnected = False

        self.qryEnabled = False

        self.inited = False

        self.login_dict = login_dict

    def connect(self):
        userID = str(self.login_dict['userID'])
        password = str(self.login_dict['password'])
        brokerID = str(self.login_dict['brokerID'])
        tdAddress = str(self.login_dict['tdAddress'])
        mdAddress = str(self.login_dict['mdAddress'])

        self.mdApi.connect(userID, password, brokerID, mdAddress)
        self.tdApi.connect(userID, password, brokerID, tdAddress, None, None)
        self.initQuery()

    def qryAccount(self):
        super(RQVNCTPGateway, self).qryAccount()

    def qryPosition(self):
        super(RQVNCTPGateway, self).qryPosition()

    def qryCommission(self, symbol, exchange):
        self.tdApi.reqCommission(symbol, exchange, self.login_dict['userID'], self.login_dict['brokerID'])

    def onPositionExtra(self, positionExtra):
        event = Event(type_=EVENT_POSITION_EXTRA)
        event.dict_['data'] = positionExtra
        self.eventEngine.put(event)

    def onContractExtra(self, contractExtra):
        event = Event(type_=EVENT_CONTRACT_EXTRA)
        event.dict_['data'] = contractExtra
        self.eventEngine.put(event)

    def onCommission(self, commissionData):
        event = Event(type_=EVENT_COMMISSION)
        event.dict_['data'] = commissionData
        self.eventEngine.put(event)

    def onRspSettlementInfoConfirm(self, data, error, n, last):
        """确认结算信息回报"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = u'结算信息确认完成'
        self.gateway.onLog(log)

        # 查询合约代码
        self.reqID += 1
        self.reqQryInstrument({}, self.reqID)
