# -*- coding: utf-8 -*-
from datetime import timedelta, datetime, date
from threading import Thread
from enum import Enum

from rqalpha.utils.logger import system_log
from rqalpha.interface import AbstractEventSource
from rqalpha.events import Event, EVENT
from rqalpha.utils import RqAttrDict
from rqalpha.api import get_trading_dates


class TimePeriod(Enum):
    BEFORE_TRADING = 'before_trading'
    AFTER_TRADING = 'after_trading'
    TRADING = 'trading'
    CLOSING = 'closing'


# TODO: 目前只考虑了期货的场景
class VNPYEventSource(AbstractEventSource):
    def __init__(self, env, vnpy_engine):
        self._env = env
        self._engine = vnpy_engine
        self._before_trading_processed = False
        self._after_trading_processed = False
        self._time_period = None

    def mark_time_period(self, start_date, end_date):
        trading_days = self._env.data_proxy.get_trading_dates(start_date, end_date)

        def in_before_trading_time(time):
            return time.hour == 20 and time.minute < 55

        def in_after_trading(time):
            return (time.hour == 15 and time.minute >= 30) or time.hour == 16

        def in_trading_time(time):
            if time.hour < 15 or time.hour > 21:
                return True
            elif time.hour == 20 and time.minute >= 55:
                return True
            elif time.hour == 15 and time.minute < 30:
                return True
            else:
                return False

        def in_trading_day(time):
            if time.hour < 20:
                if time.date() in trading_days:
                    return True
            else:
                if (time + timedelta(days=1)).date() in trading_days:
                    return True
            return False

        while True:
            now = datetime.now()
            if not in_trading_day(now):
                self._time_period = TimePeriod.CLOSING
                continue
            if in_before_trading_time(now):
                self._time_period = TimePeriod.BEFORE_TRADING
                continue
            if in_after_trading(now):
                self._time_period = TimePeriod.AFTER_TRADING
                continue
            if in_trading_time(now):
                self._time_period = TimePeriod.TRADING
                continue
            else:
                self._time_period = TimePeriod.CLOSING

    def events(self, start_date, end_date, frequency):
        while datetime.now().date() < start_date:
            continue

        mark_time_thread = Thread(target=self.mark_time_period, args=(start_date, date.fromtimestamp(2147483647)))
        mark_time_thread.setDaemon(True)
        mark_time_thread.start()

        while True:
            if self._time_period == TimePeriod.BEFORE_TRADING:
                if self._after_trading_processed:
                    self._after_trading_processed = False
                if not self._before_trading_processed:
                    system_log.debug("VNPYEventSource: before trading event")
                    yield Event(EVENT.BEFORE_TRADING, datetime.now(), datetime.now() + timedelta(days=1))
                    self._before_trading_processed = True
                    continue
                else:
                    continue
            elif self._time_period == TimePeriod.TRADING:
                if not self._before_trading_processed:
                    system_log.debug("VNPYEventSource: before trading event")
                    yield Event(EVENT.BEFORE_TRADING, datetime.now(), datetime.now() + timedelta(days=1))
                    self._before_trading_processed = True
                    continue
                else:
                    tick = self._engine.get_tick()
                    calendar_dt = tick['datetime']
                    if calendar_dt.hour > 20:
                        trading_dt = calendar_dt + timedelta(days=1)
                    else:
                        trading_dt = calendar_dt
                    system_log.debug("VNPYEventSource: tick {}", tick)
                    yield Event(EVENT.TICK, calendar_dt, trading_dt, {"tick": RqAttrDict(tick)})
            elif self._time_period == TimePeriod.AFTER_TRADING:
                if self._before_trading_processed:
                    self._before_trading_processed = False
                if not self._after_trading_processed:
                    system_log.debug("VNPYEventSource: after trading event")
                    yield Event(EVENT.AFTER_TRADING, datetime.now(), datetime.now())
                    self._after_trading_processed = True
                else:
                    continue


if __name__ == '__main__':
    source = VNPYEventSource(None, None)
    mark_time_thread = Thread(target=source.mark_time_period, args=(date(2017, 1, 1), date(2017, 5, 1)))
    mark_time_thread.start()
    print(source._time_period)
