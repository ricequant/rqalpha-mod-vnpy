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

import six

from dateutil.parser import parse
from six import iteritems

from rqalpha.model.position import Positions
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.model.account.future_account import FutureAccount, margin_of
from rqalpha.const import COMMISSION_TYPE, MARGIN_TYPE
from .vnpy import OFFSET_OPEN, DIRECTION_SHORT, DIRECTION_LONG
from .vnpy import STATUS_NOTTRADED, STATUS_PARTTRADED, CURRENCY_CNY, PRODUCT_FUTURES
from .vnpy import VtOrderReq, VtCancelOrderReq, VtSubscribeReq, VtTradeData, VtOrderData
from .vnpy_gateway import RQOrderReq
from .utils import make_underlying_symbol, make_order_book_id, make_order
from .utils import make_order_from_vnpy_trade
from .utils import SIDE_MAPPING, ORDER_TYPE_MAPPING, POSITION_EFFECT_MAPPING


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


class DataFactory(object):
    def __init__(self):
        self._data_cache = DataCache()

    # ------------------------------------ rqalpha to vnpy ------------------------------------
    def make_order_req(self, order):
        symbol = self._data_cache.order_book_id_symbol_map.get(order.order_book_id)
        if symbol is None:
            return None
        contract = self._data_cache.contract_cache.get(symbol)
        if contract is None:
            return None

        order_req = RQOrderReq()
        order_req.symbol = contract['symbol']
        order_req.exchange = contract['exchange']
        order_req.price = order.price
        order_req.volume = order.quantity
        order_req.direction = SIDE_MAPPING[order.side]
        order_req.priceType = ORDER_TYPE_MAPPING[order.type]
        order_req.offset = POSITION_EFFECT_MAPPING[order.position_effect]
        order_req.currency = CURRENCY_CNY
        order_req.productClass = PRODUCT_FUTURES

        order_req.orderID = order.order_id

        return order_req

    def make_cancel_order_req(self, order):
        symbol = self._data_cache.order_book_id_symbol_map.get(order.order_book_id)
        contract = self._data_cache.contract_cache.get(symbol)
        cancel_order_req = VtCancelOrderReq()
        cancel_order_req.symbol = symbol
        cancel_order_req.exchange = contract['exchange']
        cancel_order_req.orderID = order.order_id
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

                buy_today_quantity = position_dict[
                    'buy_today_quantity'] if 'buy_today_quantity' in position_dict else 0
                sell_today_quantity = position_dict[
                    'sell_today_quantity'] if 'sell_today_quantity' in position_dict else 0

                trades = sorted(position_dict['trades'], key=lambda t: t.tradeID, reverse=True)
                buy_today_holding_list = []
                sell_today_holding_list = []

                for vnpy_trade in trades:
                    if vnpy_trade.direction == DIRECTION_LONG:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            buy_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))
                    else:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            sell_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))

                self.process_today_holding_list(buy_today_quantity, buy_today_holding_list)
                self.process_today_holding_list(sell_today_quantity, sell_today_holding_list)
                position._buy_today_holding_list = buy_today_holding_list
                position._sell_today_holding_list = sell_today_holding_list

            positions[order_book_id] = position

        return positions

    def make_account_before_init(self):
        static_value = self._data_cache.account_cache_before_init['yesterday_portfolio_value']
        positions = self.make_positions_before_init()
        holding_pnl = sum(position.holding_pnl for position in six.itervalues(positions))
        realized_pnl = sum(position.realized_pnl for position in six.itervalues(positions))
        cost = sum(position.transaction_cost for position in six.itervalues(positions))
        margin = sum(position.margin for position in six.itervalues(positions))
        total_cash = static_value + holding_pnl + realized_pnl - cost - margin

        account = FutureAccount(total_cash, positions)
        frozen_cash = 0.
        for vnpy_order in self._data_cache.order_cache_before_init:
            if vnpy_order.status == STATUS_NOTTRADED or vnpy_order.status == STATUS_PARTTRADED:
                order_book_id = make_order_book_id(vnpy_order.symbol)
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

        order_book_id = make_order_book_id(symbol)
        self._data_cache.order_book_id_symbol_map[order_book_id] = symbol

        if 'longMarginRatio' in contract.__dict__:
            underlying_symbol = make_underlying_symbol(order_book_id)
            if underlying_symbol not in self._data_cache.future_info_cache:
                # hard code
                self._data_cache.future_info_cache[underlying_symbol] = {'speculation': {}}
            self._data_cache.future_info_cache[underlying_symbol]['speculation'].update({
                'long_margin_ratio': contract.longMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })
        if 'shortMarginRatio' in contract.__dict__:
            underlying_symbol = make_underlying_symbol(order_book_id)
            if underlying_symbol not in self._data_cache.future_info_cache:
                self._data_cache.future_info_cache[underlying_symbol] = {'speculation': {}}
            self._data_cache.future_info_cache[underlying_symbol]['speculation'].update({
                'short_margin_ratio': contract.shortMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })

    def put_commission(self, commission_dict):
        for underlying_symbol, commission_data in iteritems(commission_dict):
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
        order_book_id = make_order_book_id(vnpy_trade.symbol)
        if order_book_id not in self._data_cache.position_cache_before_init:
            self._data_cache.position_cache_before_init[order_book_id] = {}
        if 'trades' not in self._data_cache.position_cache_before_init[order_book_id]:
            self._data_cache.position_cache_before_init[order_book_id]['trades'] = []
        self._data_cache.position_cache_before_init[order_book_id]['trades'].append(vnpy_trade)

    def cache_vnpy_account_before_init(self, vnpy_account):
        if 'preBalance' in vnpy_account.__dict__:
            self._data_cache.account_cache_before_init['yesterday_portfolio_value'] = vnpy_account.preBalance

    def cache_vnpy_position(self, vnpy_position):
        order_book_id = make_order_book_id(vnpy_position.symbol)

        if order_book_id not in self._data_cache.position_cache_before_init:
            self._data_cache.position_cache_before_init[order_book_id] = {}

        if vnpy_position.direction == DIRECTION_LONG:
            self._data_cache.position_cache_before_init[order_book_id]['buy_old_quantity'] = vnpy_position.ydPosition
            self._data_cache.position_cache_before_init[order_book_id]['buy_quantity'] = vnpy_position.position
            self._data_cache.position_cache_before_init[order_book_id]['buy_today_quantity'] = vnpy_position.todayPosition
            self._data_cache.position_cache_before_init[order_book_id]['buy_transaction_cost'] = vnpy_position.commission
            self._data_cache.position_cache_before_init[order_book_id]['buy_realized_pnl'] = vnpy_position.closeProfit
            self._data_cache.position_cache_before_init[order_book_id]['buy_avg_open_price'] = vnpy_position.avgOpenPrice

        elif vnpy_position.direction == DIRECTION_SHORT:
            self._data_cache.position_cache_before_init[order_book_id]['sell_old_quantity'] = vnpy_position.ydPosition
            self._data_cache.position_cache_before_init[order_book_id]['sell_quantity'] = vnpy_position.position
            self._data_cache.position_cache_before_init[order_book_id]['sell_today_quantity'] = vnpy_position.todayPosition
            self._data_cache.position_cache_before_init[order_book_id]['sell_transaction_cost'] = vnpy_position.commission
            self._data_cache.position_cache_before_init[order_book_id]['sell_realized_pnl'] = vnpy_position.closeProfit
            self._data_cache.position_cache_before_init[order_book_id]['sell_avg_open_price'] = vnpy_position.avgOpenPrice

        if 'preSettlementPrice' in vnpy_position.__dict__:
            self._data_cache.position_cache_before_init[order_book_id]['prev_settle_price'] = vnpy_position.preSettlementPrice

    # ------------------------------------ read data cache ------------------------------------
    def get_order(self, vnpy_order_or_trade):
        order = self._data_cache.order_dict.get(vnpy_order_or_trade.vtOrderID)
        if order is None:
            if isinstance(vnpy_order_or_trade, VtTradeData):
                order = make_order_from_vnpy_trade(vnpy_order_or_trade)
            if isinstance(vnpy_order_or_trade, VtOrderData):
                order = make_order(vnpy_order_or_trade)
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
        underlying_symbol = make_underlying_symbol(order_book_id)
        if underlying_symbol not in self._data_cache.future_info_cache:
            return None
        if hedge_flag not in self._data_cache.future_info_cache[underlying_symbol]:
            return None
        return self._data_cache.future_info_cache[underlying_symbol][hedge_flag]

    def get_tick_snapshot(self, order_book_id):
        return self._data_cache.snapshot_cache.get(order_book_id)

    def get_contract_cache(self):
        return self._data_cache.contract_cache

    def process_today_holding_list(self, today_quantity, holding_list):
        # check if list is empty
        if not holding_list:
            return
        cum_quantity = sum(quantity for price, quantity in holding_list)
        left_quantity = cum_quantity - today_quantity
        while left_quantity > 0:
            oldest_price, oldest_quantity = holding_list.pop()
            if oldest_quantity > left_quantity:
                consumed_quantity = left_quantity
                holding_list.append(oldest_price, oldest_quantity - left_quantity)
            else:
                consumed_quantity = oldest_quantity
            left_quantity -= consumed_quantity

