# encoding: UTF-8
from rqalpha.interface import AbstractBroker
from rqalpha.model.account import BenchmarkAccount, FutureAccount
from rqalpha.const import ACCOUNT_TYPE


def init_accounts(env):
    # FIXME: 从ctp获取获取账户信息，持仓等
    accounts = {}
    config = env.config
    start_date = config.base.start_date
    total_cash = 0
    future_starting_cash = config.base.future_starting_cash
    accounts[ACCOUNT_TYPE.FUTURE] = FutureAccount(env, future_starting_cash, start_date)
    if config.base.benchmark is not None:
        accounts[ACCOUNT_TYPE.BENCHMARK] = BenchmarkAccount(env, total_cash, start_date)

    return accounts


class VNPYBroker(AbstractBroker):
    def __init__(self, vnpy_engine):
        self. _accounts = None

        self._engine = vnpy_engine

        self._account_cache = None

    def after_trading(self):
        pass

    def before_trading(self):
        pass

    def get_open_orders(self, order_book_id=None):
        return self._engine.open_orders

    def submit_order(self, order):
        self._engine.send_order(order)

    def cancel_order(self, order):
        self._engine.cancel_order(order)

    def update(self, calendar_dt, trading_dt, bar_dict):
        pass

    def get_portfolio(self):
        return self._engine.get_portfolio()

    def get_benchmark_portfolio(self):
        return None
