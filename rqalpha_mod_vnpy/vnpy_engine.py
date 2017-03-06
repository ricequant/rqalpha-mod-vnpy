# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.parser import parse
from Queue import Queue
from Queue import Empty
from time import time, sleep
import numpy as np

from rqalpha.events import EVENT
from rqalpha.utils import get_account_type
from rqalpha.utils.logger import system_log
from rqalpha.const import ACCOUNT_TYPE, ORDER_STATUS

from .vn_trader.eventEngine import EventEngine2
from .vn_trader.vtGateway import VtOrderReq, VtCancelOrderReq, VtSubscribeReq
from .vn_trader.eventType import EVENT_CONTRACT, EVENT_ORDER, EVENT_TRADE, EVENT_TICK, EVENT_LOG, EVENT_ACCOUNT, EVENT_POSITION
from .vn_trader.vtConstant import STATUS_NOTTRADED, STATUS_PARTTRADED, STATUS_ALLTRADED, STATUS_CANCELLED, STATUS_UNKNOWN

from .vn_trader.vtConstant import CURRENCY_CNY
from .vn_trader.vtConstant import PRODUCT_FUTURES

from .vnpy_gateway import EVENT_POSITION_EXTRA
from .data_factory import RQVNOrder, RQVNTrade, RQVNCount
from .utils import SIDE_MAPPING, ORDER_TYPE_MAPPING, POSITION_EFFECT_MAPPING

_engine = None


def _order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


