# -*- coding: utf-8 -*-
from dateutil.parser import parse
from datetime import timedelta
from six import iteritems

from rqalpha.model.order import Order
from rqalpha.model.trade import Trade
from rqalpha.model.instrument import Instrument
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.model.account.future_account import FutureAccount, margin_of
from rqalpha.const import ORDER_STATUS, ORDER_TYPE, POSITION_EFFECT
from .vnpy import EXCHANGE_SHFE, OFFSET_OPEN, OFFSET_CLOSETODAY, DIRECTION_SHORT, DIRECTION_LONG
from .vnpy import STATUS_NOTTRADED, STATUS_PARTTRADED

from .utils import SIDE_REVERSE


def _trading_dt(calendar_dt):
    if calendar_dt.hour > 20:
        return calendar_dt + timedelta(days=1)
    return calendar_dt


def _order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


class RQVNInstrument(Instrument):
    def __init__(self, vnpy_contract):
        # TODO：从 rqalpha data bundle 中读取数据，补充字段
        listed_date = vnpy_contract.get('openDate')
        de_listed_date = vnpy_contract.get('expireDate')

        if listed_date is not None:
            listed_date = '%s-%s-%s' % (listed_date[:4], listed_date[4:6], listed_date[6:])
        else:
            listed_date = '0000-00-00'

        if de_listed_date is not None:
            de_listed_date = '%s-%s-%s' % (de_listed_date[:4], de_listed_date[4:6], de_listed_date[6:])
        else:
            de_listed_date = '0000-00-00'

        dic = {
            'order_book_id': _order_book_id(vnpy_contract.get('symbol')),
            'exchange': vnpy_contract.get('exchange'),
            'symbol': vnpy_contract.get('name'),
            'contract_multiplier': vnpy_contract.get('size'),
            'trading_unit': vnpy_contract.get('priceTick'),
            'type': 'Future',
            'margin_rate': vnpy_contract.get('longMarginRatio'),
            'listed_date': listed_date,
            'de_listed_date': de_listed_date,
            'maturity_date': de_listed_date,
        }

        super(RQVNInstrument, self).__init__(dic)


class RQVNOrder(Order):
    def __init__(self, vnpy_order=None):
        super(RQVNOrder, self).__init__()
        if vnpy_order is None:
            return
        self._order_id = next(self.order_id_gen)
        self._calendar_dt = parse(vnpy_order.orderTime)
        self._trading_dt = _trading_dt(self._calendar_dt)
        self._quantity = vnpy_order.totalVolume
        self._order_book_id = _order_book_id(vnpy_order.symbol)
        self._side = SIDE_REVERSE[vnpy_order.direction]

        if vnpy_order.exchange == EXCHANGE_SHFE:
            if vnpy_order.offset == OFFSET_OPEN:
                self._position_effect = POSITION_EFFECT.OPEN
            elif vnpy_order.offset == OFFSET_CLOSETODAY:
                self._position_effect = POSITION_EFFECT.CLOSE_TODAY
            else:
                self._position_effect = POSITION_EFFECT.CLOSE
        else:
            if vnpy_order.offset == OFFSET_OPEN:
                self._position_effect = POSITION_EFFECT.OPEN
            else:
                self._position_effect = POSITION_EFFECT.CLOSE

        self._message = ""
        self._filled_quantity = vnpy_order.tradedVolume
        self._status = ORDER_STATUS.PENDING_NEW
        # hard code VNPY 封装的报单类型中省掉了 type 字段
        self._type = ORDER_TYPE.LIMIT
        self._frozen_price = vnpy_order.price
        self._type = ORDER_TYPE.LIMIT
        self._avg_price = 0
        self._transaction_cost = 0

    @classmethod
    def create_from_vnpy_trade__(cls, vnpy_trade):
        order = cls()
        order._order_id = next(order.order_id_gen)
        order._calendar_dt = parse(vnpy_trade.tradeTime)
        order._trading_dt = _trading_dt(order._calendar_dt)
        order._order_book_id = _order_book_id(vnpy_trade.symbol)
        order._quantity = vnpy_trade.volume
        order._side = SIDE_REVERSE[vnpy_trade.direction]

        if vnpy_trade.exchange == EXCHANGE_SHFE:
            if vnpy_trade.offset == OFFSET_OPEN:
                order._position_effect = POSITION_EFFECT.OPEN
            elif vnpy_trade.offset == OFFSET_CLOSETODAY:
                order._position_effect = POSITION_EFFECT.CLOSE_TODAY
            else:
                order._position_effect = POSITION_EFFECT.CLOSE
        else:
            if vnpy_trade.offset == OFFSET_OPEN:
                order._position_effect = POSITION_EFFECT.OPEN
            else:
                order._position_effect = POSITION_EFFECT.CLOSE

        order._message = ""
        order._filled_quantity = vnpy_trade.volume
        order._status = ORDER_STATUS.FILLED
        order._type = ORDER_TYPE.LIMIT
        order._avg_price = vnpy_trade.price
        order._transaction_cost = 0
        return order


