from typing import Union

from vnpy.trader.constant import (
    Exchange as VNExchange, Direction as VNDirection, Offset as VNOffset, OrderType as VNOrderType
)

from rqalpha.const import DEFAULT_ACCOUNT_TYPE, EXCHANGE, SIDE, POSITION_EFFECT, ORDER_TYPE

ACCOUNT_TYPE = Union[DEFAULT_ACCOUNT_TYPE, str]

EXCHANGE_MAP = {
    EXCHANGE.XSHE: VNExchange.SSE,
    EXCHANGE.XSHG: VNExchange.SZSE,
    EXCHANGE.SHFE: VNExchange.SHFE,
    EXCHANGE.CFFEX: VNExchange.CFFEX,
    EXCHANGE.DCE: VNExchange.DCE,
    EXCHANGE.INE: VNExchange.INE,
    EXCHANGE.CZCE: VNExchange.CZCE
}

DIRECTION_OFFSET_MAP = {
    (SIDE.BUY, POSITION_EFFECT.OPEN): (VNDirection.LONG, VNOffset.OPEN),
    (SIDE.SELL, POSITION_EFFECT.OPEN): (VNDirection.SHORT, VNOffset.OPEN),
    (SIDE.SELL, POSITION_EFFECT.CLOSE): (VNDirection.LONG, VNOffset.CLOSE),
    (SIDE.BUY, POSITION_EFFECT.CLOSE): (VNDirection.SHORT, VNOffset.CLOSE),
    (SIDE.SELL, POSITION_EFFECT.CLOSE_TODAY): (VNDirection.LONG, VNOffset.CLOSETODAY),
    (SIDE.BUY, POSITION_EFFECT.CLOSE_TODAY): (VNDirection.SHORT, VNOffset.CLOSETODAY)
}

ORDER_TYPE_MAP = {
    ORDER_TYPE.MARKET: VNOrderType.MARKET,
    ORDER_TYPE.LIMIT: VNOrderType.LIMIT
}

