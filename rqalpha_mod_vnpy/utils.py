from rqalpha.const import SIDE, ORDER_TYPE, POSITION_EFFECT

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