class RQVNPYEngine(object):
    def __init__(self, env, config):
        self._env = env
        self._config = config
        self.event_engine = EventEngine2()
        self.event_engine.start()

        self.accounts = {ACCOUNT_TYPE.FUTURE: RQVNCount(env, env.config.base.start_date)}

        self.gateway_type = None
        self.vnpy_gateway = None
        self.init_account_time = None
        self.account_inited = None

        self._init_gateway()
        self._data_cache = DataCache()

        self._tick_que = Queue()

        self._register_event()
        self._inited = False

    # ------------------------------------ order生命周期 ------------------------------------
    def send_order(self, order):
        account = self._get_account_for(order.order_book_id)
        self._env.event_bus.publish_event(EVENT.ORDER_PENDING_NEW, account, order)

        contract = self._data_cache.get_contract(order.order_book_id)

        if contract is None:
            self._env.event_bus.publish_event(EVENT.ORDER_PENDING_CANCEL)
            order._mark_cancelled('No contract exists whose order_book_id is %s' % order.order_book_id)
            self._env.event_bus.publish_event(EVENT.ORDER_CANCELLATION_PASS)

        if order._is_final():
            return

        order_req = VtOrderReq()
        order_req.symbol = contract.symbol
        order_req.exchange = contract.exchange
        order_req.price = order.price
        order_req.volume = order.quantity
        order_req.direction = SIDE_MAPPING[order.side]
        order_req.priceType = ORDER_TYPE_MAPPING[order.type]
        order_req.offset = POSITION_EFFECT_MAPPING[order.position_effect]
        order_req.currency = CURRENCY_CNY
        order_req.productClass = PRODUCT_FUTURES

        vnpy_order_id = self.vnpy_gateway.sendOrder(order_req)
        self._data_cache.put_order(vnpy_order_id, order)

    def cancel_order(self, order):
        account = self._get_account_for(order.order_book_id)
        self._env.event_bus.publish_event(EVENT.ORDER_PENDING_CANCEL, account, order)

        vnpy_order = self._data_cache.get_vnpy_order(order.order_id)

        cancel_order_req = VtCancelOrderReq()
        cancel_order_req.symbol = vnpy_order.symbol
        cancel_order_req.exchange = vnpy_order.exchange
        cancel_order_req.sessionID = vnpy_order.sessionID
        cancel_order_req.orderID = vnpy_order.orderID
        self.vnpy_gateway.cancelOrder(cancel_order_req)

    def on_order(self, event):
        vnpy_order = event.dict_['data']
        # FIXME 发现订单会重复返回，此处是否会导致订单丢失有待验证
        if vnpy_order.status == STATUS_UNKNOWN:
            return
        system_log.debug("on_order {}", vnpy_order.__dict__)
        vnpy_order_id = vnpy_order.vtOrderID
        order = self._data_cache.get_order(vnpy_order_id)

        if order is not None:
            account = self._get_account_for(order.order_book_id)

            order._activate()

            self._env.event_bus.publish_event(EVENT.ORDER_CREATION_PASS, account, order)

            self._data_cache.put_vnpy_order(order.order_id, vnpy_order)
            if vnpy_order.status == STATUS_NOTTRADED or vnpy_order.status == STATUS_PARTTRADED:
                self._data_cache.put_open_order(vnpy_order_id, order)
            elif vnpy_order.status == STATUS_ALLTRADED:
                self._data_cache.del_open_order(vnpy_order_id)
            elif vnpy_order.status == STATUS_CANCELLED:
                self._data_cache.del_open_order(vnpy_order_id)
                if order.status == ORDER_STATUS.PENDING_CANCEL:
                    order._mark_cancelled("%d order has been cancelled by user." % order.order_id)
                    self._env.event_bus.publish_event(EVENT.ORDER_CANCELLATION_PASS, account, order)
                else:
                    order._mark_rejected('Order was rejected or cancelled by vnpy.')
                    self._env.event_bus.publish_event(EVENT.ORDER_UNSOLICITED_UPDATE, account, order)
        else:
            account = self._get_account_for(_order_book_id(vnpy_order.symbol))
            if not account.inited:
                account.put_vnpy_hist_order(vnpy_order)
            else:
                system_log.error('Order from VNPY dose not match that in rqalpha')

    @property
    def open_orders(self):
        return self._data_cache.open_orders

    # ------------------------------------ trade生命周期 ------------------------------------
    def on_trade(self, event):
        vnpy_trade = event.dict_['data']
        system_log.debug("on_trade {}", vnpy_trade.__dict__)
        order = self._data_cache.get_order(vnpy_trade.vtOrderID)
        account = self._get_account_for(_order_book_id(vnpy_trade.symbol))
        if not account.inited:
            account.put_vnpy_hist_trade(vnpy_trade)
        else:
            if order is None:
                contract = self._data_cache.get_contract(_order_book_id(vnpy_trade.symbol))
                order = RQVNOrder.create_from_vnpy_trade__(vnpy_trade, contract)
            trade = RQVNTrade(vnpy_trade, order)
            # TODO: 以下三行是否需要在 mod 中实现？
            # trade._commission = account.commission_decider.get_commission(trade)
            # trade._tax = account.tax_decider.get_tax(trade)
            # order._fill(trade)
            self._env.event_bus.publish_event(EVENT.TRADE, account, trade)

    # ------------------------------------ instrument生命周期 ------------------------------------
    def on_contract(self, event):
        contract = event.dict_['data']
        system_log.debug("on_contract {}", contract.__dict__)
        self._data_cache.put_contract(contract)

    def wait_until_contract_updated(self, timeout=None):
        start_time = time()
        while True:
            if self.vnpy_gateway.contract_update_complete:
                break
            else:
                if timeout is not None:
                    if time() - start_time > timeout:
                        break

    # ------------------------------------ tick生命周期 ------------------------------------
    def on_universe_changed(self, universe):
        self.wait_until_contract_updated(timeout=10)
        for order_book_id in universe:
            self.subscribe(order_book_id)

    def subscribe(self, order_book_id):
        contract = self._data_cache.get_contract(order_book_id)
        if contract is None:
            system_log.error('Cannot find contract whose order_book_id is %s' % order_book_id)
            return
        subscribe_req = VtSubscribeReq()
        subscribe_req.symbol = contract.symbol
        subscribe_req.exchange = contract.exchange
        # hard code
        subscribe_req.productClass = PRODUCT_FUTURES
        subscribe_req.currency = CURRENCY_CNY
        self.vnpy_gateway.subscribe(subscribe_req)

    def on_tick(self, event):
        vnpy_tick = event.dict_['data']
        system_log.debug("vnpy tick {}", vnpy_tick.__dict__)
        order_book_id = _order_book_id(vnpy_tick.symbol)
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
        self._tick_que.put(tick)
        self._data_cache.put_tick_snapshot(tick)

    def get_tick(self):
        while True:
            try:
                return self._tick_que.get(block=True, timeout=1)
            except Empty:
                system_log.debug("get tick timeout")
                continue

    def get_tick_snapshot(self, order_book_id):
        return self._data_cache.get_tick_snapshot(order_book_id)

    # ------------------------------------ account生命周期 ------------------------------------
    def on_positions(self, event):
        vnpy_position = event.dict_['data']
        system_log.debug("on_positions {}", vnpy_position.__dict__)
        order_book_id = _order_book_id(vnpy_position.symbol)
        account = self._get_account_for(order_book_id)
        if not account.inited:
            contract = self._data_cache.get_contract(order_book_id)
            account.put_vnpy_position(vnpy_position, contract)

    def on_position_extra(self, event):
        vnpy_position_extra = event.dict_['data']
        system_log.debug("on_position_extra {}", vnpy_position_extra.__dict__)
        order_book_id = _order_book_id(vnpy_position_extra.symbol)
        account = self._get_account_for(order_book_id)
        if not account.inited:
            contract = self._data_cache.get_contract(order_book_id)
            account.put_vnpy_position_extra(vnpy_position_extra, contract)

    def on_account(self, event):
        vnpy_account = event.dict_['data']
        system_log.debug("on_account {}", vnpy_account.__dict__)
        # hard code
        account = self.accounts[ACCOUNT_TYPE.FUTURE]
        if not account.inited:
            account.put_vnpy_account(vnpy_account)

    # ------------------------------------ gateway 和 event engine生命周期 ------------------------------------
    def _init_gateway(self):
        self.gateway_type = self._config.gateway_type
        if self.gateway_type == 'CTP':
            try:
                from .vnpy_gateway import RQVNCTPGateway
                self.vnpy_gateway = RQVNCTPGateway(self.event_engine, self.gateway_type)
                # self.vnpy_gateway.setQryEnabled(True)
            except ImportError as e:
                system_log.exception("No Gateway named CTP")
        else:
            system_log.error('No Gateway named {}', self.gateway_type)

    def do_init(self):
        self.vnpy_gateway.do_init(dict(getattr(self._config, self.gateway_type)))
        for account in self.accounts.values():
            if account.inited:
                continue
            account.do_init(self._data_cache.get_contract_dict())

    def exit(self):
        self.vnpy_gateway.close()
        self.event_engine.stop()

    def _register_event(self):
        self.event_engine.register(EVENT_ORDER, self.on_order)
        self.event_engine.register(EVENT_CONTRACT, self.on_contract)
        self.event_engine.register(EVENT_TRADE, self.on_trade)
        self.event_engine.register(EVENT_TICK, self.on_tick)
        self.event_engine.register(EVENT_LOG, self.on_log)
        self.event_engine.register(EVENT_ACCOUNT, self.on_account)
        self.event_engine.register(EVENT_POSITION, self.on_positions)
        self.event_engine.register(EVENT_POSITION_EXTRA, self.on_position_extra)

        self._env.event_bus.add_listener(EVENT.POST_UNIVERSE_CHANGED, self.on_universe_changed)

    def wait_until_inited(self, timeout=None):
        start_time = time()
        while True:
            if self.vnpy_gateway.inited:
                break
            else:
                if timeout is not None:
                    if time() - start_time > timeout:
                        break

    # ------------------------------------ 其他 ------------------------------------
    def on_log(self, event):
        log = event.dict_['data']
        system_log.debug(log.logContent)

    def _get_account_for(self, order_book_id):
        # hard code
        account_type = ACCOUNT_TYPE.FUTURE
        return self.accounts[account_type]


