from rqalpha.interface import AbstractPriceBoard


class VNPYPriceBoard(AbstractPriceBoard):
    def __init__(self, data_cache):
        self._data_cache = data_cache

    def get_last_price(self, order_book_id):
        return self._data_cache.get_tick_snapshot(order_book_id)['last']
