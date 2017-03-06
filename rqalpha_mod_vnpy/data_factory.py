# -*- coding: utf-8 -*-
from dateutil.parser import parse
from datetime import timedelta, date
from six import iteritems

from rqalpha.model.order import Order
from rqalpha.model.trade import Trade
from rqalpha.model.instrument import Instrument
from rqalpha.model.account.future_account import FutureAccount
from rqalpha.model.portfolio.future_portfolio import FuturePortfolio
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.const import ORDER_STATUS, ORDER_TYPE, POSITION_EFFECT, ACCOUNT_TYPE, SIDE
from .vn_trader.vtConstant import EXCHANGE_SHFE, OFFSET_OPEN, OFFSET_CLOSETODAY
from .vn_trader.vtConstant import DIRECTION_LONG, DIRECTION_SHORT, DIRECTION_NET
from .utils import SIDE_REVERSE, POSITION_EFFECT_MAPPING, ORDER_TYPE_MAPPING


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
    def __init__(self, vnpy_order=None, contract=None):
        super(RQVNOrder, self).__init__()
        if vnpy_order is None or contract is None:
            return
        self._order_id = next(self.order_id_gen)
        self._calendar_dt = parse(vnpy_order.orderTime)
        self._trading_dt = _trading_dt(self._calendar_dt)
        self._quantity = vnpy_order.totalVolume
        self._order_book_id = _order_book_id(vnpy_order.symbol)
        self._side = SIDE_REVERSE[vnpy_order.direction]

        if contract.exchange == EXCHANGE_SHFE:
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
    def create_from_vnpy_trade__(cls, vnpy_trade, contract):
        order = cls()
        order._order_id = next(order.order_id_gen)
        order._calendar_dt = parse(vnpy_trade.tradeTime)
        order._trading_dt = _trading_dt(order._calendar_dt)
        order._order_book_id = _order_book_id(vnpy_trade.symbol)
        order._quantity = vnpy_trade.volume
        order._side = SIDE_REVERSE[vnpy_trade.direction]

        if contract.exchange == EXCHANGE_SHFE:
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
        # TODO: 查询合约commission信息并计算trade的commission，需要扩展CTPGateway并添加新的数据类，
        # 另一种解决方案是在 data_source 内实现 get_all_instruments, 但是个别字段需要单独请求CTP，貌似不太现实。
        self._commission = 0.
        self._tax = 0.
        self._trade_id = next(self.trade_id_gen)
        self._close_today_amount = 0.


class RQVNFuturePosition(FuturePosition):
        # self._prev_settle_price
    def __init__(self, order_book_id, contract):
        super(RQVNFuturePosition, self).__init__(order_book_id)

        if contract is not None:
            self._contract_multiplier = contract.size

        self._buy_final_holding = None
        self._sell_final_holding = None
        self.commission = 0

    def update_with_vnpy_position(self, vnpy_position):
        if vnpy_position.direction in [DIRECTION_LONG, DIRECTION_NET]:
            self._sell_open_order_quantity = vnpy_position.frozen
            self._buy_avg_open_price = vnpy_position.price
            self._buy_today_holding_list = [(vnpy_position.price, vnpy_position.position - vnpy_position.ydPosition)]
            if vnpy_position.ydPosition > 0:
                self._buy_old_holding_list = [vnpy_position.price, vnpy_position.ydPosition]
            # self._buy_market_value
        elif vnpy_position.direction == DIRECTION_SHORT:
            self._buy_close_order_quantity = vnpy_position.close
            self._sell_avg_open_price = vnpy_position.price
            self._sell_today_holding_list = [(vnpy_position.price, vnpy_position.position - vnpy_position.ydPosition)]
            if vnpy_position.ydPosition > 0:
                self._sell_old_holding_list = [vnpy_position.price, vnpy_position.ydPosition]
            # self._sell_market_value

    def update_with_position_extra(self, vnpy_position_extra):
        if vnpy_position_extra.direction in [DIRECTION_LONG, DIRECTION_NET]:
            self._buy_daily_realized_pnl = vnpy_position_extra.closeProfit
            self._buy_avg_open_price = vnpy_position_extra.openCost
        elif vnpy_position_extra.direction == DIRECTION_SHORT:
            self._sell_avg_open_price = vnpy_position_extra.closeProfit
            self._sell_daily_realized_pnl = vnpy_position_extra.closeProfit

    def update_with_hist_trade(self, trade):
        order = trade.order
        trade_quantity = trade.last_quantity
        trade_value = trade.last_price * trade_quantity * position._contract_multiplier
        if order.side == SIDE.BUY:
            if order.position_effect == POSITION_EFFECT.OPEN:
                self._buy_open_trade_quantity += trade_quantity
                self._buy_open_trade_value += trade_value
                self._buy_open_transaction_cost += trade.commission
            else:
                self._buy_close_trade_quantity += trade_quantity
                self._buy_close_trade_value += trade_value
                self._buy_close_transaction_cost += trade.commission

                if order.position_effect == POSITION_EFFECT.CLOSE_TODAY:
                    self._sell_today_holding_list.apend((trade.last_price, trade.last_quantity))
                else:
                    self._sell_old_holding_list.append((trade.last_price, trade.last_quantity))

            self._buy_trade_quantity += trade_quantity
            self._buy_trade_value += trade_value
        else:
            if order.position_effect == POSITION_EFFECT.OPEN:
                self._sell_open_trade_quantity += trade_quantity
                self._sell_open_trade_value += trade_value
                self._sell_open_transaction_cost += trade.commission
            else:
                self._sell_close_trade_quantity += trade_quantity
                self._sell_close_trade_value += trade_value
                self._sell_close_transaction_cost += trade.commission

                if order.position_effect == POSITION_EFFECT.CLOSE_TODAY:
                    self._buy_today_holding_list.append((trade.last_price, trade.last_quantity))
                else:
                    self._buy_old_holding_list.append((trade.last_price, trade.last_quantity))

            self._sell_trade_quantity += trade_quantity
            self._sell_trade_value += trade_value
        self.commission += trade.commission

    def update_with_hist_order(self, order):
        inc_order_quantity = order.quantity
        inc_order_value = order._frozen_price * created_quantity * self._contract_multiplier
        if order.side == SIDE.BUY:
            if order.position_effect == POSITION_EFFECT.OPEN:
                self._buy_open_order_quantity += inc_order_quantity
                self._buy_open_order_value += inc_order_value
            else:
                self._buy_close_order_quantity += inc_order_quantity
                self._buy_close_order_value += inc_order_value
        else:
            if order.position_effect == POSITION_EFFECT.OPEN:
                self._sell_open_order_quantity += inc_order_quantity
                self._sell_open_order_value += inc_order_value
            else:
                self._sell_close_order_quantity += inc_order_quantity
                self._sell_close_order_value += inc_order_value

    def final_update(self):
        self._daily_realized_pnl = self._buy_daily_realized_pnl + self._sell_daily_realized_pnl


