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

from rqalpha.data.base_data_source import BaseDataSource
from rqalpha.model.snapshot import SnapshotObject
from rqalpha.utils.logger import system_log
from datetime import date


class VNPYDataSource(BaseDataSource):
    def __init__(self, env, data_factory):
        path = env.config.base.data_bundle_path
        super(VNPYDataSource, self).__init__(path)
        self._data_factory = data_factory

    def current_snapshot(self, instrument, frequency, dt):
        if frequency != 'tick':
            raise NotImplementedError

        order_book_id = instrument.order_book_id
        tick_snapshot = self._data_factory.get_tick_snapshot(order_book_id)
        if tick_snapshot is None:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
        return SnapshotObject(instrument, tick_snapshot, dt)

    def available_data_range(self, frequency):
        if frequency != 'tick':
            raise NotImplementedError
        s = date.today()
        e = date.fromtimestamp(2147483647)
        return s, e

    def get_future_info(self, instrument, hedge_type):
        order_book_id = instrument.order_book_id
        hedge_flag = hedge_type.value
        return self._data_factory.get_future_info(order_book_id, hedge_flag)
