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

import pytz
from functools import lru_cache
from datetime import datetime, date, time
from queue import Queue, Empty
from operator import itemgetter
from typing import Optional, Dict, Set

import rqdatac

from vnpy.event import EventEngine as VNEventEngine, Event as VNEvent
from vnpy.trader.gateway import BaseGateway as VNBaseGateway
from vnpy.trader.object import SubscribeRequest as VNSubscribeRequest, TickData as VNTickData
from vnpy.trader.event import EVENT_TICK as VN_EVENT_TICK

from rqalpha.model import TickObject, Instrument
from rqalpha.environment import Environment
from rqalpha.interface import AbstractEventSource
from rqalpha.core.events import Event, EVENT
from rqalpha.const import DEFAULT_ACCOUNT_TYPE
from rqalpha.utils import STOCK_TRADING_PERIOD, TimeRange, is_trading

from .consts import ACCOUNT_TYPE, EXCHANGE_MAP


class MarketEventPublisher:
    def __init__(self, env: Environment):
        self._env = env
        self._last_bft: Optional[date] = None  # 最近一次 before_trading 事件所在的交易日
        self._last_aft: Optional[date] = None  # 最近一次 after_trading 事件所在的交易日

    def get_state(self):
        return {"last_bft": self._last_bft, "last_aft": self._last_aft}

    def set_state(self, state):
        self._last_bft, self._last_aft = itemgetter("last_bft", "last_aft")

    def publish_if_need(self, need_night_trading):
        # TODO: 根据订阅合约所需的交易时间发送事件
        # 依靠计算机物理时间发送 before_trading 和 after_trading 时间
        now = datetime.now()
        if (not need_night_trading) and now.hour >= 20:
            return
        try:
            trading_date = self._env.data_proxy.get_future_trading_date(now)
        except RuntimeError:
            # 非交易时间
            return
        if trading_date == self._last_aft:
            # 当日已经发送了 after_trading 事件，啥也不做
            return
        if trading_date == self._last_bft:
            # 当日已经发送了 before_trading，还没发 after_trading，检查是否收盘了
            if now.hour >= 16:
                self._publish(EVENT.AFTER_TRADING, now, trading_date)
                self._last_bft = trading_date
        else:
            # 当日还未发送 before_trading
            if now.hour >= 20 or 8 <= now.hour < 16:
                self._publish(EVENT.BEFORE_TRADING, now, trading_date)

    def _publish(self, event_type, now: datetime, trading_date: date):
        self._env.event_bus.publish_event(Event(
            event_type,
            calendar_dt=now,
            trading_dt=datetime.combine(trading_date, now.time())
        ))


@lru_cache()
def get_tick_trading_period(order_book_id):
    trading_hours = rqdatac.get_trading_hours(order_book_id, frequency="tick")
    trading_period = list()
    trading_hours = trading_hours.replace("-", ":")
    for time_range_str in trading_hours.split(","):
        start_h, start_m, end_h, end_m = (int(i) for i in time_range_str.split(":"))
        start, end = time(start_h, start_m), time(end_h, end_m)
        if start > end:
            trading_period.append(TimeRange(start, time(23, 59)))
            trading_period.append(TimeRange(time(0, 0), end))
        else:
            trading_period.append(TimeRange(start, end))
    return trading_period