class RQVNPortfolio(FuturePortfolio):
    def __init__(self, vnpy_account, start_date):
        super(RQVNPortfolio, self).__init__(0, start_date, ACCOUNT_TYPE.FUTURE)
        self._yesterday_portfolio_value = vnpy_account['preBalance']
        # self._cash =
        # self._starting_cash = self._yesterday_portfolio_value
        # self._start_date = date.today()
        # self._current_date = date.today(0)
        # self._frozen_cash =
        # self._total_tax =
        # _dividend_receivable
        # _dividend_info
        # _daily_transaction_cost
        # _positions

    def update_positions(self, position_cache):
        for order_book_id, position in position_cache:
            # self._position[order_book_id] = position
            self._total_commission += position.commission


class RQVNCount(FutureAccount):
    def __init__(self, env, start_date):
        super(RQVNCount, self).__init__(env, 0, start_date)

        self._vnpy_order_cache = []
        self._vnpy_trade_cache = []

        self._position_cache = {}

        self._vnpy_account_cache = None

        self.inited = False

    def do_init(self, contract_dict):
        order_list = []
        for vnpy_order in self._vnpy_order_cache:
            contract = contract_dict.get(_order_book_id(vnpy_order.symbol))
            order = RQVNOrder(vnpy_order, contract)
            order_list.append(order)
        trade_list = []
        for vnpy_trade in self._vnpy_trade_cache:
            contract = contract_dict.get(_order_book_id(vnpy_trade.symbol))
            order = RQVNOrder.create_from_vnpy_trade__(vnpy_trade, contract)
            trade = RQVNTrade(vnpy_trade, order)
            trade_list.append(trade)
        order_list = sorted(order_list, key=lambda x: x.datetime)
        trade_list = sorted(trade_list, key=lambda x: x.datetime)

        for order in order_list:
            order_book_id = order.order_book_id
            if order_book_id not in self._position_cache:
                contract = contract_dict.get(order_book_id)
                self._position_cache[order_book_id] = RQVNFuturePosition(order_book_id, contract)
            self._position_cache[order_book_id].update_with_hist_order(order)

        for trade in trade_list:
            order_book_id = trade.order_book_id
            if order_book_id not in self._position_cache:
                contract = contract_dict.get(order_book_id)
                self._position_cache[order_book_id] = RQVNFuturePosition(order_book_id, contract)
            self._position_cache[order_book_id].update_with_hist_trade(trade)

        for position in self._position_cache.values():
            position.final_update()

        # TODO: 恢复portfolio数据并还原account数据结构

    def put_vnpy_hist_order(self, order):
        self._vnpy_order_cache.append(order)

    def put_vnpy_hist_trade(self, trade):
        self._vnpy_trade_cache.append(trade)

    def put_vnpy_position(self, vnpy_position, contract):
        order_book_id = _order_book_id(vnpy_position.symbol)
        if order_book_id not in self._position_cache:
            self._position_cache[order_book_id] = RQVNFuturePosition(order_book_id, contract)
        self._position_cache[order_book_id].update_with_vnpy_position(vnpy_position)

    def put_vnpy_position_extra(self, vnpy_position_extra, contract):
        order_book_id = _order_book_id(vnpy_position_extra.symbol)
        if order_book_id not in self._position_cache:
            self._position_cache[order_book_id] = RQVNFuturePosition(order_book_id, contract)
        self._position_cache[order_book_id].update_with_position_extra(vnpy_position_extra)

    def put_vnpy_account(self, vnpy_account):
        self._vnpy_account_cache = vnpy_account
