"""
字幕时间轴核心数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Cue:
    """单条字幕条目"""
    index: int
    start: float
    end: float
    text: str
    style: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def clone(self) -> 'Cue':
        return Cue(
            index=self.index,
            start=self.start,
            end=self.end,
            text=self.text,
            style=self.style,
            extra=dict(self.extra)
        )


@dataclass
class Subtitle:
    """完整字幕文件数据"""
    format: str
    cues: List[Cue]
    header: str = ''
    footer: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)
    encoding: str = 'utf-8'

    @property
    def cue_count(self) -> int:
        return len(self.cues)

    @property
    def total_duration(self) -> float:
        if not self.cues:
            return 0.0
        return self.cues[-1].end - self.cues[0].start

    def sort_cues(self) -> None:
        self.cues.sort(key=lambda c: c.start)
        for i, cue in enumerate(self.cues):
            cue.index = i + 1
