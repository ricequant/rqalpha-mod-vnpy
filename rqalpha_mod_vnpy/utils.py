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

from dateutil.parser import parse
from datetime import timedelta
import numpy as np

from rqalpha.model.order import Order, LimitOrder
from rqalpha.model.trade import Trade
from rqalpha.environment import Environment
from rqalpha.const import ORDER_STATUS, HEDGE_TYPE, POSITION_EFFECT, SIDE, ORDER_TYPE, COMMISSION_TYPE
from .vnpy import *


SIDE_REVERSE = {
        DIRECTION_LONG: SIDE.BUY,
        DIRECTION_SHORT: SIDE.SELL,
}

SIDE_MAPPING = {
    SIDE.BUY: DIRECTION_LONG,
    SIDE.SELL: DIRECTION_SHORT
}

ORDER_TYPE_MAPPING = {
    ORDER_TYPE.MARKET: PRICETYPE_MARKETPRICE,
    ORDER_TYPE.LIMIT: PRICETYPE_LIMITPRICE
}

POSITION_EFFECT_MAPPING = {
        POSITION_EFFECT.OPEN: OFFSET_OPEN,
        POSITION_EFFECT.CLOSE: OFFSET_CLOSE,
}


def make_underlying_symbol(id_or_symbol):
    return filter(lambda x: x not in '0123456789 ', id_or_symbol).upper()


def make_position_effect(vnpy_exchange, vnpy_offset):
    if vnpy_exchange == EXCHANGE_SHFE:
        if vnpy_offset == OFFSET_OPEN:
            return POSITION_EFFECT.OPEN
        elif vnpy_offset == OFFSET_CLOSETODAY:
            return POSITION_EFFECT.CLOSE_TODAY
        else:
            return POSITION_EFFECT.CLOSE
    else:
        if vnpy_offset == OFFSET_OPEN:
            return POSITION_EFFECT.OPEN
        else:
            return POSITION_EFFECT.CLOSE


def make_order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


def make_trading_dt(calendar_dt):
    # FIXME: 替换为 next_trading_date
    if calendar_dt.hour > 20:
        return calendar_dt + timedelta(days=1)
    return calendar_dt


def make_order(vnpy_order):
    calendar_dt = parse(vnpy_order.orderTime)
    trading_dt = make_trading_dt(calendar_dt)
    order_book_id = make_order_book_id(vnpy_order.symbol)
    quantity = vnpy_order.totalVolume
    side = SIDE_REVERSE[vnpy_order.direction]
    style = LimitOrder(vnpy_order.price)
    position_effect = make_position_effect(vnpy_order.exchange, vnpy_order.offset)

    order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
    order._filled_quantity = vnpy_order.totalVolume

    return order


def make_order_from_vnpy_trade(vnpy_trade):
    calendar_dt = parse(vnpy_trade.tradeTime)
    trading_dt = make_trading_dt(calendar_dt)
    order_book_id = make_order_book_id(vnpy_trade.symbol)
    quantity = vnpy_trade.volume
    side = SIDE_REVERSE[vnpy_trade.direction]
    style = LimitOrder(vnpy_trade.price)
    position_effect = make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)

    order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
    order._filled_quantity = vnpy_trade.volume
    order._status = ORDER_STATUS.FILLED
    order._avg_price = vnpy_trade.price
    order._transaction_cost = 0
    return order


def cal_commission(order_book_id, position_effect, price, amount, hedge_type=HEDGE_TYPE.SPECULATION):
    info = Environment.get_instance().get_future_commission_info(order_book_id, hedge_type)
    commission = 0
    if info['commission_type'] == COMMISSION_TYPE.BY_MONEY:
        contract_multiplier = Environment.get_instance().get_instrument(order_book_id).contract_multiplier
        if position_effect == POSITION_EFFECT.OPEN:
            commission += price * amount * contract_multiplier * info['open_commission_ratio']
        else:
            commission += price * amount * contract_multiplier * info['close_commission_ratio']
    else:
        if position_effect == POSITION_EFFECT.OPEN:
            commission += amount * info['open_commission_ratio']
        else:
            commission += amount * info['close_commission_ratio']
    return commission


def make_trade(vnpy_trade, order_id=None):
    order_id = order_id if order_id is not None else next(Order.order_id_gen)
    calendar_dt = parse(vnpy_trade.tradeTime)
    trading_dt = make_trading_dt(calendar_dt)
    price = vnpy_trade.price
    amount = vnpy_trade.volume
    side = SIDE_REVERSE[vnpy_trade.direction]
    position_effect = make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)
    order_book_id = make_order_book_id(vnpy_trade.symbol)
    commission = cal_commission(order_book_id, position_effect, price, amount)
    frozen_price = vnpy_trade.price

    return Trade.__from_create__(
        order_id, calendar_dt, trading_dt, price, amount, side, position_effect,  order_book_id,
        commission=commission, frozen_price=frozen_price)


def make_tick(vnpy_tick):
    order_book_id = make_order_book_id(vnpy_tick.symbol)
    tick = {
        'order_book_id': order_book_id,
        'datetime': parse('%s %s' % (vnpy_tick.date, vnpy_tick.time)),
        'open': vnpy_tick.openPrice,
        'last': vnpy_tick.lastPrice,
        'low': vnpy_tick.lowPrice,
        'high': vnpy_tick.highPrice,
        'prev_close': vnpy_tick.preClosePrice,
        'volume': vnpy_tick.volume,
        'total_turnover': np.nan,
        'open_interest': vnpy_tick.openInterest,
        'prev_settlement': np.nan,

        'b1': vnpy_tick.bidPrice1,
        'b2': vnpy_tick.bidPrice2,
        'b3': vnpy_tick.bidPrice3,
        'b4': vnpy_tick.bidPrice4,
        'b5': vnpy_tick.bidPrice5,

        'b1_v': vnpy_tick.bidVolume1,
        'b2_v': vnpy_tick.bidVolume2,
        'b3_v': vnpy_tick.bidVolume3,
        'b4_v': vnpy_tick.bidVolume4,
        'b5_v': vnpy_tick.bidVolume5,


        'a1': vnpy_tick.askPrice1,
        'a2': vnpy_tick.askPrice2,
        'a3': vnpy_tick.askPrice3,
        'a4': vnpy_tick.askPrice4,
        'a5': vnpy_tick.askPrice5,

        'a1_v': vnpy_tick.askVolume1,
        'a2_v': vnpy_tick.askVolume2,
        'a3_v': vnpy_tick.askVolume3,
        'a4_v': vnpy_tick.askVolume4,
        'a5_v': vnpy_tick.askVolume5,


        'limit_up': vnpy_tick.upperLimit,
        'limit_down': vnpy_tick.lowerLimit,
    }

    return tick



