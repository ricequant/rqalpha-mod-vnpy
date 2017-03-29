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


class VNPYMod(AbstractMod):
    def __init__(self):
        self._engine = None

    def start_up(self, env, mod_config):
        import sys
        sys.path.append(mod_config.vn_trader_path)
        from .data_factory import DataFactory
        from .vnpy_engine import RQVNPYEngine, EVENT_ENGINE_CONNECT
        from .vnpy_event_source import VNPYEventSource
        from .vnpy_broker import VNPYBroker
        from .vnpy_data_source import VNPYDataSource
        from .vnpy_price_board import VNPYPriceBoard
        from .vnpy_gateway import RQVNEventEngine
        from .vnpy import Event

        data_factory = DataFactory()
        event_engine = RQVNEventEngine()
        event_engine.put(Event(type_=EVENT_ENGINE_CONNECT))
        self._engine = RQVNPYEngine(env, mod_config, data_factory, event_engine)

        sleep(10)

        self._engine._account_inited = True
        # self._engine.connect()
        env.set_broker(VNPYBroker(self._engine))
        env.set_event_source(VNPYEventSource(env, mod_config, self._engine))
        env.set_data_source(VNPYDataSource(env, data_factory))
        env.set_price_board(VNPYPriceBoard(data_factory))

    def tear_down(self, code, exception=None):
        self._engine.exit()
