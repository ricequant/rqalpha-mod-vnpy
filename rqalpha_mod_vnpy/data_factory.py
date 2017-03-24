# -*- coding: utf-8 -*-
from dateutil.parser import parse
from datetime import timedelta
from six import iteritems
import numpy as np

from rqalpha.model.order import Order, LimitOrder
from rqalpha.model.trade import Trade
from rqalpha.model.position import Positions
from rqalpha.model.position.future_position import FuturePosition
from rqalpha.model.account.future_account import FutureAccount, margin_of
from rqalpha.environment import Environment
from rqalpha.const import ORDER_STATUS, HEDGE_TYPE, POSITION_EFFECT, COMMISSION_TYPE, SIDE, ORDER_TYPE
from .vnpy import EXCHANGE_SHFE, OFFSET_OPEN, OFFSET_CLOSE, OFFSET_CLOSETODAY, DIRECTION_SHORT, DIRECTION_LONG
from .vnpy import STATUS_NOTTRADED, STATUS_PARTTRADED, PRICETYPE_MARKETPRICE, PRICETYPE_LIMITPRICE, CURRENCY_CNY, PRODUCT_FUTURES
from .vnpy import VtOrderReq, VtCancelOrderReq, VtSubscribeReq


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
        order_book_id = DataFactory.make_order_book_id(vnpy_trade.symbol)
        if order_book_id not in self._position_cache:
            self._position_cache[order_book_id] = {}
        if 'trades' not in self._position_cache[order_book_id]:
            self._position_cache[order_book_id]['trades'] = []
        self._position_cache[order_book_id]['trades'].append(vnpy_trade)

    def put_vnpy_account(self, vnpy_account):
        if 'preBalance' in vnpy_account.__dict__:
            self._account_cache['yesterday_portfolio_value'] = vnpy_account.preBalance

    def put_vnpy_position(self, vnpy_position):
        order_book_id = DataFactory.make_order_book_id(vnpy_position.symbol)

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
        positions = Positions(FuturePosition)
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
                order_book_id = DataFactory.make_order_book_id(vnpy_order.symbol)
                unfilled_quantity = vnpy_order.totalVolume - vnpy_order.tradedVolume
                price = vnpy_order.price
                frozen_cash += margin_of(order_book_id, unfilled_quantity, price)
        account._frozen_cash = frozen_cash
        return account