class EventSource(AbstractEventSource):
    def __init__(
            self,
            env: Environment,
            rqa_event_queue: Queue,
            vn_event_engine: VNEventEngine,
            vn_gateways: Dict[ACCOUNT_TYPE, VNBaseGateway],
    ):
        self._env = env
        self._queue = rqa_event_queue
        self._event_engine = vn_event_engine
        self._gateways = vn_gateways

        self._subscribed: Set[str] = set()
        self._trading_code_map: Dict[str, Instrument] = {}  # trading_code: order_book_id

        self._market_event_publisher = MarketEventPublisher(env)
        self._universe_changed = True

        vn_event_engine.register(VN_EVENT_TICK, self._on_tick)
        self._env.event_bus.add_listener(EVENT.POST_UNIVERSE_CHANGED, self._on_universe_change)

    def get_state(self):
        return self._market_event_publisher.get_state()

    def set_state(self, state):
        self._market_event_publisher.set_state(state)

    def events(self, start_date, end_date, frequency):
        trading_periods = []
        need_night_trading = False

        def _update_trading_periods_if_universe_changed():
            nonlocal trading_periods, need_night_trading
            if not self._universe_changed:
                return
            trading_periods = self._env.data_proxy.get_trading_period(
                self._env.get_universe(),
                STOCK_TRADING_PERIOD if DEFAULT_ACCOUNT_TYPE.STOCK in self._env.config.base.accounts else []
            )
            need_night_trading = self._env.data_proxy.is_night_trading(self._env.get_universe())
            self._universe_changed = False

        start_time = datetime.now()
        while True:
            _update_trading_periods_if_universe_changed()
            self._market_event_publisher.publish_if_need(need_night_trading)
            try:
                events = [self._queue.get(timeout=1)]
            except Empty:
                continue
            while True:
                try:
                    events.append(self._queue.get_nowait())
                except Empty:
                    break
                if not events:
                    continue
            events = self._filter_events(events)
            for e in events:
                if e.event_type == EVENT.BAR and not is_trading(e.trading_dt, trading_periods):
                    continue
                if e.event_type == EVENT.TICK:
                    trading_periods = get_tick_trading_period(e.tick.order_book_id)
                    if not (is_trading(e.trading_dt, trading_periods) and e.calendar_dt >= start_time):
                        # 有可能会收到旧的 tick
                        continue
                yield e

    def _on_universe_change(self, event):
        self._universe_changed = True
        universe: Set = event.universe
        to_be_subscribed = universe - self._subscribed
        if to_be_subscribed:
            for ins in self._env.data_proxy.instruments(list(to_be_subscribed)):
                self._trading_code_map[ins.trading_code] = ins
                # TODO: 推动 VNPY 加入批量订阅的接口
                self._gateways[ins.account_type].subscribe(VNSubscribeRequest(
                    symbol=ins.trading_code,
                    exchange=EXCHANGE_MAP[ins.exchange]
                ))
        # TODO: 推动 vnpy 加入 unsubscribe
        self._subscribed = universe

    VN_ASKS_FIELDS = [f"ask_price_{i}" for i in range(1, 6)]
    VN_ASK_VOLS_FIELDS = [f"ask_volume_{i}" for i in range(1, 6)]
    VN_BIDS_FIELDS = [f"bid_price_{i}" for i in range(1, 6)]
    VN_BID_VOLS_FIELDS = [f"bid_volume_{i}" for i in range(1, 6)]

    def _on_tick(self, vn_event: VNEvent):
        # run in child thread
        vn_tick: VNTickData = vn_event.data
        try:
            ins = self._trading_code_map[vn_tick.symbol]
        except KeyError:
            return
        if ins.order_book_id not in self._subscribed:
            return
        # TODO: 构造 lazy tick，大部分 tick 都没啥用
        # TODO: total_turnover, prev_settlement
        tick = TickObject(
            instrument=ins,
            tick_dict={
                "datetime": vn_tick.datetime,
                "open": vn_tick.open_price,
                "last": vn_tick.last_price,
                "high": vn_tick.high_price,
                "low": vn_tick.low_price,
                "volume": vn_tick.volume,
                "open_interest": vn_tick.open_interest,
                "asks": [getattr(vn_tick, f) for f in self.VN_ASKS_FIELDS],
                "ask_vols": [getattr(vn_tick, f) for f in self.VN_ASK_VOLS_FIELDS],
                "bids": [getattr(vn_tick, f)  for f in self.VN_BIDS_FIELDS],
                "bid_vols": [getattr(vn_tick, f) for f in self.VN_BID_VOLS_FIELDS],
                "limit_up": vn_tick.limit_up,
                "limit_down": vn_tick.limit_down,
            }
        )
        dt = datetime.combine(tick.datetime.date(), tick.datetime.time())
        self._queue.put(Event(
            EVENT.TICK,
            calendar_dt=dt,
            trading_dt=self._env.data_proxy.get_trading_dt(dt),
            tick=tick
        ))

    def _filter_events(self, events):
        if len(events) == 1:
            return events

        seen = set()
        results = []
        for e in events[::-1]:
            if e.event_type == EVENT.BAR:
                if EVENT.BAR not in seen:
                    results.append(e)
                    seen.add(EVENT.BAR)
            elif e.event_type == EVENT.TICK:
                if e.tick.order_book_id not in self._subscribed:
                    continue
                if EVENT.TICK.value + e.tick.order_book_id not in seen:
                    results.append(e)
                    seen.add(EVENT.TICK.value + e.tick.order_book_id)
            elif e.event_type == EVENT.DO_PERSIST:
                if EVENT.DO_PERSIST not in seen:
                    results.append(e)
                    seen.add(EVENT.DO_PERSIST)
            else:
                results.append(e)
        return results[::-1]
