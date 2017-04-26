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
from time import sleep
from rqalpha.utils.logger import system_log

from .api import CtpTdApi, CtpMdApi
from .data_cache import DataCache


class CtpGateway(object):
    def __init__(self, temp_path, user_id, password, broker_id, retry_times=5, retry_interval=1):
        self.td_api = None
        self.md_api = None

        self.temp_path = temp_path
        self.user_id = user_id
        self.password = password
        self.broker_id = broker_id

        self._retry_times = retry_times
        self._retry_interval = retry_interval

        self._query_returns = {}
        self._cache = DataCache()
        self.subscribed = []

    def init_md_api(self, md_address):
        self.md_api = CtpMdApi(self, self.temp_path, self.user_id, self.password, self.broker_id, md_address)
        self._query_returns[self.md_api.api_name] = {}

    def init_td_api(self, td_address, auth_code=None, user_production_info=None):
        self.td_api = CtpTdApi(self, self.temp_path, self.user_id, self.password, self.broker_id, td_address, auth_code, user_production_info)
        self._query_returns[self.td_api.api_name] = {}

    def get_exchagne_id(self, order_book_id):
        try:
            return self._cache.ins[order_book_id].exchange_id
        except KeyError:
            return None

    def get_instrument_id(self, order_book_id):
        try:
            return self._cache.ins[order_book_id].instrument_id
        except KeyError:
            return None

    def on_query(self, api_name, n, result):
        self._query_returns[api_name][n] = result

    def on_log(self, log):
        system_log.info(log)

    def on_err(self, error):
        system_log.error('CTP 错误，错误代码：%s，错误信息：%s' % (str(error['ErrorID']), error['ErrorMsg']))

    def on_order(self):
        pass

    def on_trade(self):
        pass

    def connect(self):
        if self.md_api:
            for i in range(self._retry_times):
                self.md_api.connect()
                sleep(self._retry_interval * (i+1))
                if self.md_api.logged_in:
                    self.on_log('CTP 行情服务器登录成功')
                    break
            else:
                raise RuntimeError('CTP 行情服务器连接或登录超时')

        if self.td_api:
            for i in range(self._retry_times):
                self.td_api.connect()
                sleep(self._retry_interval * (i+1))
                if self.td_api.logged_in:
                    self.on_log('CTP 交易服务器登录成功')
                    break
            else:
                raise RuntimeError('CTP 交易服务器连接或登录超时')
        else:
            raise RuntimeError('CTP 交易服务器必须被初始化')

    def _qry_instrumnent(self):
        for i in range(self._retry_times):
            req_id = self.td_api.qryInstrument()
            sleep(self._retry_interval * (i+1))
            if req_id in self._query_returns[self.td_api.api_name]:
                ins_cache = self._query_returns[self.td_api.api_name][req_id].copy()
                del self._query_returns[self.td_api.api_name][req_id]
                return ins_cache
        else:
            raise RuntimeError('请求合约数据超时')

    def _qry_position(self):
        for i in range(self._retry_times):
            req_id = self.td_api.qryPosition()
            sleep(self._retry_interval * (i+1))
            if req_id in self._query_returns[self.td_api.api_name]:
                positions = self._query_returns[self.td_api.api_name][req_id].copy()
                del self._query_returns[self.td_api.api_name][req_id]
                return positions
        # 持仓数据有可能不返回

    def _qry_account(self):
        for i in range(self._retry_times):
            req_id = self.td_api.qryAccount()
            sleep(self._retry_interval * (i+1))
            if req_id in self._query_returns[self.td_api.api_name]:
                account_dict = self._query_returns[self.td_api.api_name][req_id].copy()
                del self._query_returns[self.td_api.api_name][req_id]
                return account_dict
        else:
            raise RuntimeError('请求账户数据超时')

    def _qry_commission(self, order_book_id):
        for i in range(self._retry_times):
            req_id = self.td_api.qryCommission(order_book_id)
            sleep(self._retry_interval * (i+1))
            if req_id in self._query_returns[self.td_api.api_name]:
                commission_dict = self._query_returns[self.td_api.api_name][req_id].copy()
                del self._query_returns[self.td_api.api_name][req_id]
                return commission_dict
        # commission 数据有可能不返回

    def _qry_order(self):
        for i in range(self._retry_times):
            req_id = self.td_api.qryOrder()
            sleep(self._retry_interval * (i+1))
            if req_id in self._query_returns[self.td_api.api_name]:
                order_dict = self._query_returns[self.td_api.api_name][req_id].copy()
                del self._query_returns[self.td_api.api_name][req_id]
                return order_dict
        # order 数据有可能不返回

    def qry_instrument(self):
        ins_cache = self._qry_instrumnent()
        self._cache.cache_ins(ins_cache)

    def qry_account(self):
        account_dict = self._qry_account()
        self._cache.cache_account(account_dict)

    def qry_position(self):
        positions = self._qry_position()
        self._cache.cache_position(positions)

    def qry_order(self):
        order_cache = self._qry_order()
        self._cache.cache_order(order_cache)


