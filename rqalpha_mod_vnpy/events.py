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

from queue import Queue
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from rqalpha.environment import Environment
from rqalpha.core.events import Event, EVENT

from vnpy.event import EventEngine as VNPYEventEngine, Event as VNEvent

VNPY_EVENT = "VNPY_EVENT"


class EventEngine(VNPYEventEngine):
    # TODO：事件从产生到进入 rqa 主线程经过了两个 queue，性能较差
    #  未来如果能够推动 VNPYEventEngine 定义相对规范的接口，可以通过重写 VNPYEventEngine 的方式减少调一个 queue
    def __init__(self, env: Environment, rqa_event_queue: Queue, interval: int = 1):
        super(EventEngine, self).__init__(interval)
        self._rqa_event_queue = rqa_event_queue
        self._vn_event_listener: Dict[str, List[Callable[[VNEvent], Optional[bool]]]]= defaultdict(list)

        env.event_bus.add_listener(VNPY_EVENT, self._on_rqa_vn_event)

    def _on_vn_event(self, vn_event: VNEvent):
        # run in child thread
        if vn_event.type not in self._vn_event_listener:
            return
        self._rqa_event_queue.put(Event(VNPY_EVENT, vn_event=vn_event))

    def _on_rqa_vn_event(self, event: Event):
        # run in rqa main thread
        vn_event: VNEvent = event.vn_event  # noqa
        for listener in self._vn_event_listener[vn_event.type]:
            if listener(vn_event):
                # 如果返回 True ，那么消息不再传递下去
                break

    def add_rqa_listener(self, vnpy_event_type: str, listener: Callable[[VNEvent], Optional[bool]]):
        self.register(vnpy_event_type, self._on_vn_event)
        self._vn_event_listener[vnpy_event_type].append(listener)
