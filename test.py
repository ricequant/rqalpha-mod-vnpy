import sys
from datetime import date, datetime, time

import rqdatac

from rqalpha import run_func

config = {
    "base": {
        "run_type": "r",
        "frequency": "tick",
        "accounts": {
            "future": 1000000
        },
        "start_date": date.today(),
        "end_date": "20991231",
        "rqdatac_uri": "tcp://rice:rice@192.168.10.11:16010"
    },
    "extra": {
        "log_level": "debug"
    },
    "mod": {
        "vnpy": {
            "enabled": True,
            "gateways": {"FUTURE": {
                "name": "CTP",
                "app": "vnpy.gateway.ctp:CtpGateway",
                "settings": {
                    "用户名": "",
                    "密码": "",
                    "经纪商代码": "9999",
                    "交易服务器": "tcp://180.168.146.187:10201",
                    "行情服务器": "tcp://180.168.146.187:10211",
                    "产品名称": "simnow_client_test",
                    "授权编码": "0000000000000000"
                }
            }}
        },
        "option": {
            "enabled": True
        },
        "realtime": {
            "enabled": True
        }
    }
}


def init(context):
    context.counter = 0
    context.target_contract = None
    context.contracts = rqdatac.options.get_contracts("CU", "C", maturity="2108", trading_date=date.today())
    subscribe(context.contracts)
    print(f"{len(context.contracts)} contracts subscribed: {context.contracts}")


def handle_tick(context, tick):
    context.counter += 1
    if context.counter <= 50:
        print(tick)
    if context.counter == 1:
        context.target_contract = tick.order_book_id
        print(f"BUY_OPEN {context.target_contract}")
        buy_open(tick.order_book_id, 1, tick.limit_up)
    if context.counter <= 10:
        print(get_position(context.target_contract, POSITION_DIRECTION.LONG))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test.py <SIMNOW_username> <SIMNOW_password>")
    else:
        ctp_settings: dict = config["mod"]["vnpy"]["gateways"]["FUTURE"]["settings"]
        _, ctp_settings["用户名"], ctp_settings["密码"] = sys.argv
        if time(15, 30) <= datetime.now().time() < time(21):
            # simnow 24 小时服务器
            ctp_settings["交易服务器"] = "tcp://180.168.146.187:10130",
            ctp_settings["行情服务器"] = "tcp://180.168.146.187:10131"
        run_func(config=config, init=init, handle_tick=handle_tick)
