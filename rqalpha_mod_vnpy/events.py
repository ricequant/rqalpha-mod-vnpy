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
