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

from dateutil.parser import parse
from datetime import timedelta
from six import iteritems
import numpy as np

from rqalpha.model.order import Order, LimitOrder
from rqalpha.model.trade import Trade
from rqalpha.model.position import Positions
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.model.account.future_account import FutureAccount, margin_of
from rqalpha.environment import Environment
from rqalpha.const import ORDER_STATUS, HEDGE_TYPE, POSITION_EFFECT, SIDE, ORDER_TYPE, COMMISSION_TYPE, MARGIN_TYPE
from .vnpy import EXCHANGE_SHFE, OFFSET_OPEN, OFFSET_CLOSE, OFFSET_CLOSETODAY, DIRECTION_SHORT, DIRECTION_LONG
from .vnpy import STATUS_NOTTRADED, STATUS_PARTTRADED, PRICETYPE_MARKETPRICE, PRICETYPE_LIMITPRICE, CURRENCY_CNY, PRODUCT_FUTURES
from .vnpy import VtOrderReq, VtCancelOrderReq, VtSubscribeReq, VtTradeData, VtOrderData


class DataCache(object):
    def __init__(self):
        self.order_dict = {}
        self.open_order_dict = {}
        self.vnpy_order_dict = {}

        self.order_book_id_symbol_map = {}

        self.contract_cache = {}
        self.snapshot_cache = {}
        self.future_info_cache = {}

        self.account_cache_before_init = {}
        self.position_cache_before_init = {}

        self.order_cache_before_init = []
        self.buy_open_cost_cache_before_init = 0.
        self.sell_open_cost_cache_before_init = 0.


