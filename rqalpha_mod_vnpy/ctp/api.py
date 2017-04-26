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

from functools import wraps
import os
from rqalpha.const import ORDER_TYPE, SIDE, POSITION_EFFECT

from .data_dict import TickDict, PositionDict, AccountDict, InstrumentDict, OrderDict, TradeDict, CallBackData, CommissionDict

from ..vnpy import *
from ..utils import make_order_book_id


ORDER_TYPE_MAPPING = {
    ORDER_TYPE.MARKET: defineDict["THOST_FTDC_OPT_LimitPrice"],
    ORDER_TYPE.LIMIT: defineDict["THOST_FTDC_OPT_AnyPrice"],
}

SIDE_MAPPING = {
    SIDE.BUY: defineDict['THOST_FTDC_D_Buy'],
    SIDE.SELL: defineDict['THOST_FTDC_D_Sell']
}

POSITION_EFFECT_MAPPING = {
    POSITION_EFFECT.OPEN: defineDict['THOST_FTDC_OF_Open'],
    POSITION_EFFECT.CLOSE: defineDict['THOST_FTDC_OF_Close'],
    POSITION_EFFECT.CLOSE_TODAY: defineDict['THOST_FTDC_OF_CloseToday'],
}


def query_in_sync(func):
    @wraps(func)
    def wrapper(api, data, error, n, last):
        api.req_id = max(api.req_id, n)
        result = func(api, data, last)
        if last:
            api.gateway.on_query(api.api_name, n, result)
    return wrapper


class CtpMdApi(MdApi):
    def __init__(self, gateway, temp_path, user_id, password, broker_id, address, api_name='ctp_md'):
        super(CtpMdApi, self).__init__()

        self.gateway = gateway
        self.temp_path = temp_path
        self.req_id = 0

        self.connected = False
        self.logged_in = False

        self.user_id = user_id
        self.password = password
        self.broker_id = broker_id
        self.address = address

        self.api_name = api_name

    def onFrontConnected(self):
        """服务器连接"""
        self.connected = True
        self.login()

    def onFrontDisconnected(self, n):
        """服务器断开"""
        self.connected = False
        self.logged_in = False

    def onHeartBeatWarning(self, n):
        """心跳报警"""
        pass

    def onRspError(self, error, n, last):
        """错误回报"""
        self.gateway.on_err(error)

    def onRspUserLogin(self, data, error, n, last):
        """登陆回报"""
        if error['ErrorID'] == 0:
            self.logged_in = True
        else:
            self.gateway.on_err(error)

    def onRspUserLogout(self, data, error, n, last):
        """登出回报"""
        if error['ErrorID'] == 0:
            self.logged_in = False
        else:
            self.gateway.on_err(error)

    def onRspSubMarketData(self, data, error, n, last):
        """订阅合约回报"""
        pass

    def onRspUnSubMarketData(self, data, error, n, last):
        """退订合约回报"""
        pass

    def onRtnDepthMarketData(self, data):
        """行情推送"""
        tick_dict = TickDict(data)
        self.gateway.on_tick(tick_dict)

    def onRspSubForQuoteRsp(self, data, error, n, last):
        """订阅期权询价"""
        pass

    def onRspUnSubForQuoteRsp(self, data, error, n, last):
        """退订期权询价"""
        pass

    def onRtnForQuoteRsp(self, data):
        """期权询价推送"""
        pass

    def connect(self):
        """初始化连接"""
        if not self.connected:
            if not os.path.exists(self.temp_path):
                os.makedirs(self.temp_path)
            self.createFtdcMdApi(self.temp_path)
            self.registerFront(self.address)
            self.init()
        else:
            self.login()

    def subscribe(self, order_book_id):
        """订阅合约"""
        instrument_id = self.gateway.get_instrument_id(order_book_id)
        if instrument_id:
            self.subscribeMarketData(str(instrument_id))

    def login(self):
        """登录"""
        if not self.logged_in:
            req = {
                'UserID': self.user_id,
                'Password': self.password,
                'BrokerID': self.broker_id,
            }
            self.req_id += 1
            self.reqUserLogin(req, self.req_id)
        return self.req_id

    def close(self):
        """关闭"""
        self.exit()


