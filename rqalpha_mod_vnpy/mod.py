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

from queue import Queue
from importlib import import_module
from typing import Optional, Dict

from vnpy.event import EventEngine as VNEventEngine
from vnpy.trader.gateway import BaseGateway as VNBaseGateway

from rqalpha.const import RUN_TYPE
from rqalpha.core.events import EVENT
from rqalpha.utils.logger import system_log
from rqalpha.interface import AbstractMod

from .event_source import EventSource
from .broker import Broker
from .consts import ACCOUNT_TYPE


class VNPYMod(AbstractMod):
    def __init__(self):
        self._env = None
        self._vn_gateways: Dict[ACCOUNT_TYPE, VNBaseGateway] = {}
        self._vn_gateway_settings: Dict[ACCOUNT_TYPE, Dict] = {}
        self._vn_event_engine: Optional[VNEventEngine] = None

    def start_up(self, env, mod_config):
        if not mod_config.gateways:
            system_log.info("未设置 gateways，rqalpha-mod-vnpy 关闭")
            return
        if env.config.base.run_type != RUN_TYPE.LIVE_TRADING:
            system_log.info("未以实盘模式运行，rqalpha-mod-vnpy 关闭")

        self._vn_event_engine = VNEventEngine()
        for account_type, gateway_config in mod_config.gateways.items():
            gateway_app = gateway_config["app"]
            module_path, cls_name = gateway_app.split(":")
            gateway_cls = getattr(import_module(module_path), cls_name)
            if not issubclass(gateway_cls, VNBaseGateway):
                raise ValueError(f"{gateway_app} is not a VN.PY BaseGateway")
            account_type = account_type.upper()
            self._vn_gateways[account_type] = gateway_cls(self._vn_event_engine, gateway_app.get("name", cls_name))
            self._vn_gateway_settings[account_type] = gateway_config["settings"]

        rqa_event_queue = Queue()
        self._env.set_broker(Broker(env, rqa_event_queue, self._vn_event_engine, self._vn_gateways))
        self._env.set_event_source(EventSource(env, rqa_event_queue, self._vn_event_engine, self._vn_gateways))

        self._env.event_bus.add(EVENT.POST_SYSTEM_INIT, self._post_system_init)

    def _post_system_init(self, _):
        self._vn_event_engine.start()
        for account_type, vn_gateway in self._vn_gateways.items():
            vn_gateway.connect(self._vn_gateway_settings[account_type])

    def tear_down(self, code, exception=None):
        for vn_gateway in self._vn_gateways.values():
            vn_gateway.close()
        if self._vn_event_engine:
            self._vn_event_engine.stop()
