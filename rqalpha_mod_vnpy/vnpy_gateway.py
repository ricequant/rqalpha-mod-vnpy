# -*- coding: utf-8 -*-
from time import sleep, time
from Queue import Queue, Empty
from threading import Thread

from .vn_trader.ctpGateway.ctpGateway import CtpGateway
from .vn_trader.ctpGateway.ctpGateway import CtpTdApi, CtpMdApi
from .vn_trader.ctpGateway.ctpGateway import directionMapReverse, posiDirectionMapReverse
from .vn_trader.vtGateway import VtBaseData, VtContractData
from .vn_trader.vtConstant import EMPTY_FLOAT, EMPTY_INT, EMPTY_STRING, EMPTY_UNICODE
from .vn_trader.eventEngine import Event

EVENT_POSITION_EXTRA = 'ePositionExtra'
EVENT_CONTRACT_EXTRA = 'eContractExtra'
EVENT_COMMISSION = 'eCommission'


# ------------------------------------ 自定义或扩展数据类型 ------------------------------------
class PositionExtra(VtBaseData):
    def __init__(self):
        super(PositionExtra, self).__init__()
        self.symbol = EMPTY_STRING
        self.direction = EMPTY_STRING

        self.closeProfit = EMPTY_FLOAT
        self.openCost = EMPTY_FLOAT


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


# ------------------------------------ 扩展CTPApi ------------------------------------
class RQCTPTdApi(CtpTdApi):
    def __init__(self, gateway):
        super(RQCTPTdApi, self).__init__(gateway)
        self.posExtraDict = {}

    def onRspQryTradingAccount(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryTradingAccount(data, error, n, last)
        self.gateway.status.account_success()

    def onRspQryInvestorPosition(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryInvestorPosition(data, error, n, last)
        positionName = '.'.join([data['InstrumentID'], data['PosiDirection']])
        posExtra = PositionExtra()
        posExtra.symbol = data['InstrumentID']
        posExtra.direction = posiDirectionMapReverse.get(data['PosiDirection'])
        posExtra.closeProfit = data["CloseProfit"]
        posExtra.openCost = data["OpenCost"]

        self.posExtraDict[positionName] = posExtra

        if last:
            for posExtra in self.posExtraDict.values():
                self.gateway.onPositionExtra(posExtra)

            self.gateway.status.position_success()

    def onRspQryInstrument(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryInstrument(data, error, n, last)

        contractExtra = ContractExtra()
        contractExtra.symbol = data['InstrumentID']

        contractExtra.expireDate = data['ExpireDate']
        contractExtra.openDate = data['OpenDate']
        contractExtra.longMarginRatio = data['LongMarginRatio']
        contractExtra.shortMarginRatio = data['ShortMarginRatio']

        self.gateway.onContractExtra(contractExtra)
        if last:
            self.gateway.status.contract_success()

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


# ------------------------------------ order生命周期 ------------------------------------
class RQVNCTPGateway(CtpGateway):
    def __init__(self, event_engine, gateway_name, login_dict):
        super(CtpGateway, self).__init__(event_engine, gateway_name)

        self.mdApi = RQCTPMdApi(self)
        self.tdApi = RQCTPTdApi(self)

        self.mdConnected = False
        self.tdConnected = False

        self.qryEnabled = False

        self.inited = False

        self.status = InitStatus()

        self.login_dict = login_dict

        self.query_que = Queue()
        self._activate = True
        self._query_thread = Thread(target=self._process)

    def connect_and_init_contract(self):
        self.put_query(self.connect, login_dict=self.login_dict)
        # self.connect(self.login_dict)
        self.status.wait_until_contract(timeout=100)
        self.wait_until_query_que_empty()

    def init_account(self):
        # TODO: 加入超时重试功能
        self.qryAccount()
        self.status.wait_until_account(timeout=10)
        sleep(1)
        self.qryPosition()
        self.status.wait_until_position(timeout=10)

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
        print 'on_commission'
        event = Event(type_=EVENT_COMMISSION)
        event.dict_['data'] = commissionData
        self.eventEngine.put(event)

    def put_query(self, query_name, **kwargs):
        self.query_que.put((query_name, kwargs))

    def _process(self):
        while self._activate:
            try:
                query = self.query_que.get(block=True, timeout=1)
            except Empty:
                continue
            query[0](**query[1])
            sleep(0.5)

    def start(self):
        self._activate = True
        self._query_thread.start()

    def wait_until_query_que_empty(self):
        while True:
            if self.query_que.empty():
                break


class InitStatus(object):
    def __init__(self):
        self._login = False
        self._contract = False
        self._account = False
        self._position = False

    def _wait_until(self, which, timeout):
        start_time = time()
        while True:
            which_dict = {
                'login': self._login,
                'contract': self._contract,
                'account': self._account,
                'position': self._position,
            }
            if which_dict[which]:
                break
            else:
                if timeout is not None:
                    if time() - start_time > timeout:
                        break

    def wait_until_login(self, timeout=None):
        self._wait_until('login', timeout)

    def login_success(self):
        self._login = True

    def wait_until_contract(self, timeout=None):
        self._wait_until('contract', timeout)

    def contract_success(self):
        self._contract = True

    def wait_until_account(self, timeout=None):
        self._wait_until('account', timeout)

    def account_success(self):
        self._account = True

    def wait_until_position(self, timeout=None):
        self._wait_until('position', timeout)

    def position_success(self):
        self._position = True

