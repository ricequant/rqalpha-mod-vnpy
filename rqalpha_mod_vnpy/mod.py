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

from time import sleep
from queue import Queue
from importlib import import_module
from typing import Optional, Dict

from vnpy.event import EventEngine as VNEventEngine
from vnpy.trader.gateway import BaseGateway as VNBaseGateway
from vnpy.trader.event import EVENT_LOG as VN_EVENT_LOG

from rqalpha.environment import Environment
from rqalpha.const import RUN_TYPE
from rqalpha.core.events import EVENT
from rqalpha.utils.logger import system_log
from rqalpha.interface import AbstractMod

from .event_source import EventSource
from .broker import Broker
from .consts import ACCOUNT_TYPE, LOG_LEVEL_MAP
from .utils import get_mac_address, get_ip_address


class VNPYMod(AbstractMod):
    def __init__(self):
        self._vn_gateways: Dict[ACCOUNT_TYPE, VNBaseGateway] = {}
        self._vn_gateway_settings: Dict[ACCOUNT_TYPE, Dict] = {}
        self._vn_event_engine: Optional[VNEventEngine] = None
        self._vn_event_engine_started = False

    def start_up(self, env: Environment, mod_config):
        if not mod_config.gateways:
            system_log.info("未设置 gateways，rqalpha-mod-vnpy 关闭")
            return
        if env.config.base.run_type != RUN_TYPE.LIVE_TRADING:
            system_log.info(f"run in {env.config.base.run_type}，vnpy mod disabled")
            return

        if mod_config.full_day_mode:
            system_log.warn("全天交易模式启动，改模式仅用于调试，请勿在生产环境开启!!!")
            from . import event_source
            event_source.is_trading = lambda dt, tp: True

        self._vn_event_engine = VNEventEngine()
        self._vn_event_engine.register(VN_EVENT_LOG, lambda e: system_log.log(
            LOG_LEVEL_MAP[e.data.level], f"[VN.PY]{e.data.msg}"
        ))
        for account_type, gateway_config in mod_config.gateways.items():
            gateway_app = gateway_config["app"]
            module_path, cls_name = gateway_app.split(":")
            gateway_cls = getattr(import_module(module_path), cls_name)
            if not issubclass(gateway_cls, VNBaseGateway):
                raise ValueError(f"{gateway_app} is not a VN.PY BaseGateway")
            account_type = account_type.upper()
            self._vn_gateways[account_type] = gateway_cls(self._vn_event_engine, gateway_config.get("name", cls_name))
            self._vn_gateway_settings[account_type] = gateway_config["settings"]

        self._vn_event_engine.start()
        self._vn_event_engine_started = True
        for account_type, vn_gateway in self._vn_gateways.items():
            system_log.debug(f"VN.PY gateway {vn_gateway.gateway_name} connecting..")
            vn_gateway.connect(self._vn_gateway_settings[account_type])

        # TODO: 等待 VN.PY gateway 真正 ready 后再执行策略逻辑，这里需要 VN.PY gateway 给出连接状态
        sleep(5)
        rqa_event_queue = Queue()
        env.set_broker(Broker(env, rqa_event_queue, self._vn_event_engine, self._vn_gateways))
        env.set_event_source(EventSource(env, rqa_event_queue, self._vn_event_engine, self._vn_gateways))

        env.event_bus.add_listener(EVENT.POST_SYSTEM_INIT, self._post_system_init)

    def tear_down(self, code, exception=None):
        for vn_gateway in self._vn_gateways.values():
            vn_gateway.close()
        if self._vn_event_engine_started:
            self._vn_event_engine.stop()

    def _post_system_init(self, _):
        system_log.info(f"IP address: {get_ip_address()}")
        system_log.info(f"MAC address: {get_mac_address()}")