class DataCache(object):
    def __init__(self):
        self._order_dict = {}
        self._vnpy_order_dict = {}
        self._open_order_dict = {}

        self._contract_dict = {}

        self._tick_snapshot_dict = {}

    @staticmethod
    def _order_book_id(symbol):
        if len(symbol) < 4:
            return None
        if symbol[-4] not in '0123456789':
            order_book_id = symbol[:2] + '1' + symbol[-3:]
        else:
            order_book_id = symbol
        return order_book_id.upper()

    @property
    def open_orders(self):
        return list(self._open_order_dict.values())

    def put_order(self, vnpy_order_id, order):
        self._order_dict[vnpy_order_id] = order

    def put_open_order(self, vnpy_order_id, order):
        self._open_order_dict[vnpy_order_id] = order

    def put_vnpy_order(self, order_id, vnpy_order):
        self._vnpy_order_dict[order_id] = vnpy_order

    def put_contract(self, contract):
        order_book_id = self._order_book_id(contract.symbol)
        self._contract_dict[order_book_id] = contract

    def del_open_order(self, vnpy_order_id):
        if vnpy_order_id in self._open_order_dict:
            del self._open_order_dict[vnpy_order_id]

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

    def get_contract(self, order_book_id):
        try:
            return self._contract_dict[order_book_id]
        except KeyError:
            system_log.error('Cannot find such contract whose order_book_id is {} ', order_book_id)

    def put_tick_snapshot(self, tick):
        order_book_id = tick['order_book_id']
        self._tick_snapshot_dict[order_book_id] = tick

    def get_tick_snapshot(self, order_book_id):
        try:
            return self._tick_snapshot_dict[order_book_id]
        except KeyError:
            system_log.error('Cannot find such tick whose order_book_id is {} ', order_book_id)
            return None

    def get_contract_dict(self):
        return self._contract_dict