class DataFactory(object):
    SIDE_REVERSE = {
        DIRECTION_LONG: SIDE.BUY,
        DIRECTION_SHORT: SIDE.SELL,
    }

    SIDE_MAPPING = {
        SIDE.BUY: DIRECTION_LONG,
        SIDE.SELL: DIRECTION_SHORT
    }

    ORDER_TYPE_MAPPING = {
        ORDER_TYPE.MARKET: PRICETYPE_MARKETPRICE,
        ORDER_TYPE.LIMIT: PRICETYPE_LIMITPRICE
    }

    POSITION_EFFECT_MAPPING = {
        POSITION_EFFECT.OPEN: OFFSET_OPEN,
        POSITION_EFFECT.CLOSE: OFFSET_CLOSE,
    }

    def __init__(self, data_cache):
        self._data_cache = data_cache

    @classmethod
    def make_trading_dt(cls, calendar_dt):
        # FIXME: 替换为 next_trading_date
        if calendar_dt.hour > 20:
            return calendar_dt + timedelta(days=1)
        return calendar_dt

    @classmethod
    def make_position_effect(cls, vnpy_exchange, vnpy_offset):
        if vnpy_exchange == EXCHANGE_SHFE:
            if vnpy_offset == OFFSET_OPEN:
                return POSITION_EFFECT.OPEN
            elif vnpy_offset == OFFSET_CLOSETODAY:
                return POSITION_EFFECT.CLOSE_TODAY
            else:
                return POSITION_EFFECT.CLOSE
        else:
            if vnpy_offset == OFFSET_OPEN:
                return POSITION_EFFECT.OPEN
            else:
                return POSITION_EFFECT.CLOSE

    @classmethod
    def make_order_book_id(cls, symbol):
        if len(symbol) < 4:
            return None
        if symbol[-4] not in '0123456789':
            order_book_id = symbol[:2] + '1' + symbol[-3:]
        else:
            order_book_id = symbol
        return order_book_id.upper()

    @classmethod
    def make_order(cls, vnpy_order):
        calendar_dt = parse(vnpy_order.orderTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        order_book_id = cls.make_order_book_id(vnpy_order.symbol)
        quantity = vnpy_order.totalVolume
        side = cls.SIDE_REVERSE[vnpy_order.direction]
        style = LimitOrder(vnpy_order.price)
        position_effect = cls.make_position_effect(vnpy_order.exchange, vnpy_order.offset)

        order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
        order._filled_quantity = vnpy_order.totalVolume

        return order

    @classmethod
    def make_order_from_vnpy_trade(cls, vnpy_trade):
        calendar_dt = parse(vnpy_trade.tradeTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        order_book_id = cls.make_order_book_id(vnpy_trade.symbol)
        quantity = vnpy_trade.volume
        side = cls.SIDE_REVERSE[vnpy_trade.direction]
        style = LimitOrder(vnpy_trade.price)
        position_effect = cls.make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)

        order = Order.__from_create__(calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect)
        order._filled_quantity = vnpy_trade.volume
        order._status = ORDER_STATUS.FILLED
        order._avg_price = vnpy_trade.price
        # FIXME: 用近似值代替
        order._transaction_cost = 0
        return order

    @classmethod
    def get_commission(cls, order_book_id, position_effect, price, amount, hedge_type=HEDGE_TYPE.SPECULATION):
        info = Environment.get_instance().get_future_commission_info(order_book_id, hedge_type)
        commission = 0
        if info['commission_type'] == COMMISSION_TYPE.BY_MONEY:
            contract_multiplier = Environment.get_instance().get_instrument(order_book_id).contract_multiplier
            if position_effect == POSITION_EFFECT.OPEN:
                commission += price * amount * contract_multiplier * info['open_commission_ratio']
            else:
                commission += price * amount * contract_multiplier * info['close_commission_ratio']
        else:
            if position_effect == POSITION_EFFECT.OPEN:
                commission += amount * info['open_commission_ratio']
            else:
                commission += amount * info['close_commission_ratio']
        return commission

    @classmethod
    def make_trade(cls, vnpy_trade, order_id=None):
        order_id = order_id if order_id is not None else next(Order.order_id_gen)
        calendar_dt = parse(vnpy_trade.tradeTime)
        trading_dt = cls.make_trading_dt(calendar_dt)
        price = vnpy_trade.price
        amount = vnpy_trade.volume
        side = cls.SIDE_REVERSE[vnpy_trade.direction]
        position_effect = cls.make_position_effect(vnpy_trade.exchange, vnpy_trade.offset)
        order_book_id = cls.make_order_book_id(vnpy_trade.symbol)
        commission = cls.get_commission(order_book_id, position_effect, price, amount)
        frozen_price = vnpy_trade.price

        return Trade.__from_create__(
            order_id, calendar_dt, trading_dt, price, amount, side, position_effect,  order_book_id,
            commission=commission, frozen_price=frozen_price)

    @classmethod
    def make_tick(cls, vnpy_tick):
        order_book_id = cls.make_order_book_id(vnpy_tick.symbol)
        tick = {
            'order_book_id': order_book_id,
            'datetime': parse('%s %s' % (vnpy_tick.date, vnpy_tick.time)),
            'open': vnpy_tick.openPrice,
            'last': vnpy_tick.lastPrice,
            'low': vnpy_tick.lowPrice,
            'high': vnpy_tick.highPrice,
            'prev_close': vnpy_tick.preClosePrice,
            'volume': vnpy_tick.volume,
            'total_turnover': np.nan,
            'open_interest': vnpy_tick.openInterest,
            'prev_settlement': np.nan,

            'bid': [
                vnpy_tick.bidPrice1,
                vnpy_tick.bidPrice2,
                vnpy_tick.bidPrice3,
                vnpy_tick.bidPrice4,
                vnpy_tick.bidPrice5,
            ],
            'bid_volume': [
                vnpy_tick.bidVolume1,
                vnpy_tick.bidVolume2,
                vnpy_tick.bidVolume3,
                vnpy_tick.bidVolume4,
                vnpy_tick.bidVolume5,
            ],
            'ask': [
                vnpy_tick.askPrice1,
                vnpy_tick.askPrice2,
                vnpy_tick.askPrice3,
                vnpy_tick.askPrice4,
                vnpy_tick.askPrice5,
            ],
            'ask_volume': [
                vnpy_tick.askVolume1,
                vnpy_tick.askVolume2,
                vnpy_tick.askVolume3,
                vnpy_tick.askVolume4,
                vnpy_tick.askVolume5,
            ],

            'limit_up': vnpy_tick.upperLimit,
            'limit_down': vnpy_tick.lowerLimit,
        }
        return tick

    def make_order_req(self, order):
        symbol = self._data_cache.get_symbol(order.order_book_id)
        contract = self._data_cache.get_contract(symbol)
        if contract is None:
            return None

        order_req = VtOrderReq()
        order_req.symbol = contract['symbol']
        order_req.exchange = contract['exchange']
        order_req.price = order.price
        order_req.volume = order.quantity
        order_req.direction = self.SIDE_MAPPING[order.side]
        order_req.priceType = self.ORDER_TYPE_MAPPING[order.type]
        order_req.offset = self.POSITION_EFFECT_MAPPING[order.position_effect]
        order_req.currency = CURRENCY_CNY
        order_req.productClass = PRODUCT_FUTURES

        return order_req

    def make_cancel_order_req(self, order):
        vnpy_order = self._data_cache.get_vnpy_order(order.order_id)

        cancel_order_req = VtCancelOrderReq()
        cancel_order_req.symbol = vnpy_order.symbol
        cancel_order_req.exchange = vnpy_order.exchange
        cancel_order_req.sessionID = vnpy_order.sessionID
        cancel_order_req.orderID = vnpy_order.orderID

        return cancel_order_req

    def make_subscribe_req(self, order_book_id):
        symbol = self._data_cache.get_symbol(order_book_id)
        contract = self._data_cache.get_contract(symbol)
        if contract is None:
            return None
        subscribe_req = VtSubscribeReq()
        subscribe_req.symbol = contract['symbol']
        subscribe_req.exchange = contract['exchange']
        subscribe_req.productClass = PRODUCT_FUTURES
        subscribe_req.currency = CURRENCY_CNY

        return subscribe_req
