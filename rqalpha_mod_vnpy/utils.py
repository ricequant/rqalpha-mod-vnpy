# -*- coding: utf-8 -*-
#
# Copyright 2017 Ricequant, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import timedelta
import re

from rqalpha.environment import Environment
from rqalpha.const import HEDGE_TYPE, POSITION_EFFECT, COMMISSION_TYPE
from .vnpy import *


def make_underlying_symbol(id_or_symbol):
    return filter(lambda x: x not in '0123456789 ', id_or_symbol).upper()


def make_position_effect(vnpy_exchange, vnpy_offset):
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


def make_order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


def make_trading_dt(calendar_dt):
    # FIXME: 替换为 next_trading_date
    if calendar_dt.hour > 20:
        return calendar_dt + timedelta(days=1)
    return calendar_dt


def cal_commission(order_book_id, position_effect, price, amount, hedge_type=HEDGE_TYPE.SPECULATION):
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


def is_future(order_book_id):
    if order_book_id is None:
        return False
    return re.match('^[a-zA-Z]+[0-9]+$', order_book_id) is not None

