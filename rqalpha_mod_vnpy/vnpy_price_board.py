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

from rqalpha.interface import AbstractPriceBoard
from rqalpha.utils.logger import system_log


class VNPYPriceBoard(AbstractPriceBoard):
    def __init__(self, data_factory):
        self._data_factory = data_factory

    def get_last_price(self, order_book_id):
        tick_snapshot = self._data_factory.get_tick_snapshot(order_book_id)
        if tick_snapshot is None:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
            return
        return tick_snapshot['last']

    def get_limit_up(self, order_book_id):
        tick_snapshot = self._data_factory.get_tick_snapshot(order_book_id)
        if tick_snapshot is None:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
            return
        return tick_snapshot['limit_up']

    def get_limit_down(self, order_book_id):
        tick_snapshot = self._data_factory.get_tick_snapshot(order_book_id)
        if tick_snapshot is None:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
            return
        return tick_snapshot['limit_down']
