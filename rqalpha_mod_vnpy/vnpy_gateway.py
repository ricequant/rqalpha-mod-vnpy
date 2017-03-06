# -*- coding: utf-8 -*-
from time import sleep, time

from .vn_trader.ctpGateway.ctpGateway import CtpGateway
from .vn_trader.ctpGateway.ctpGateway import CtpTdApi, CtpMdApi
from .vn_trader.ctpGateway.ctpGateway import directionMapReverse, posiDirectionMapReverse
from .vn_trader.vtGateway import VtBaseData, VtContractData
from .vn_trader.vtConstant import EMPTY_FLOAT, EMPTY_INT, EMPTY_STRING, EMPTY_UNICODE
from .vn_trader.eventEngine import Event

EVENT_POSITION_EXTRA = 'ePositionExtra'


# ------------------------------------ 自定义或扩展数据类型 ------------------------------------
class PositionExtra(VtBaseData):
    def __init__(self):
        super(PositionExtra, self).__init__()
        self.symbol = EMPTY_STRING
        self.direction = EMPTY_STRING

        self.closeProfit = EMPTY_FLOAT
        self.openCost = EMPTY_FLOAT


# ------------------------------------ 扩展CTPApi ------------------------------------
class RQCTPTdApi(CtpTdApi):
    def __init__(self, gateway):
        super(RQCTPTdApi, self).__init__(gateway)
        self.posExtraDict = {}

    def onRspQryInstrument(self, data, error, n, last):
        super(RQCTPTdApi, self).onRspQryInstrument(data, error, n, last)
        if last:
            self.gateway.status.contract_success()

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


class RQCTPMdApi(CtpMdApi):
    def __init__(self, gateway):
        super(RQCTPMdApi, self).__init__(gateway)


# ------------------------------------ order生命周期 ------------------------------------
class RQVNCTPGateway(CtpGateway):
    def __init__(self, event_engine, gateway_name):
        super(CtpGateway, self).__init__(event_engine, gateway_name)

        self.mdApi = RQCTPMdApi(self)
        self.tdApi = RQCTPTdApi(self)

        self.mdConnected = False
        self.tdConnected = False

        self.qryEnabled = False

        self.inited = False

        self.status = InitStatus()

    def do_init(self, login_dict):
        # TODO: 加入超时重试功能
        self.connect(login_dict)
        self.status.wait_until_contract(timeout=10)
        sleep(1)
        self.qryAccount()
        self.status.wait_until_account(timeout=10)
        sleep(1)
        self.qryPosition()
        self.status.wait_until_position(timeout=10)

    def onPositionExtra(self, posExtra):
        event = Event(type_=EVENT_POSITION_EXTRA)
        event.dict_['data'] = posExtra
        self.eventEngine.put(event)


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

