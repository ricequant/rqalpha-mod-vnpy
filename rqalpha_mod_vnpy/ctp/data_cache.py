import six

from rqalpha.model.position import Positions
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.model.account.future_account import FutureAccount, margin_of
from rqalpha.const import SIDE, POSITION_EFFECT


class TdDataCache(object):
    def __init__(self):
        self._ins_cache = {}
        self._future_info_cache = {}
        self._account_dict = {}
        self._pos_cache = {}
        self._trade_cache = {}
        self._order_cache = {}

        self._snapshot_cache = {}

    def cache_ins(self, ins_cache):
        self._ins_cache = ins_cache
        self._future_info_cache = {ins_dict.underlying_symbol: {'speculation': {
                'long_margin_ratio': ins_dict.long_margin_ratio,
                'short_margin_ratio': ins_dict.short_margin_ratio,
                'margin_type': ins_dict.margin_type,
            }} for ins_dict in self._ins_cache.values()}

    def cache_commission(self, commission_cache):
        for underlying_symbol, commission_dict in six.iteritems(commission_cache):
            self._future_info_cache[underlying_symbol]['speculation'].update({
                'open_commission_ratio': commission_dict.open_ratio,
                'close_commission_ratio': commission_dict.close_ratio,
                'close_commission_today_ratio': commission_dict.close_today_ratiom
                'commission_type': commission_dict.commission_type,
            })

    def cache_position(self, pos_cache):
        self._pos_cache = pos_cache

    def cache_account(self, account_dict):
        self._account_dict = account_dict

    def cache_order(self, order_cache):
        self._order_cache = order_cache

    def cache_snapshot(self, tick_dict):
        self._snapshot_cache[tick_dict.order_book_id] = tick

    @property
    def ins(self):
        return self._ins_cache

    @property
    def positions(self):
        ps = Positions(FuturePosition)
        for order_book_id, pos_dict in self._positions:
            position = FuturePosition(order_book_id)

            position._buy_old_holding_list = [(pos_dict.prev_settle_price, pos_dict.buy_old_quantity)]
            position._sell_old_holding_list = [(pos_dict.prev_settle_price, pos_dict.sell_old_quantity)]

            position._buy_transaction_cost = pos_dict.buy_transaction_cost
            position._sell_transaction_cost = pos_dict.sell_transaction_cost
            position._buy_realized_pnl = pos_dict.buy_realized_pnl
            position._sell_realized_pnl = pos_dic.sell_realized_pnl

            position._buy_avg_open_price = pos_dict.buy_avg_open_price
            position._sell_avg_open_price = pos_dict.sell_avg_open_price

            trades = sorted(self._trade_cache[order_book_id], key=lambda t: t.trade_id, reverse=True)

            buy_today_holding_list = []
            sell_today_holding_list = []

            for trade_dict in trades:
                if trade_dict.side == SIDE.BUY and trade_dict.position_effect == POSITION_EFFECT.OPEN:
                    buy_today_holding_list.append((trade_dict.price, trade_dict.quantity))
                elif trade_dict.side == SIDE.SELL and trade_dict.position_effect == POSITION_EFFECT.OPEN:
                    sell_today_holding_list.append((trade_dict.price, trade_dict.quantity))

            position._buy_today_holding_list = buy_today_holding_list
            position._sell_today_holding_list = sell_today_holding_list

            ps[order_book_id] = position
        return ps

    @property
    def account(self):
        static_value = self._account_dict.yesterday_portfolio_value
        ps = self.positions
        holding_pnl = sum(position.holding_pnl for position in six.itervalues(ps))
        realized_pnl = sum(position.realized_pnl for position in six.itervalues(ps))
        cost = sum(position.transaction_cost for position in six.itervalues(ps))
        margin = sum(position.margin for position in six.itervalues(ps))
        total_cash = static_value + holding_pnl + realized_pnl - cost - margin

        account = FutureAccount(total_cash, positions)
        account._frozen_cash = sum(
            [margin_of(order_dict.order_book_id, order_dict.unfilled_quantity, order_dict.price) for order_dict in
             self._order_cache.values() if order_dict.order_status == ACTIVATE])
        return account


class RQObjectCache(object):
    def __init__(self):
        self.orders = {}

    def cache_order(self, order):
        self.orders[order.order_id] = order