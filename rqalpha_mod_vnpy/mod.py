# -*- coding: utf-8 -*-
from rqalpha.interface import AbstractMod
from rqalpha.events import EVENT

from .vnpy_engine import RQVNPYEngine
from .vnpy_event_source import VNPYEventSource
from .vnpy_broker import VNPYBroker
from .vnpy_data_source import VNPYDataSource
from .data_cache import DataCache


class VNPYMod(AbstractMod):
    def __init__(self):
        self._env = None
        self._engine = None
        self._data_cache = DataCache()

    def init_engine(self, event):
        self._engine.init_account()
        self._engine.wait_until_account_inited()

    def start_up(self, env, mod_config):
        self._env = env
        self._engine = RQVNPYEngine(env, mod_config, self._data_cache)
        self._engine.connect()
        self._env.set_broker(VNPYBroker(env, self._engine))
        self._env.set_event_source(VNPYEventSource(env, self._engine))
        self._env.set_data_source(VNPYDataSource(env, self._data_cache))
        # self._engine.do_init()
        self._env.event_bus.add_listener(EVENT.POST_SYSTEM_INIT, self.init_engine)

    def tear_down(self, code, exception=None):
        self._engine.exit()
