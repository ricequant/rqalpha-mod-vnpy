from rqalpha.utils.logger import system_log
from rqalpha.const import COMMISSION_TYPE, MARGIN_TYPE

from .utils import symbol_2_order_book_id


def _underlying_symbol(id_or_symgol):
    return filter(lambda x: x not in '0123456789 ', id_or_symgol).upper()


class DataCache(object):
    def __init__(self):
        self._order_dict = {}
        self._vnpy_order_dict = {}
        self._open_order_dict = {}

        self._order_book_id_symbol_map = {}

        self._contract_dict = {}
        self._contract_cache = {}

        self._tick_snapshot_dict = {}

        self._future_info_cache = {}

    @property
    def open_orders(self):
        return list(self._open_order_dict.values())

    def put_order(self, vnpy_order_id, order):
        self._order_dict[vnpy_order_id] = order

    def put_open_order(self, vnpy_order_id, order):
        self._open_order_dict[vnpy_order_id] = order

    def put_vnpy_order(self, order_id, vnpy_order):
        self._vnpy_order_dict[order_id] = vnpy_order

    def put_contract_or_extra(self, contract_or_extra):
        symbol = contract_or_extra.symbol
        if symbol not in self._contract_cache:
            self._contract_cache[symbol] = contract_or_extra.__dict__
        else:
            self._contract_cache[symbol].update(contract_or_extra.__dict__)
        order_book_id = symbol_2_order_book_id(symbol)
        self._order_book_id_symbol_map[order_book_id] = symbol
        if 'longMarginRatio' in contract_or_extra.__dict__:
            underlying_symbol = _underlying_symbol(order_book_id)
            if underlying_symbol not in self._future_info_cache:
                # hard code
                self._future_info_cache[underlying_symbol] = {'speculation': {}}
            self._future_info_cache[underlying_symbol]['speculation'].update({
                'long_margin_ratio': contract_or_extra.longMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })
        if 'shortMarginRatio' in contract_or_extra.__dict__:
            underlying_symbol = _underlying_symbol(order_book_id)
            if underlying_symbol not in self._future_info_cache:
                self._future_info_cache[underlying_symbol] = {'speculation': {}}
            self._future_info_cache[underlying_symbol]['speculation'].update({
                'short_margin_ratio': contract_or_extra.shortMarginRatio,
                'margin_type': MARGIN_TYPE.BY_MONEY,
            })

    def put_commission(self, commission_data):
        underlying_symbol = _underlying_symbol(commission_data.symbol)
        if commission_data.OpenRatioByMoney == 0 and commission_data.CloseRatioByMoney == 0:
            open_ratio = commission_data.OpenRatioByVolume
            close_ratio = commission_data.CloseRatioByVolume
            close_today_ratio = commission_data.CloseTodayRatioByVolume
            if commission_data.OpenRatioByVolume != 0 or commission_data.CloseRatioByVolume != 0:
                commission_type = COMMISSION_TYPE.BY_VOLUME
            else:
                commission_type = None
        else:
            open_ratio = commission_data.OpenRatioByMoney
            close_ratio = commission_data.CloseRatioByMoney
            close_today_ratio = commission_data.CloseTodayRatioByMoney
            if commission_data.OpenRatioByVolume == 0 and commission_data.CloseRatioByVolume == 0:
                commission_type = COMMISSION_TYPE.BY_MONEY
            else:
                commission_type = None

        if underlying_symbol not in self._future_info_cache:
            self._future_info_cache[underlying_symbol] = {'speculation': {}}
        self._future_info_cache[underlying_symbol]['speculation'].update({
            'open_commission_ratio': open_ratio,
            'close_commission_ratio': close_ratio,
            'close_commission_today_ratio': close_today_ratio,
            'commission_type': commission_type
        })

    def del_open_order(self, vnpy_order_id):
        if vnpy_order_id in self._open_order_dict:
            del self._open_order_dict[vnpy_order_id]

    def get_symbol(self, order_book_id):
        return self._order_book_id_symbol_map.get(order_book_id)

    def get_order(self, vnpy_order_id):
        try:
            return self._order_dict[vnpy_order_id]
        except KeyError:
            return

    def get_vnpy_order(self, order_id):
        try:
            return self._vnpy_order_dict[order_id]
        except KeyError:
            return

    def get_contract(self, symbol):
        try:
            return self._contract_cache[symbol]
        except KeyError:
            system_log.error('Cannot find such contract whose order_book_id is {} ', symbol)

    def get_future_info(self, order_book_id, hedge_flag='speculation'):
        underlying_symbol = _underlying_symbol(order_book_id)
        if underlying_symbol not in self._future_info_cache:
            return None
        if hedge_flag not in self._future_info_cache[underlying_symbol]:
            return None
        return self._future_info_cache[underlying_symbol][hedge_flag]

    def put_tick_snapshot(self, tick):
        order_book_id = tick['order_book_id']
        self._tick_snapshot_dict[order_book_id] = tick

    def get_tick_snapshot(self, order_book_id):
        try:
            return self._tick_snapshot_dict[order_book_id]
        except KeyError:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
            return None

