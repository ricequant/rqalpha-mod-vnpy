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
from rqalpha.const import POSITION_EFFECT, COMMISSION_TYPE


def make_underlying_symbol(id_or_symbol):
    return filter(lambda x: x not in '0123456789 ', id_or_symbol).upper()


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


def cal_commission(trade_dict, position_effect):
    order_book_id = trade_dict.order_book_id
    env = Environment.get_instance()
    info = env.data_proxy.get_commission_info(order_book_id)
    commission = 0
    if info['commission_type'] == COMMISSION_TYPE.BY_MONEY:
        contract_multiplier = env.get_instrument(trade_dict.order_book_id).contract_multiplier
        if position_effect == POSITION_EFFECT.OPEN:
            commission += trade_dict.price * trade_dict.amount * contract_multiplier * info['open_commission_ratio']
        elif position_effect == POSITION_EFFECT.CLOSE:
            commission += trade_dict.price * trade_dict.amount * contract_multiplier * info['close_commission_ratio']
        elif position_effect == POSITION_EFFECT.CLOSE_TODAY:
            commission += trade_dict.price * trade_dict.amount * contract_multiplier * info['close_commission_today_ratio']
    else:
        if position_effect == POSITION_EFFECT.OPEN:
            commission += trade_dict.amount * info['open_commission_ratio']
        elif position_effect == POSITION_EFFECT.CLOSE:
            commission += trade_dict.amount * info['close_commission_ratio']
        elif position_effect == POSITION_EFFECT.CLOSE_TODAY:
            commission += trade_dict.amount * info['close_commission_today_ratio']
    return commission


def is_future(order_book_id):
    if order_book_id is None:
        return False
    return re.match('^[a-zA-Z]+[0-9]+$', order_book_id) is not None