class DataFactory(object):
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

    def __init__(self):
        self._data_cache = DataCache()

    @classmethod
    def make_trading_dt(cls, calendar_dt):
        # FIXME: 替换为 next_trading_date
        if calendar_dt.hour > 20:
            return calendar_dt + timedelta(days=1)
        return calendar_dt

    @classmethod
    def make_underlying_symbol(cls, id_or_symbol):
        return filter(lambda x: x not in '0123456789 ', id_or_symbol).upper()

    # ------------------------------------ vnpy to rqalpha ------------------------------------
    @classmethod
    def make_position_effect(cls, vnpy_exchange, vnpy_offset):
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

    @classmethod
    def make_order_book_id(cls, symbol):
        if len(symbol) < 4:
            return None
        if symbol[-4] not in '0123456789':
            order_book_id = symbol[:2] + '1' + symbol[-3:]
        else:
            order_book_id = symbol
        return order_book_id.upper()

    @classmethod
    def make_order(cls, vnpy_order):
        calendar_dt = parse(vnpy_order.orderTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        order_book_id = cls.make_order_book_id(vnpy_order.symbol)
        quantity = vnpy_order.totalVolume
        side = cls.SIDE_REVERSE[vnpy_order.direction]
        style = LimitOrder(vnpy_order.price)
        position_effect = cls.make_position_effect(vnpy_order.exchange, vnpy_order.offset)

        order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
        order._filled_quantity = vnpy_order.totalVolume

        return order

    @classmethod
    def make_order_from_vnpy_trade(cls, vnpy_trade):
        calendar_dt = parse(vnpy_trade.tradeTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        order_book_id = cls.make_order_book_id(vnpy_trade.symbol)
        quantity = vnpy_trade.volume
        side = cls.SIDE_REVERSE[vnpy_trade.direction]
        style = LimitOrder(vnpy_trade.price)
        position_effect = cls.make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)

        order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
        order._filled_quantity = vnpy_trade.volume
        order._status = ORDER_STATUS.FILLED
        order._avg_price = vnpy_trade.price
        # FIXME: 用近似值代替
        order._transaction_cost = 0
        return order

    @classmethod
    def get_commission(cls, order_book_id, position_effect, price, amount, hedge_type=HEDGE_TYPE.SPECULATION):
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

    @classmethod
    def make_trade(cls, vnpy_trade, order_id=None):
        order_id = order_id if order_id is not None else next(Order.order_id_gen)
        calendar_dt = parse(vnpy_trade.tradeTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        price = vnpy_trade.price
        amount = vnpy_trade.volume
        side = cls.SIDE_REVERSE[vnpy_trade.direction]
        position_effect = cls.make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)
        order_book_id = cls.make_order_book_id(vnpy_trade.symbol)
        commission = cls.get_commission(order_book_id, position_effect, price, amount)
        frozen_price = vnpy_trade.price

        return Trade.__from_create__(
            order_id, calendar_dt, trading_dt, price, amount, side, position_effect,  order_book_id,
            commission=commission, frozen_price=frozen_price)

    @classmethod
    def make_tick(cls, vnpy_tick):
        order_book_id = cls.make_order_book_id(vnpy_tick.symbol)
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

            'bid': [
                vnpy_tick.bidPrice1,
                vnpy_tick.bidPrice2,
                vnpy_tick.bidPrice3,
                vnpy_tick.bidPrice4,
                vnpy_tick.bidPrice5,
            ],
            'bid_volume': [
                vnpy_tick.bidVolume1,
                vnpy_tick.bidVolume2,
                vnpy_tick.bidVolume3,
                vnpy_tick.bidVolume4,
                vnpy_tick.bidVolume5,
            ],
            'ask': [
                vnpy_tick.askPrice1,
                vnpy_tick.askPrice2,
                vnpy_tick.askPrice3,
                vnpy_tick.askPrice4,
                vnpy_tick.askPrice5,
            ],
            'ask_volume': [
                vnpy_tick.askVolume1,
                vnpy_tick.askVolume2,
                vnpy_tick.askVolume3,
                vnpy_tick.askVolume4,
                vnpy_tick.askVolume5,
            ],

            'limit_up': vnpy_tick.upperLimit,
            'limit_down': vnpy_tick.lowerLimit,
        }
        return tick

    # ------------------------------------ rqalpha to vnpy ------------------------------------
    def make_order_req(self, order):
        symbol = self._data_cache.order_book_id_symbol_map.get(order.order_book_id)
        if symbol is None:
            return None
        contract = self._data_cache.contract_cache.get(symbol)
        if contract is None:
            return None

        order_req = VtOrderReq()
        order_req.symbol = contract['symbol']
        order_req.exchange = contract['exchange']
        order_req.price = order.price
        order_req.volume = order.quantity
        order_req.direction = self.SIDE_MAPPING[order.side]
        order_req.priceType = self.ORDER_TYPE_MAPPING[order.type]
        order_req.offset = self.POSITION_EFFECT_MAPPING[order.position_effect]
        order_req.currency = CURRENCY_CNY
        order_req.productClass = PRODUCT_FUTURES

        return order_req

    def make_cancel_order_req(self, order):
        vnpy_order = self._data_cache.vnpy_order_dict.get(order.order_id)
        if vnpy_order is None:
            return
        cancel_order_req = VtCancelOrderReq()
        cancel_order_req.symbol = vnpy_order.symbol
        cancel_order_req.exchange = vnpy_order.exchange
        cancel_order_req.sessionID = vnpy_order.sessionID
        cancel_order_req.orderID = vnpy_order.orderID

        return cancel_order_req

    def make_subscribe_req(self, order_book_id):
        symbol = self._data_cache.order_book_id_symbol_map.get(order_book_id)
        if symbol is None:
            return None
        contract = self._data_cache.contract_cache.get(symbol)
        if contract is None:
            return None
        subscribe_req = VtSubscribeReq()
        subscribe_req.symbol = contract['symbol']
        subscribe_req.exchange = contract['exchange']
        subscribe_req.productClass = PRODUCT_FUTURES
        subscribe_req.currency = CURRENCY_CNY

        return subscribe_req

    def make_positions_before_init(self):
        positions = Positions(FuturePosition)
        for order_book_id, position_dict in iteritems(self._data_cache.position_cache_before_init):
            position = FuturePosition(order_book_id)
            if 'prev_settle_price' in position_dict and 'buy_old_quantity' in position_dict:
                position._buy_old_holding_list = [
                    (position_dict['prev_settle_price'], position_dict['buy_old_quantity'])]
            if 'prev_settle_price' in position_dict and 'sell_old_quantity' in position_dict:
                position._sell_old_holding_list = [
                    (position_dict['prev_settle_price'], position_dict['sell_old_quantity'])]

            if 'buy_transaction_cost' in position_dict:
                position._buy_transaction_cost = position_dict['buy_transaction_cost']
            if 'sell_transaction_cost' in position_dict:
                position._sell_transaction_cost = position_dict['sell_transaction_cost']
            if 'buy_realized_pnl' in position_dict:
                position.__buy_realized_pnl = position_dict['buy_realized_pnl']
            if 'sell_realized_pnl' in position_dict:
                position._sell_realized_pnl = position_dict['sell_realized_pnl']

            if 'buy_avg_open_price' in position_dict:
                position._buy_avg_open_price = position_dict['buy_avg_open_price']
            if 'sell_avg_open_price' in position_dict:
                position._sell_avg_open_price = position_dict['sell_avg_open_price']

            if 'trades' in position_dict:
                accum_buy_open_quantity = 0.
                accum_sell_open_quantity = 0.

                buy_today_quantity = position_dict[
                    'buy_today_quantity'] if 'buy_today_quantity' in position_dict else 0
                sell_today_quantity = position_dict[
                    'sell_today_quantity'] if 'sell_today_quantity' in position_dict else 0

                trades = sorted(position_dict['trades'], key=lambda t: parse(t.tradeTime), reverse=True)

                buy_today_holding_list = []
                sell_today_holding_list = []
                for vnpy_trade in trades:
                    if vnpy_trade.direction == DIRECTION_LONG:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            accum_buy_open_quantity += vnpy_trade.volume
                            if accum_buy_open_quantity == buy_today_quantity:
                                break
                            if accum_buy_open_quantity > buy_today_quantity:
                                buy_today_holding_list.append((vnpy_trade.price,
                                                                buy_today_quantity - accum_buy_open_quantity + vnpy_trade.volume))
                                break
                            buy_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))
                    else:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            accum_sell_open_quantity += vnpy_trade.volume
                            if accum_sell_open_quantity == sell_today_quantity:
                                break
                            if accum_sell_open_quantity > sell_today_quantity:
                                sell_today_holding_list.append((vnpy_trade.price,
                                                                 sell_today_quantity - accum_sell_open_quantity + vnpy_trade.volume))
                                break
                            sell_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))

                position._buy_today_holding_list = buy_today_holding_list
                position._sell_today_holding_list = sell_today_holding_list

            positions[order_book_id] = position
        return positions

    def make_account_before_init(self):
        total_cash = self._data_cache.account_cache_before_init['yesterday_portfolio_value']
        positions = self.make_positions_before_init()

        account = FutureAccount(total_cash, positions)
        frozen_cash = 0.
        for vnpy_order in self._data_cache.order_cache_before_init:
            if vnpy_order.status == STATUS_NOTTRADED or vnpy_order.status == STATUS_PARTTRADED:
                order_book_id = DataFactory.make_order_book_id(vnpy_order.symbol)
                unfilled_quantity = vnpy_order.totalVolume - vnpy_order.tradedVolume
                price = vnpy_order.price
                frozen_cash += margin_of(order_book_id, unfilled_quantity, price)
        account._frozen_cash = frozen_cash
        return account

    # ------------------------------------ put data cache ------------------------------------
    def cache_order(self, vnpy_order_id, order):
        self._data_cache.order_dict[vnpy_order_id] = order

    def cache_open_order(self, vnpy_order_id, order):
        self._data_cache.open_order_dict[vnpy_order_id] = order

    def cache_vnpy_order(self, order_id, vnpy_order):
        self._data_cache.vnpy_order_dict[order_id] = vnpy_order

    def cache_contract(self, contract):
        symbol = contract.symbol
        if symbol not in self._data_cache.contract_cache:
            self._data_cache.contract_cache[symbol] = contract.__dict__
        else:
            self._data_cache.contract_cache[symbol].update(contract.__dict__)

        order_book_id = self.make_order_book_id(symbol)
        self._data_cache.order_book_id_symbol_map[order_book_id] = symbol

        if 'longMarginRatio' in contract.__dict__:
            underlying_symbol = self.make_underlying_symbol(order_book_id)
            if underlying_symbol not in self._data_cache.future_info_cache:
                # hard code
                self._data_cache.future_info_cache[underlying_symbol] = {'speculation': {}}
            self._data_cache.future_info_cache[underlying_symbol]['speculation'].update({
                'long_margin_ratio': contract.longMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })
        if 'shortMarginRatio' in contract.__dict__:
            underlying_symbol = self.make_underlying_symbol(order_book_id)
            if underlying_symbol not in self._data_cache.future_info_cache:
                self._data_cache.future_info_cache[underlying_symbol] = {'speculation': {}}
            self._data_cache.future_info_cache[underlying_symbol]['speculation'].update({
                'short_margin_ratio': contract.shortMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })

    def put_commission(self, commission_data):
        underlying_symbol = self.make_underlying_symbol(commission_data.symbol)
        if commission_data.OpenRatioByMoney == 0 and commission_data.CloseRatioByMoney == 0:
            open_ratio = commission_data.OpenRatioByVolume
            close_ratio = commission_data.CloseRatioByVolume
            close_today_ratio = commission_data.CloseTodayRatioByVolume
            if commission_data.OpenRatioByVolume != 0 or commission_data.CloseRatioByVolume != 0:
                commission_type = COMMISSION_TYPE.BY_VOLUME
            else:
                commission_type = None
        else:
            open_ratio = commission_data.OpenRatioByMoney
            close_ratio = commission_data.CloseRatioByMoney
            close_today_ratio = commission_data.CloseTodayRatioByMoney
            if commission_data.OpenRatioByVolume == 0 and commission_data.CloseRatioByVolume == 0:
                commission_type = COMMISSION_TYPE.BY_MONEY
            else:
                commission_type = None

        if underlying_symbol not in self._data_cache.future_info_cache or \
            'open_commission_ratio' not in self._data_cache.future_info_cache[underlying_symbol]['speculation']:
            self._data_cache.future_info_cache[underlying_symbol] = {'speculation': {}}
            self._data_cache.future_info_cache[underlying_symbol]['speculation'].update({
                'open_commission_ratio': open_ratio,
                'close_commission_ratio': close_ratio,
                'close_commission_today_ratio': close_today_ratio,
                'commission_type': commission_type
            })

    def put_tick_snapshot(self, tick):
        order_book_id = tick['order_book_id']
        self._data_cache.snapshot_cache[order_book_id] = tick

    def cache_vnpy_order_before_init(self, vnpy_order):
        self._data_cache.order_cache_before_init.append(vnpy_order)

    def cache_vnpy_trade_before_init(self, vnpy_trade):
        order_book_id = self.make_order_book_id(vnpy_trade.symbol)
        if order_book_id not in self._data_cache.position_cache_before_init:
            self._data_cache.position_cache_before_init[order_book_id] = {}
        if 'trades' not in self._data_cache.position_cache_before_init[order_book_id]:
            self._data_cache.position_cache_before_init[order_book_id]['trades'] = []
            self._data_cache.position_cache_before_init[order_book_id]['trades'].append(vnpy_trade)

    def cache_vnpy_account_before_init(self, vnpy_account):
        if 'preBalance' in vnpy_account.__dict__:
            self._data_cache.account_cache_before_init['yesterday_portfolio_value'] = vnpy_account.preBalance

    def cache_vnpy_position_before_init(self, vnpy_position):
        order_book_id = self.make_order_book_id(vnpy_position.symbol)

        if order_book_id not in self._data_cache.position_cache_before_init:
            self._data_cache.position_cache_before_init[order_book_id] = {}

        if vnpy_position.direction == DIRECTION_LONG:
            if 'position' in vnpy_position.__dict__:
                self._data_cache.position_cache_before_init[order_book_id]['buy_old_quantity'] = vnpy_position.ydPosition
                self._data_cache.position_cache_before_init[order_book_id]['buy_quantity'] = vnpy_position.position
                self._data_cache.position_cache_before_init[order_book_id][
                    'buy_today_quantity'] = vnpy_position.position - vnpy_position.ydPosition
            if 'commission' in vnpy_position.__dict__:
                if 'buy_transaction_cost' not in self._data_cache.position_cache_before_init[order_book_id]:
                    self._data_cache.position_cache_before_init[order_book_id]['buy_transaction_cost'] = 0.
                self._data_cache.position_cache_before_init[order_book_id]['buy_transaction_cost'] += vnpy_position.commission
            if 'closeProfit' in vnpy_position.__dict__:
                if 'buy_realized_pnl' not in self._data_cache.position_cache_before_init[order_book_id]:
                    self._data_cache.position_cache_before_init[order_book_id]['buy_realized_pnl'] = 0.
                self._data_cache.position_cache_before_init[order_book_id]['buy_realized_pnl'] += vnpy_position.closeProfit
            if 'openCost' in vnpy_position.__dict__:
                self._data_cache.buy_open_cost_cache_before_init += vnpy_position.openCost
                contract = self._data_cache.contract_cache.get(vnpy_position.symbol)
                if contract is not None:
                    contract_multiplier = contract['size']
                    buy_quantity = self._data_cache.position_cache_before_init[order_book_id]['buy_quantity']
                    self._data_cache.position_cache_before_init[order_book_id]['buy_avg_open_price'] =\
                        self._data_cache.buy_open_cost_cache_before_init / (buy_quantity * contract_multiplier)\
                        if buy_quantity != 0 else 0

        elif vnpy_position.direction == DIRECTION_SHORT:
            if 'position' in vnpy_position.__dict__:
                self._data_cache.position_cache_before_init[order_book_id]['sell_old_quantity'] = vnpy_position.ydPosition
                self._data_cache.position_cache_before_init[order_book_id]['sell_position'] = vnpy_position.position
                self._data_cache.position_cache_before_init[order_book_id][
                    'sell_today_quantity'] = vnpy_position.position - vnpy_position.ydPosition
            if 'commission' in vnpy_position.__dict__:
                if 'sell_transaction_cost' not in self._data_cache.position_cache_before_init[order_book_id]:
                    self._data_cache.position_cache_before_init[order_book_id]['sell_transaction_cost'] = 0.
                self._data_cache.position_cache_before_init[order_book_id]['sell_transaction_cost'] += vnpy_position.commission
            if 'closeProfit' in vnpy_position.__dict__:
                if 'sell_realized_pnl' not in self._data_cache.position_cache_before_init[order_book_id]:
                    self._data_cache.position_cache_before_init[order_book_id]['sell_realized_pnl'] = 0.
                self._data_cache.position_cache_before_init[order_book_id]['sell_realized_pnl'] += vnpy_position.closeProfit
            if 'openCost' in vnpy_position.__dict__:
                self._data_cache.sell_open_cost_cache_before_init += vnpy_position.openCost
                contract = self._data_cache.contract_cache.get(vnpy_position.symbol)
                if contract is not None:
                    contract_multiplier = contract['size']
                    sell_quantity = self._data_cache.position_cache_before_init[order_book_id]['sell_quantity']
                    self._data_cache.position_cache_before_init[order_book_id]['sell_avg_open_price'] =\
                        self._data_cache.sell_open_cost_cache_before_init / (sell_quantity * contract_multiplier)\
                        if sell_quantity != 0 else 0

        if 'preSettlementPrice' in vnpy_position.__dict__:
            self._data_cache.position_cache_before_init[order_book_id]['prev_settle_price'] = vnpy_position.preSettlementPrice

    # ------------------------------------ read data cache ------------------------------------
    def get_order(self, vnpy_order_or_trade):
        order = self._data_cache.order_dict.get(vnpy_order_or_trade.vtOrderID)
        if order is None:
            if isinstance(vnpy_order_or_trade, VtTradeData):
                order = self.make_order_from_vnpy_trade(vnpy_order_or_trade)
            if isinstance(vnpy_order_or_trade, VtOrderData):
                order = self.make_order(vnpy_order_or_trade)
        return order

    def get_open_orders(self, order_book_id):
        if order_book_id is None:
            return list(self._data_cache.open_order_dict.values())
        else:
            return [order for order in self._data_cache.open_order_dict.values() if order.order_book_id == order_book_id]

    def del_open_order(self, vnpy_order_id):
        if vnpy_order_id in self._data_cache.open_order_dict:
            del self._data_cache.open_order_dict[vnpy_order_id]

    def get_symbol(self, order_book_id):
        return self._data_cache.order_book_id_symbol_map.get(order_book_id)

    def get_future_info(self, order_book_id, hedge_flag='speculation'):
        underlying_symbol = self.make_underlying_symbol(order_book_id)
        if underlying_symbol not in self._data_cache.future_info_cache:
            return None
        if hedge_flag not in self._data_cache.future_info_cache[underlying_symbol]:
            return None
        return self._data_cache.future_info_cache[underlying_symbol][hedge_flag]

    def get_tick_snapshot(self, order_book_id):
        return self._data_cache.snapshot_cache.get(order_book_id)

    def get_contract_cache(self):
        return self._data_cache.contract_cache
