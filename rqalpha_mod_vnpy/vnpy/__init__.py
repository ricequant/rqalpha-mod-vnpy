import os
import sys

vn_trader_path = os.path.join(os.path.dirname(__file__), 'vnpy/vn.trader')
sys.path.append(vn_trader_path)
# ctp_gateway_path = os.path.join(os.path.dirname(__file__), 'vnpy/vn.trader/ctpGateway')
# sys.path.append(ctp_gateway_path)

from vtConstant import *
from eventEngine import EventEngine2, Event
from vtGateway import VtOrderReq, VtCancelOrderReq, VtSubscribeReq, VtBaseData, VtTradeData, VtOrderData
from eventType import EVENT_CONTRACT, EVENT_ORDER, EVENT_TRADE, EVENT_TICK, EVENT_LOG, EVENT_ACCOUNT, EVENT_POSITION
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
    'CtpGateway',
    'CtpMdApi',
    'CtpTdApi',
    'posiDirectionMapReverse',
]
