from rqalpha.const import SIDE, ORDER_TYPE, POSITION_EFFECT, COMMISSION_TYPE, HEDGE_TYPE
from rqalpha.environment import Environment

from .vnpy import DIRECTION_LONG, DIRECTION_SHORT
from .vnpy import PRICETYPE_LIMITPRICE, PRICETYPE_MARKETPRICE
from .vnpy import OFFSET_CLOSE, OFFSET_OPEN

SIDE_MAPPING = {
    SIDE.BUY: DIRECTION_LONG,
    SIDE.SELL: DIRECTION_SHORT
}

SIDE_REVERSE = {
    DIRECTION_LONG: SIDE.BUY,
    DIRECTION_SHORT: SIDE.SELL,
}

ORDER_TYPE_MAPPING = {
    ORDER_TYPE.MARKET: PRICETYPE_MARKETPRICE,
    ORDER_TYPE.LIMIT: PRICETYPE_LIMITPRICE
}

POSITION_EFFECT_MAPPING = {
    POSITION_EFFECT.OPEN: OFFSET_OPEN,
    POSITION_EFFECT.CLOSE: OFFSET_CLOSE,
}

POSITION_EFFECT_REVERSE = {
    OFFSET_OPEN: POSITION_EFFECT.OPEN,
    OFFSET_CLOSE: POSITION_EFFECT.CLOSE,
}


def symbol_2_order_book_id(symbol):
    if len(symbol) < 4:
        return None
    if symbol[-4] not in '0123456789':
        order_book_id = symbol[:2] + '1' + symbol[-3:]
    else:
        order_book_id = symbol
    return order_book_id.upper()


def get_commission(trade, hedge_type=HEDGE_TYPE.SPECULATION):
    order_book_id = trade.order_book_id
    info = Environment.get_instance().get_future_commission_info(order_book_id, hedge_type)
    commission = 0
    if info['commission_type'] == COMMISSION_TYPE.BY_MONEY:
        contract_multiplier = Environment.get_instance().get_instrument(trade.order_book_id).contract_multiplier
        if trade.position_effect == POSITION_EFFECT.OPEN:
            commission += trade.last_price * trade.last_quantity * contract_multiplier * info['open_commission_ratio']
        else:
            commission += trade.last_price * (trade.last_quantity - trade._close_today_amount) * contract_multiplier * \
                          info[
                              'close_commission_ratio']
            commission += trade.last_price * trade._close_today_amount * contract_multiplier * info[
                'close_commission_today_ratio']
    else:
        if trade.order.position_effect == POSITION_EFFECT.OPEN:
            commission += trade.last_quantity * info['open_commission_ratio']
        else:
            commission += (trade.last_quantity - trade._close_today_amount) * info['close_commission_ratio']
            commission += trade._close_today_amount * info['close_commission_today_ratio']
    return commission
