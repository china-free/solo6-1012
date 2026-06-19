"""
对齐策略抽象基类和注册机制
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Type
import importlib

from ..models import Subtitle
from ..report import AdjustmentReport


@dataclass
class AlignerResult:
    """对齐器计算结果"""
    scale: float = 1.0
    offset: float = 0.0
    matched_points: List[Tuple[float, float]] = field(default_factory=list)
    method: str = ''
    params: Dict = field(default_factory=dict)

    def apply(self, t: float) -> float:
        """将映射应用到时间点"""
        return t * self.scale + self.offset


class BaseAligner(ABC):
    """对齐策略抽象基类"""

    name: str = 'base'
    description: str = '基础对齐器'

    @abstractmethod
    def compute(self, source: Subtitle, reference: Subtitle) -> AlignerResult:
        """
        计算源字幕到参考字幕的映射参数

        Args:
            source: 待校正字幕
            reference: 参考字幕（正确时间轴）

        Returns:
            AlignerResult 包含 scale 和 offset
        """
        raise NotImplementedError


ALIGNERS: Dict[str, Type[BaseAligner]] = {}


def register_aligner(cls: Type[BaseAligner]) -> Type[BaseAligner]:
    """注册对齐器的装饰器"""
    if not hasattr(cls, 'name') or not cls.name:
        raise ValueError(f'对齐器 {cls.__name__} 必须定义 name 属性')
    ALIGNERS[cls.name] = cls
    return cls


def get_aligner(name: str) -> BaseAligner:
    """获取对齐器实例"""
    name = name.lower().replace('-', '_').replace(' ', '_')
    if name not in ALIGNERS:
        available = ', '.join(sorted(ALIGNERS.keys()))
        raise ValueError(f'未知的对齐算法: {name}，可用算法: {available}')
    return ALIGNERS[name]()


def list_aligners() -> List[Tuple[str, str]]:
    """列出所有已注册的对齐算法"""
    return [(name, cls.description) for name, cls in ALIGNERS.items()]
