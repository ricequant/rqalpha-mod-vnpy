# -*- coding: utf-8 -*-
from dateutil.parser import parse
from datetime import timedelta

from rqalpha.model.order import Order
from rqalpha.model.trade import Trade
from rqalpha.model.instrument import Instrument
from rqalpha.const import ORDER_STATUS, ORDER_TYPE, POSITION_EFFECT
from .vn_trader.vtConstant import EXCHANGE_SHFE, OFFSET_OPEN, OFFSET_CLOSETODAY
from .utils import SIDE_REVERSE


def _trading_dt(calendar_dt):
    if calendar_dt.hour > 20:
        return calendar_dt + timedelta(days=1)
    return calendar_dt


def _order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


class RQVNInstrument(Instrument):
    def __init__(self, vnpy_contract):
        # TODO：从 rqalpha data bundle 中读取数据，补充字段
        listed_date = vnpy_contract.get('openDate')
        de_listed_date = vnpy_contract.get('expireDate')

        if listed_date is not None:
            listed_date = '%s-%s-%s' % (listed_date[:4], listed_date[4:6], listed_date[6:])
        else:
            listed_date = '0000-00-00'

        if de_listed_date is not None:
            de_listed_date = '%s-%s-%s' % (de_listed_date[:4], de_listed_date[4:6], de_listed_date[6:])
        else:
            de_listed_date = '0000-00-00'

        dic = {
            'order_book_id': _order_book_id(vnpy_contract.get('symbol')),
            'exchange': vnpy_contract.get('exchange'),
            'symbol': vnpy_contract.get('name'),
            'contract_multiplier': vnpy_contract.get('size'),
            'trading_unit': vnpy_contract.get('priceTick'),
            'type': 'Future',
            'margin_rate': vnpy_contract.get('longMarginRatio'),
            'listed_date': listed_date,
            'de_listed_date': de_listed_date,
            'maturity_date': de_listed_date,
        }

        super(RQVNInstrument, self).__init__(dic)


class RQVNOrder(Order):
    def __init__(self, vnpy_order=None):
        super(RQVNOrder, self).__init__()
        if vnpy_order is None:
            return
        self._order_id = next(self.order_id_gen)
        self._calendar_dt = parse(vnpy_order.orderTime)
        self._trading_dt = _trading_dt(self._calendar_dt)
        self._quantity = vnpy_order.totalVolume
        self._order_book_id = _order_book_id(vnpy_order.symbol)
        self._side = SIDE_REVERSE[vnpy_order.direction]

        if vnpy_order.exchange == EXCHANGE_SHFE:
            if vnpy_order.offset == OFFSET_OPEN:
                self._position_effect = POSITION_EFFECT.OPEN
            elif vnpy_order.offset == OFFSET_CLOSETODAY:
                self._position_effect = POSITION_EFFECT.CLOSE_TODAY
            else:
                self._position_effect = POSITION_EFFECT.CLOSE
        else:
            if vnpy_order.offset == OFFSET_OPEN:
                self._position_effect = POSITION_EFFECT.OPEN
            else:
                self._position_effect = POSITION_EFFECT.CLOSE

        self._message = ""
        self._filled_quantity = vnpy_order.tradedVolume
        self._status = ORDER_STATUS.PENDING_NEW
        # hard code VNPY 封装的报单类型中省掉了 type 字段
        self._type = ORDER_TYPE.LIMIT
        self._frozen_price = vnpy_order.price
        self._type = ORDER_TYPE.LIMIT
        self._avg_price = 0
        self._transaction_cost = 0

    @classmethod
    def create_from_vnpy_trade__(cls, vnpy_trade):
        order = cls()
        order._order_id = next(order.order_id_gen)
        order._calendar_dt = parse(vnpy_trade.tradeTime)
        order._trading_dt = _trading_dt(order._calendar_dt)
        order._order_book_id = _order_book_id(vnpy_trade.symbol)
        order._quantity = vnpy_trade.volume
        order._side = SIDE_REVERSE[vnpy_trade.direction]

        if vnpy_trade.exchange == EXCHANGE_SHFE:
            if vnpy_trade.offset == OFFSET_OPEN:
                order._position_effect = POSITION_EFFECT.OPEN
            elif vnpy_trade.offset == OFFSET_CLOSETODAY:
                order._position_effect = POSITION_EFFECT.CLOSE_TODAY
            else:
                order._position_effect = POSITION_EFFECT.CLOSE
        else:
            if vnpy_trade.offset == OFFSET_OPEN:
                order._position_effect = POSITION_EFFECT.OPEN
            else:
                order._position_effect = POSITION_EFFECT.CLOSE

        order._message = ""
        order._filled_quantity = vnpy_trade.volume
        order._status = ORDER_STATUS.FILLED
        order._type = ORDER_TYPE.LIMIT
        order._avg_price = vnpy_trade.price
        order._transaction_cost = 0
        return order


class RQVNTrade(Trade):
    def __init__(self, vnpy_trade, order):
        super(RQVNTrade, self).__init__()
        self._calendar_dt = parse(vnpy_trade.tradeTime)
        self._trading_dt = _trading_dt(self._calendar_dt)
        self._price = vnpy_trade.price
        self._amount = vnpy_trade.volume
        self._order = order
        self._tax = 0.
        self._trade_id = next(self.trade_id_gen)
        self._close_today_amount = 0.