class RQVNTrade(Trade):
    def __init__(self, vnpy_trade, order):
        super(RQVNTrade, self).__init__()
        self._calendar_dt = parse(vnpy_trade.tradeTime)
        self._trading_dt = _trading_dt(self._calendar_dt)
        self._price = vnpy_trade.price
        self._amount = vnpy_trade.volume
        self._order = order
        self._tax = 0.
        self._trade_id = next(self.trade_id_gen)
        self._close_today_amount = 0.


class AccountCache(object):
    def __init__(self, data_cache):
        self._account_cache = {}
        self._position_cache = {}

        self._order_cache = []

        self._data_cache = data_cache
        self._buy_open_cost_cache = 0.
        self._sell_open_cost_cache = 0.

    def put_vnpy_order(self, vnpy_order):
        self._order_cache.append(vnpy_order)

    def put_vnpy_trade(self, vnpy_trade):
        order_book_id = _order_book_id(vnpy_trade.symbol)
        if order_book_id not in self._position_cache:
            self._position_cache[order_book_id] = {}
        if 'trades' not in self._position_cache[order_book_id]:
            self._position_cache[order_book_id]['trades'] = []
        self._position_cache[order_book_id]['trades'].append(vnpy_trade)

    def put_vnpy_account(self, vnpy_account):
        if 'preBalance' in vnpy_account.__dict__:
            self._account_cache['yesterday_portfolio_value'] = vnpy_account.preBalance

    def put_vnpy_position(self, vnpy_position):
        order_book_id = _order_book_id(vnpy_position.symbol)

        if order_book_id not in self._position_cache:
            self._position_cache[order_book_id] = {}

        if vnpy_position.direction == DIRECTION_LONG:
            if 'position' in vnpy_position.__dict__:
                self._position_cache[order_book_id]['buy_old_quantity'] = vnpy_position.ydPosition
                self._position_cache[order_book_id]['buy_quantity'] = vnpy_position.position
                self._position_cache[order_book_id]['buy_today_quantity'] = vnpy_position.position - vnpy_position.ydPosition
            if 'commission' in vnpy_position.__dict__:
                if 'buy_transaction_cost' not in self._position_cache[order_book_id]:
                    self._position_cache[order_book_id]['buy_transaction_cost'] = 0.
                self._position_cache[order_book_id]['buy_transaction_cost'] += vnpy_position.commission
            if 'closeProfit' in vnpy_position.__dict__:
                if 'buy_realized_pnl' not in self._position_cache[order_book_id]:
                    self._position_cache[order_book_id]['buy_realized_pnl'] = 0.
                self._position_cache[order_book_id]['buy_realized_pnl'] += vnpy_position.closeProfit
            if 'openCost' in vnpy_position.__dict__:
                self._buy_open_cost_cache += vnpy_position.openCost
                contract_multiplier = self._data_cache.get_contract(vnpy_position.symbol)['size']
                buy_quantity = self._position_cache[order_book_id]['buy_quantity']
                self._position_cache[order_book_id]['buy_avg_open_price'] = self._buy_open_cost_cache / (buy_quantity * contract_multiplier) if buy_quantity != 0 else 0

        elif vnpy_position.direction == DIRECTION_SHORT:
            if 'position' in vnpy_position.__dict__:
                self._position_cache[order_book_id]['sell_old_quantity'] = vnpy_position.ydPosition
                self._position_cache[order_book_id]['sell_position'] = vnpy_position.position
                self._position_cache[order_book_id]['sell_today_quantity'] = vnpy_position.position - vnpy_position.ydPosition
            if 'commission' in vnpy_position.__dict__:
                if 'sell_transaction_cost' not in self._position_cache[order_book_id]:
                    self._position_cache[order_book_id]['sell_transaction_cost'] = 0.
                self._position_cache[order_book_id]['sell_transaction_cost'] += vnpy_position.commission
            if 'closeProfit' in vnpy_position.__dict__:
                if 'sell_realized_pnl' not in self._position_cache[order_book_id]:
                    self._position_cache[order_book_id]['sell_realized_pnl'] = 0.
                self._position_cache[order_book_id]['sell_realized_pnl'] += vnpy_position.closeProfit
            if 'openCost' in vnpy_position.__dict__:
                self._sell_open_cost_cache += vnpy_position.openCost
                contract_multiplier = self._data_cache.get_contract(vnpy_position.symbol)['size']
                sell_quantity = self._position_cache[order_book_id]['sell_quantity']
                self._position_cache[order_book_id]['sell_avg_open_price'] = self._sell_open_cost_cache / (sell_quantity * contract_multiplier) if sell_quantity != 0 else 0

        if 'preSettlementPrice' in vnpy_position.__dict__:
            self._position_cache[order_book_id]['prev_settle_price'] = vnpy_position.preSettlementPrice

    def _make_positions(self):
        positions = {}
        for order_book_id, position_dict in iteritems(self._position_cache):
            position = FuturePosition(order_book_id)
            if 'prev_settle_price' in position_dict and 'buy_old_quantity' in position_dict:
                position._buy_old_holding_list = [(position_dict['prev_settle_price'], position_dict['buy_old_quantity'])]
            if 'prev_settle_price' in position_dict and 'sell_old_quantity' in position_dict:
                position._sell_old_holding_list = [(position_dict['prev_settle_price'], position_dict['sell_old_quantity'])]

            if 'buy_transaction_cost' in position_dict:
                position._buy_transaction_cost = position_dict['buy_transaction_cost']
            if 'sell_transaction_cost' in position_dict:
                position._sell_transaction_cost = position_dict['sell_transaction_cost']
            if 'buy_realized_pnl' in position_dict:
                position.__buy_realized_pnl = position_dict['buy_realized_pnl']
            if 'sell_realized_pnl' in position_dict:
                position._sell_realized_pnl = position_dict['sell_realized_pnl']

            if 'buy_avg_open_price' in position_dict:
                position._buy_avg_open_price = position_dict['buy_avg_open_price']
            if 'sell_avg_open_price' in position_dict:
                position._sell_avg_open_price = position_dict['sell_avg_open_price']

            if 'trades' in position_dict:
                accum_buy_open_quantity = 0.
                accum_sell_open_quantity = 0.

                buy_today_quantity = position_dict['buy_today_quantity'] if 'buy_today_quantity' in position_dict else 0
                sell_today_quantity = position_dict['sell_today_quantity'] if 'sell_today_quantity' in position_dict else 0

                trades = sorted(position_dict['trades'], key=lambda t: parse(t.tradeTime), reverse=True)

                buy_today_holding_list = []
                sell_today_holding_list = []
                for vnpy_trade in trades:
                    if vnpy_trade.direction == DIRECTION_LONG:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            accum_buy_open_quantity += vnpy_trade.volume
                            if accum_buy_open_quantity == buy_today_quantity:
                                break
                            if accum_buy_open_quantity > buy_today_quantity:
                                buy_today_holding_list.append((vnpy_trade.price, buy_today_quantity - accum_buy_open_quantity + vnpy_trade.volume))
                                break
                            buy_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))
                    else:
                        if vnpy_trade.offset == OFFSET_OPEN:
                            accum_sell_open_quantity += vnpy_trade.volume
                            if accum_sell_open_quantity == sell_today_quantity:
                                break
                            if accum_sell_open_quantity > sell_today_quantity:
                                sell_today_holding_list.append((vnpy_trade.price, sell_today_quantity - accum_sell_open_quantity + vnpy_trade.volume))
                                break
                            sell_today_holding_list.append((vnpy_trade.price, vnpy_trade.volume))

                position._buy_today_holding_list = buy_today_holding_list
                position._sell_today_holding_list = sell_today_holding_list

            positions[order_book_id] = position
        return positions

    def make_account(self):
        total_cash = self._account_cache['yesterday_portfolio_value']
        positions = self._make_positions()

        account = FutureAccount(total_cash, positions)
        frozen_cash = 0.
        for vnpy_order in self._order_cache:
            if vnpy_order.status == STATUS_NOTTRADED or vnpy_order.status == STATUS_PARTTRADED:
                order_book_id = _order_book_id(vnpy_order.symbol)
                unfilled_quantity = vnpy_order.totalVolume - vnpy_order.tradedVolume
                price = vnpy_order.price
                frozen_cash += margin_of(order_book_id, unfilled_quantity, price)
        account._frozen_cash = frozen_cash
        return account