class CtpTdApi(TdApi):

    def __init__(self, gateway, temp_path, user_id, password, broker_id, address, auth_code, user_production_info, api_name='ctp_td'):
        super(CtpTdApi, self).__init__()

        self.gateway = gateway
        self.temp_path = temp_path
        self.req_id = 0

        self.connected = False
        self.logged_in = False
        self.authenticated = False

        self.user_id = user_id
        self.password = password
        self.broker_id = broker_id
        self.address = address
        self.auth_code = auth_code
        self.user_production_info = user_production_info

        self.front_id = 0
        self.session_id = 0

        self.require_authentication = False

        self.pos_cache = {}
        self.ins_cache = {}
        self.order_cache = {}

        self.api_name = api_name

    def onFrontConnected(self):
        """服务器连接"""
        self.connected = True
        if self.require_authentication:
            self.authenticate()
        else:
            self.login()

    def onFrontDisconnected(self, n):
        """服务器断开"""
        self.connected = False
        self.logged_in = False

    def onHeartBeatWarning(self, n):
        """心跳报警"""
        pass

    def onRspAuthenticate(self, data, error, n, last):
        """验证客户端回报"""
        if error['ErrorID'] == 0:
            self.authenticated = True
            self.login()
        else:
            self.gateway.on_err(error)

    def onRspUserLogin(self, data, error, n, last):
        """登陆回报"""
        if error['ErrorID'] == 0:
            self.front_id = str(data['FrontID'])
            self.session_id = str(data['SessionID'])
            self.logged_in = True
            self.qrySettlementInfoConfirm()
        else:
            self.gateway.on_err(error)

    def onRspUserLogout(self, data, error, n, last):
        """登出回报"""
        if error['ErrorID'] == 0:
            self.logged_in = False
        else:
            self.gateway.on_err(error)

    def onRspUserPasswordUpdate(self, data, error, n, last):
        """"""
        pass

    def onRspTradingAccountPasswordUpdate(self, data, error, n, last):
        """"""
        pass

    def onRspOrderInsert(self, data, error, n, last):
        """发单错误（柜台）"""
        order_dict = OrderDict(data, rejected=True)
        self.gateway.on_order(CallBackData(self.api_name, n, order_dict))

    def onRspParkedOrderInsert(self, data, error, n, last):
        """"""
        pass

    def onRspParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspOrderAction(self, data, error, n, last):
        """撤单错误（柜台）"""
        self.gateway.on_err(error)

    def onRspQueryMaxOrderVolume(self, data, error, n, last):
        """"""
        pass

    def onRspSettlementInfoConfirm(self, data, error, n, last):
        """确认结算信息回报"""
        pass
        
    def onRspRemoveParkedOrder(self, data, error, n, last):
        """"""
        pass

    def onRspRemoveParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspExecOrderInsert(self, data, error, n, last):
        """"""
        pass

    def onRspExecOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspForQuoteInsert(self, data, error, n, last):
        """"""
        pass

    def onRspQuoteInsert(self, data, error, n, last):
        """"""
        pass

    def onRspQuoteAction(self, data, error, n, last):
        """"""
        pass

    def onRspLockInsert(self, data, error, n, last):
        """"""
        pass

    def onRspCombActionInsert(self, data, error, n, last):
        """"""
        pass

    @query_in_sync
    def onRspQryOrder(self, data, last):
        """报单回报"""
        order_dict = OrderDict(data)
        self.order_cache[order_dict.order_id] = order_dict
        if last:
            return self.order_cache

    def onRspQryTrade(self, data, error, n, last):
        """"""
        pass

    @query_in_sync
    def onRspQryInvestorPosition(self, data, last):
        """持仓查询回报"""

        if not data['InstrumentID']:
            return

        order_book_id = make_order_book_id(data['InstrumentID'])
        if order_book_id not in self.pos_cache:
            self.pos_cache[order_book_id] = PositionDict(data, DataCache.contract_multiplier_cache[order_book_id])
        else:
            self.pos_cache[order_book_id].update_position(data)

        if last:
            return self.pos_cache

    @query_in_sync
    def onRspQryTradingAccount(self, data, last):
        """资金账户查询回报"""
        return AccountDict(data)

    def onRspQryInvestor(self, data, error, n, last):
        """"""
        pass

    def onRspQryTradingCode(self, data, error, n, last):
        """"""
        pass

    def onRspQryInstrumentMarginRate(self, data, error, n, last):
        """"""
        pass

    @query_in_sync
    def onRspQryInstrumentCommissionRate(self, data, last):
        """请求查询合约手续费率响应"""
        return CommissionDict(data)

    def onRspQryExchange(self, data, error, n, last):
        """"""
        pass

    def onRspQryProduct(self, data, error, n, last):
        """"""
        pass

    @query_in_sync
    def onRspQryInstrument(self, data, last):
        """合约查询回报"""
        if not data['InstrumentID']:
            return

        ins_dict = InstrumentDict(data)
        self.ins_cache[ins_dict.order_book_id] = ins_dict

        if last:
            return self.ins_cache


    def onRspQryDepthMarketData(self, data, error, n, last):
        """"""
        pass

    def onRspQrySettlementInfo(self, data, error, n, last):
        """"""
        pass

    def onRspQryTransferBank(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorPositionDetail(self, data, error, n, last):
        """"""
        pass

    def onRspQryNotice(self, data, error, n, last):
        """"""
        pass

    def onRspQrySettlementInfoConfirm(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorPositionCombineDetail(self, data, error, n, last):
        """"""
        pass

    def onRspQryCFMMCTradingAccountKey(self, data, error, n, last):
        """"""
        pass

    def onRspQryEWarrantOffset(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorProductGroupMargin(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeMarginRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeMarginRateAdjust(self, data, error, n, last):
        """"""
        pass

    def onRspQryExchangeRate(self, data, error, n, last):
        """"""
        pass

    def onRspQrySecAgentACIDMap(self, data, error, n, last):
        """"""
        pass

    def onRspQryProductExchRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryProductGroup(self, data, error, n, last):
        """"""
        pass

    def onRspQryOptionInstrTradeCost(self, data, error, n, last):
        """"""
        pass

    def onRspQryOptionInstrCommRate(self, data, error, n, last):
        """"""
        pass

    def onRspQryExecOrder(self, data, error, n, last):
        """"""
        pass

    def onRspQryForQuote(self, data, error, n, last):
        """"""
        pass

    def onRspQryQuote(self, data, error, n, last):
        """"""
        pass

    def onRspQryLock(self, data, error, n, last):
        """"""
        pass

    def onRspQryLockPosition(self, data, error, n, last):
        """"""
        pass

    def onRspQryInvestorLevel(self, data, error, n, last):
        """"""
        pass

    def onRspQryExecFreeze(self, data, error, n, last):
        """"""
        pass

    def onRspQryCombInstrumentGuard(self, data, error, n, last):
        """"""
        pass

    def onRspQryCombAction(self, data, error, n, last):
        """"""
        pass

    def onRspQryTransferSerial(self, data, error, n, last):
        """"""
        pass

    def onRspQryAccountregister(self, data, error, n, last):
        """"""
        pass

    def onRspError(self, error, n, last):
        """错误回报"""
        self.gateway.on_err(error)

    def onRtnOrder(self, data):
        """报单回报"""
        order_dict = OrderDict(data)
        self.gateway.on_order(order_dict)

    def onRtnTrade(self, data):
        """成交回报"""
        trade_dict = TradeDict(data)
        self.gateway.on_trade(CallBackData(self.api_name, n, trade_dict))

    def onErrRtnOrderInsert(self, data, error):
        """发单错误回报（交易所）"""

        self.gateway.on_err(error)
        order_dict = OrderDict(data, rejected=True)
        self.gateway.on_order(CallBackData(self.api_name, n, order_dict))

    def onErrRtnOrderAction(self, data, error):
        """撤单错误回报（交易所）"""
        self.gateway.on_err(error)

    def onRtnInstrumentStatus(self, data):
        """"""
        pass

    def onRtnTradingNotice(self, data):
        """"""
        pass

    def onRtnErrorConditionalOrder(self, data):
        """"""
        pass

    def onRtnExecOrder(self, data):
        """"""
        pass

    def onErrRtnExecOrderInsert(self, data, error):
        """"""
        pass

    def onErrRtnExecOrderAction(self, data, error):
        """"""
        pass

    def onErrRtnForQuoteInsert(self, data, error):
        """"""
        pass

    def onRtnQuote(self, data):
        """"""
        pass

    def onErrRtnQuoteInsert(self, data, error):
        """"""
        pass

    def onErrRtnQuoteAction(self, data, error):
        """"""
        pass

    def onRtnForQuoteRsp(self, data):
        """"""
        pass

    def onRtnCFMMCTradingAccountToken(self, data):
        """"""
        pass

    def onRtnLock(self, data):
        """"""
        pass

    def onErrRtnLockInsert(self, data, error):
        """"""
        pass

    def onRtnCombAction(self, data):
        """"""
        pass

    def onErrRtnCombActionInsert(self, data, error):
        """"""
        pass

    def onRspQryContractBank(self, data, error, n, last):
        """"""
        pass

    def onRspQryParkedOrder(self, data, error, n, last):
        """"""
        pass

    def onRspQryParkedOrderAction(self, data, error, n, last):
        """"""
        pass

    def onRspQryTradingNotice(self, data, error, n, last):
        """"""
        pass

    def onRspQryBrokerTradingParams(self, data, error, n, last):
        """"""
        pass

    def onRspQryBrokerTradingAlgos(self, data, error, n, last):
        """"""
        pass

    def onRspQueryCFMMCTradingAccountToken(self, data, error, n, last):
        """"""
        pass

    def onRtnFromBankToFutureByBank(self, data):
        """"""
        pass

    def onRtnFromFutureToBankByBank(self, data):
        """"""
        pass

    def onRtnRepealFromBankToFutureByBank(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByBank(self, data):
        """"""
        pass

    def onRtnFromBankToFutureByFuture(self, data):
        """"""
        pass

    def onRtnFromFutureToBankByFuture(self, data):
        """"""
        pass

    def onRtnRepealFromBankToFutureByFutureManual(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByFutureManual(self, data):
        """"""
        pass

    def onRtnQueryBankBalanceByFuture(self, data):
        """"""
        pass

    def onErrRtnBankToFutureByFuture(self, data, error):
        """"""
        pass

    def onErrRtnFutureToBankByFuture(self, data, error):
        """"""
        pass

    def onErrRtnRepealBankToFutureByFutureManual(self, data, error):
        """"""
        pass

    def onErrRtnRepealFutureToBankByFutureManual(self, data, error):
        """"""
        pass

    def onErrRtnQueryBankBalanceByFuture(self, data, error):
        """"""
        pass

    def onRtnRepealFromBankToFutureByFuture(self, data):
        """"""
        pass

    def onRtnRepealFromFutureToBankByFuture(self, data):
        """"""
        pass

    def onRspFromBankToFutureByFuture(self, data, error, n, last):
        """"""
        pass

    def onRspFromFutureToBankByFuture(self, data, error, n, last):
        """"""
        pass

    def onRspQueryBankAccountMoneyByFuture(self, data, error, n, last):
        """"""
        pass

    def onRtnOpenAccountByBank(self, data):
        """"""
        pass

    def onRtnCancelAccountByBank(self, data):
        """"""
        pass

    def onRtnChangeAccountByBank(self, data):
        """"""
        pass

    def connect(self):
        """初始化连接"""
        if not self.connected:
            if not os.path.exists(self.temp_path):
                os.makedirs(self.temp_path)
            self.createFtdcTraderApi(self.temp_path)
            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)
            self.registerFront(self.address)
            self.init()
        else:
            if self.require_authentication:
                self.authenticate()
            else:
                self.login()

    def login(self):
        """连接服务器"""
        if not self.logged_in:
            req = {
                'UserID': self.user_id,
                'Password': self.password,
                'BrokerID': self.broker_id,
            }
            self.req_id += 1
            self.reqUserLogin(req, self.req_id)
        return self.req_id

    def authenticate(self):
        """申请验证"""
        if self.authenticated:
            req = {
                'UserID': self.user_id,
                'BrokerID': self.broker_id,
                'AuthCode': self.auth_code,
                'UserProductInfo': self.user_production_info,
            }
            self.req_id += 1
            self.reqAuthenticate(req, self.req_id)
        else:
            self.login()
        return self.req_id

    def qrySettlementInfoConfirm(self):
        req = {
            'BrokerID': self.broker_id,
            'InvestorID': self.user_id,
        }
        self.req_id += 1
        self.reqSettlementInfoConfirm(req, self.req_id)
        return self.req_id

    def qryInstrument(self):
        self.ins_cache = {}
        self.req_id += 1
        self.reqQryInstrument({}, self.req_id)
        return self.req_id

    def qyrCommission(self, order_book_id):
        self.req_id += 1
        req = {
            'InstrumentID': self.gateway.get_instrument_id(order_book_id),
            'InvestorID': self.userID,
            'BrokerID': self.brokerID,
            'ExchangeID': self.gateway.get_exchange_id(order_book_id)
        }
        self.reqQryInstrumentCommissionRate(req, self.req_id)
        return self.req_id

    def qryAccount(self):
        """查询账户"""
        self.req_id += 1
        self.reqQryTradingAccount({}, self.req_id)
        return self.req_id

    def qryPosition(self):
        """查询持仓"""
        self.pos_cache = {}
        self.req_id += 1
        req = {
            'BrokerID': self.broker_id,
            'InvestorID': self.user_id,
        }
        self.reqQryInvestorPosition(req, self.req_id)
        return self.req_id

    def qryOrder(self):
        """订单查询"""
        self.order_cache = {}
        self.req_id += 1
        req = {
            'BrokerID': self.broker_id,
            'InvestorID': self.user_id,
        }
        self.reqQryOrder(req, self.req_id)
        return self.req_id

    def sendOrder(self, order):
        """发单"""

        req = {
            'InstrumentID': self.gateway.get_instrument_id(order.order_book_id),
            'LimitPrice': order.price,
            'VolumeTotalOriginal': order.quantity,
            'OrderPriceType': ORDER_TYPE_MAPPING.get(order.type, ''),
            'Direction': SIDE_MAPPING.get(order.side, ''),
            'CombOffsetFlag': POSITION_EFFECT_MAPPING.get(order.position_effect, ''),

            'OrderRef': str(order.order_id),
            'InvestorID': self.user_id,
            'UserID': self.user_id,
            'BrokerID': self.broker_id,

            'CombHedgeFlag': defineDict['THOST_FTDC_HF_Speculation'],       # 投机单
            'ContingentCondition': defineDict['THOST_FTDC_CC_Immediately'], # 立即发单
            'ForceCloseReason': defineDict['THOST_FTDC_FCC_NotForceClose'], # 非强平
            'IsAutoSuspend': 0,                                             # 非自动挂起
            'TimeCondition': defineDict['THOST_FTDC_TC_GFD'],               # 今日有效
            'VolumeCondition': defineDict['THOST_FTDC_VC_AV'],              # 任意成交量
            'MinVolume': 1,                                                 # 最小成交量为1
        }

        self.req_id += 1
        self.reqOrderInsert(req, self.req_id)
        return self.req_id

    def cancelOrder(self, order):
        """撤单"""
        self.req_id += 1
        req = {
            'InstrumentID': self.gateway.get_instrument_id(order.order_book_id),
            'ExchangeID': self.gateway.get_exchange_id(order.order_book_id),
            'OrderRef': str(order.order_id),
            'FrontID': int(self.front_id),
            'SessionID': int(self.session_id),

            'ActionFlag': defineDict['THOST_FTDC_AF_Delete'],
            'BrokerID': self.broker_id,
            'InvestorID': self.user_id,
        }

        self.reqOrderAction(req, self.req_id)
        return self.req_id

    def close(self):
        """关闭"""
        self.exit()
