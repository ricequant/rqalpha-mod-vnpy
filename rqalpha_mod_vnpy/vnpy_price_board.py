# -*- coding: utf-8 -*-
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
