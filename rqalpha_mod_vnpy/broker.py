# -*- coding: utf-8 -*-
# 版权所有 2021 深圳米筐科技有限公司（下称“米筐科技”）
#
# 除非遵守当前许可，否则不得使用本软件。
#
#     * 非商业用途（非商业用途指个人出于非商业目的使用本软件，或者高校、研究所等非营利机构出于教育、科研等目的使用本软件）：
#         遵守 Apache License 2.0（下称“Apache 2.0 许可”），
#         您可以在以下位置获得 Apache 2.0 许可的副本：http://www.apache.org/licenses/LICENSE-2.0。
#         除非法律有要求或以书面形式达成协议，否则本软件分发时需保持当前许可“原样”不变，且不得附加任何条件。
#
#     * 商业用途（商业用途指个人出于任何商业目的使用本软件，或者法人或其他组织出于任何目的使用本软件）：
#         未经米筐科技授权，任何个人不得出于任何商业目的使用本软件（包括但不限于向第三方提供、销售、出租、出借、转让本软件、
#         本软件的衍生产品、引用或借鉴了本软件功能或源代码的产品或服务），任何法人或其他组织不得出于任何目的使用本软件，
#         否则米筐科技有权追究相应的知识产权侵权责任。
#         在此前提下，对本软件的使用同样需要遵守 Apache 2.0 许可，Apache 2.0 许可与本许可冲突之处，以本许可为准。
#         详细的授权流程，请联系 public@ricequant.com 获取。

from typing import Dict, Optional
from queue import Queue

from vnpy.event import EventEngine as VNEventEngine
from vnpy.trader.event import EVENT_ORDER as VN_EVENT_ORDER, EVENT_TRADE as VN_EVENT_TRADE
from vnpy.trader.gateway import BaseGateway as VNBaseGateway
from vnpy.trader.object import (
    OrderRequest as VNOrderRequest, OrderData as VNOrderData, TradeData as VNTradeData,
    CancelRequest as VNCancelOrderRequest
)
from vnpy.trader.constant import Status as VNStatus

from rqalpha.environment import Environment
from rqalpha.interface import AbstractBroker
from rqalpha.const import ORDER_STATUS
from rqalpha.model import Order, Trade, Instrument
from rqalpha.core.events import Event, EVENT
from rqalpha.utils.logger import user_system_log, system_log

from .consts import ACCOUNT_TYPE, DIRECTION_OFFSET_MAP, EXCHANGE_MAP, ORDER_TYPE_MAP

EVENT_VN_ORDER = "EVENT_VN_ORDER"
EVENT_VN_TRADE = "EVENT_VN_TRADE"


