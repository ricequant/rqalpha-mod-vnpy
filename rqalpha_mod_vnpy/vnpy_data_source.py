# -*- coding: utf-8 -*-
from rqalpha.data.base_data_source import BaseDataSource
from rqalpha.model.snapshot import SnapshotObject
from datetime import date

from .data_factory import RQVNInstrument


class InstrumentStore(object):
    def __init__(self, vnpy_engine):
        all_contract_dict = vnpy_engine.get_all_contract_dict()
        self._instruments = [RQVNInstrument(i) for i in all_contract_dict.values()]

    def get_all_instruments(self):
        return self._instruments


class VNPYDataSource(BaseDataSource):
    def __init__(self, env, vnpy_engine):
        path = env.config.base.data_bundle_path
        super(VNPYDataSource, self).__init__(path)
        self._engine = vnpy_engine

        # 将来可替换默认的instrument
        self._instruments = InstrumentStore(vnpy_engine)

    def current_snapshot(self, instrument, frequency, dt):
        if frequency != 'tick':
            raise NotImplementedError

        order_book_id = instrument.order_book_id
        return SnapshotObject(instrument, self._engine.get_tick_snapshot(order_book_id), dt)

    def available_data_range(self, frequency):
        if frequency != 'tick':
            raise NotImplementedError
        s = date.today()
        e = date.fromtimestamp(2147483647)
        return s, e

