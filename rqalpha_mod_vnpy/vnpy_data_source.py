# -*- coding: utf-8 -*-
from rqalpha.data.base_data_source import BaseDataSource
from rqalpha.model.snapshot import SnapshotObject
from datetime import date


class VNPYDataSource(BaseDataSource):
    def __init__(self, env, vnpy_engine):
        path = env.config.base.data_bundle_path
        super(VNPYDataSource, self).__init__(path)
        self._engine = vnpy_engine

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

    # TODO: 增加get_all_instruments()，从CTP获取合约信息
