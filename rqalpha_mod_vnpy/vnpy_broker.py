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

from rqalpha.interface import AbstractBroker
from rqalpha.environment import Environment
from rqalpha.model.account import BenchmarkAccount, FutureAccount
from rqalpha.const import ACCOUNT_TYPE


def init_accounts(env):
    # FIXME: 从ctp获取获取账户信息，持仓等
    accounts = {}
    config = env.config
    start_date = config.base.start_date
    total_cash = 0
    future_starting_cash = config.base.future_starting_cash
    accounts[ACCOUNT_TYPE.FUTURE] = FutureAccount(env, future_starting_cash, start_date)
    if config.base.benchmark is not None:
        accounts[ACCOUNT_TYPE.BENCHMARK] = BenchmarkAccount(env, total_cash, start_date)

    return accounts


class VNPYBroker(AbstractBroker):
    def __init__(self, gateway):
        self._gateway = gateway
        self._open_orders = []

    def after_trading(self):
        pass

    def before_trading(self):
        self._gateway.connect_and_sync_data()
        for account, order in self._open_orders:
            order.active()
            self._env.event_bus.publish_event(Event(EVENT.ORDER_CREATION_PASS, account=account, order=order))

    def get_open_orders(self, order_book_id=None):
        if order_book_id is not None:
            return [order for order in self._gateway.open_orders if order.order_book_id == order_book_id]
        else:
            return self._gateway.open_orders

    def submit_order(self, order):
        self._gateway.submit_order(order)

    def cancel_order(self, order):
        self._gateway.cancel_order(order)

    def update(self, calendar_dt, trading_dt, bar_dict):
        pass

    def get_portfolio(self):
        return self._gateway.get_portfolio()

    def get_benchmark_portfolio(self):
        return None
