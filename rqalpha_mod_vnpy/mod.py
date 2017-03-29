# -*- coding: utf-8 -*-
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
        from .vnpy_engine import RQVNPYEngine, EVENT_ENGINE_CONNECT
        from .vnpy_event_source import VNPYEventSource
        from .vnpy_broker import VNPYBroker
        from .vnpy_data_source import VNPYDataSource
        from .vnpy_price_board import VNPYPriceBoard
        from .vnpy_gateway import RQVNEventEngine
        from .vnpy import Event
        self._data_factory = DataFactory()
        self._env = env
        self._event_engine = RQVNEventEngine()
        self._engine = RQVNPYEngine(env, mod_config, self._data_factory, self._event_engine)
        self._event_engine.put(Event(type_=EVENT_ENGINE_CONNECT))
        while True:
            if self._engine.account_inited:
                break

        # self._engine.connect()
        self._env.set_broker(VNPYBroker(self._engine))
        self._env.set_event_source(VNPYEventSource(env, mod_config, self._engine))
        self._env.set_data_source(VNPYDataSource(env, self._data_factory))
        self._env.set_price_board(VNPYPriceBoard(self._data_factory))

    def tear_down(self, code, exception=None):
        self._engine.exit()