# TODO: 中端重启后的订单状态恢复
class Broker(AbstractBroker):
    def __init__(
            self,
            env: Environment,
            rqa_event_queue: Queue,
            vn_event_engine: VNEventEngine,
            vn_gateways: Dict[ACCOUNT_TYPE, VNBaseGateway]
    ):
        self._env = env
        self._gateways = vn_gateways

        self._open_orders: Dict[str, Order] = {}  # vt_orderid: Order
        self._order_id_map: Dict[int, str] = {}  # order_id: vt_orderid

        vn_event_engine.register(VN_EVENT_ORDER, lambda e: rqa_event_queue.put(Event(EVENT_VN_ORDER, vn_event=e)))
        vn_event_engine.register(VN_EVENT_TRADE, lambda e: rqa_event_queue.put(Event(EVENT_VN_TRADE, vn_event=e)))

        self._env.event_bus.add_listener(EVENT_VN_ORDER, self._on_vn_order)
        self._env.event_bus.add_listener(EVENT_VN_TRADE, self._on_vn_trade)

    def submit_order(self, order: Order):
        ins = self._env.data_proxy.instruments(order.order_book_id)
        direction, offset = DIRECTION_OFFSET_MAP[order.side, order.position_effect]
        order_req = VNOrderRequest(
            symbol=ins.trading_code,
            exchange=EXCHANGE_MAP[ins.exchange],
            direction=direction,
            type=ORDER_TYPE_MAP[order.type],
            volume=order.quantity,
            price=order.price,
            offset=offset,
            reference=str(order.order_id)
        )
        # TODO: catch KeyErrors
        self._publish_order_event(EVENT.ORDER_PENDING_NEW, order, ins)
        vt_order_id = self._gateways[ins.account_type].send_order(order_req)
        if vt_order_id:
            self._open_orders[vt_order_id] = order
            self._order_id_map[order.order_id] = vt_order_id
        else:
            # TODO: 推动 vnpy 在下单失败时抛出异常以获取真正的原因
            order.mark_rejected("订单创建失败")
            self._publish_order_event(EVENT.ORDER_CREATION_REJECT, order, ins)

    def cancel_order(self, order):
        try:
            vt_orderid = self._order_id_map[order.order_id]
        except KeyError:
            user_system_log.warning(f"订单[{order.order_id}]撤单失败，该订单不存在")
            self._publish_order_event(EVENT.ORDER_CANCELLATION_REJECT, order)
            return
        ins = self._env.data_proxy.instruments(order.order_book_id)
        cancel_order_req = VNCancelOrderRequest(
            # TODO: 推动 vnpy 使用 vt_orderid 作为全局的订单 id
            orderid=".".join(vt_orderid.split(".")[1:]),
            symbol=ins.trading_code,
            exchange=EXCHANGE_MAP[ins.exchange]
        )
        self._gateways[ins.account_type].cancel_order(cancel_order_req)

    def get_open_orders(self, order_book_id=None):
        if order_book_id is not None:
            return [order for order in self._open_orders.values() if order.order_book_id == order_book_id]
        else:
            return list(self._open_orders.values())

    def _on_vn_order(self, event: Event):
        # run in main thread
        vn_order: VNOrderData = event.vn_event.data  # noqa
        try:
            order = self._open_orders[vn_order.vt_orderid]
        except KeyError:
            return
        system_log.debug(f"on_vn_order: {vn_order}")
        if vn_order.status == VNStatus.SUBMITTING:
            return
        if order.status == ORDER_STATUS.PENDING_NEW:
            order.active()
            self._publish_order_event(EVENT.ORDER_CREATION_PASS, order)
        if vn_order.status == VNStatus.REJECTED:
            order.mark_rejected(f"订单[{vn_order.vt_orderid}]被拒绝")
            self._publish_order_event(EVENT.ORDER_UNSOLICITED_UPDATE, order)
        elif vn_order.status == VNStatus.CANCELLED:
            if order.status == ORDER_STATUS.PENDING_CANCEL:
                event_type = EVENT.ORDER_CANCELLATION_PASS
            else:
                event_type = EVENT.ORDER_UNSOLICITED_UPDATE
            order.mark_cancelled(f"订单[{vn_order.vt_orderid}]已撤单")
            self._publish_order_event(event_type, order)
        # 不处理 PARTTRADED 和 ALLTRADED，由 _on_trade 处理
        self._pop_if_order_is_final(order)

    def _on_vn_trade(self, event: Event):
        # run in main thread
        vn_trade: VNTradeData = event.vn_event.data  # noqa
        try:
            order = self._open_orders[vn_trade.vt_orderid]
        except KeyError:
            return
        system_log.debug(f"on_vn_order: {vn_trade}")
        # TODO: 会不会重复收到 trade？
        trade = Trade.__from_create__(
            order_id=order.order_id,
            price=vn_trade.price,
            amount=vn_trade.volume,
            side=order.side,
            position_effect=order.position_effect,
            order_book_id=order.order_book_id,
            calendar_dt=vn_trade.datetime,
            trading_dt=self._env.data_proxy.get_trading_dt(vn_trade.datetime)
        )
        # TODO: 期权 commission tax 的计算并不准确
        trade._commission = self._env.get_trade_commission(trade)
        trade._tax = self._env.get_trade_tax(trade)
        order.fill(trade)
        self._env.event_bus.publish_event(Event(
            EVENT.TRADE,
            account=self._env.portfolio.get_account(order.order_book_id),
            trade=trade,
            order=order
        ))
        self._pop_if_order_is_final(order)

    def _publish_order_event(self, event_type: EVENT, order: Order, ins: Optional[Instrument] = None):
        if ins:
            account = self._env.portfolio.accounts[ins.account_type]
        else:
            account = self._env.portfolio.get_account(order.order_book_id)
        self._env.event_bus.publish_event(Event(event_type, account=account, order=order))

    def _pop_if_order_is_final(self, order: Order):
        if not order.is_final():
            return
        self._open_orders.pop(self._order_id_map.pop(order.order_id))