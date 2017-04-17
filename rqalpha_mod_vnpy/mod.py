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

from time import sleep
from rqalpha.interface import AbstractMod

vn_trader_path = None


class VNPYMod(AbstractMod):
    def __init__(self):
        self._env = None
        self._engine = None
        self._data_factory = None
        self._event_engine = None

    def start_up(self, env, mod_config):
        global vn_trader_path
        vn_trader_path = mod_config.vn_trader_path
        from .data_factory import DataFactory
        from .vnpy_engine import RQVNPYEngine
        from .vnpy_event_source import VNPYEventSource
        from .vnpy_broker import VNPYBroker
        from .vnpy_data_source import VNPYDataSource
        from .vnpy_price_board import VNPYPriceBoard
        from .vnpy_gateway import RQVNEventEngine
        self._data_factory = DataFactory()
        self._env = env
        self._event_engine = RQVNEventEngine()
        self._engine = RQVNPYEngine(env, mod_config, self._data_factory, self._event_engine)
        self._engine.connect()
        sleep(2)
        self._engine._account_inited = True
        # self._engine.connect()
        self._env.set_broker(VNPYBroker(self._engine))
        self._env.set_event_source(VNPYEventSource(env, mod_config, self._engine))
        self._env.set_data_source(VNPYDataSource(env, self._data_factory))
        self._env.set_price_board(VNPYPriceBoard(self._data_factory))

    def tear_down(self, code, exception=None):
        self._engine.exit()
