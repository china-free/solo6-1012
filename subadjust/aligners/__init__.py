"""
对齐策略模块 - 可插拔的参考字幕对齐算法

提供多种对齐算法：
  - linear_scale:    时间比例映射（基于对应点的线性回归）
  - text_similarity: 基于文本相似度匹配对应点
  - time_series:     基于时间序列规整（动态规划对齐）
"""

from .base import (
    BaseAligner,
    AlignerResult,
    register_aligner,
    get_aligner,
    list_aligners,
    ALIGNERS,
)
from .linear_scale import LinearScaleAligner
from .text_similarity import TextSimilarityAligner
from .time_series import TimeSeriesAligner

__all__ = [
    'BaseAligner',
    'AlignerResult',
    'register_aligner',
    'get_aligner',
    'list_aligners',
    'ALIGNERS',
    'LinearScaleAligner',
    'TextSimilarityAligner',
    'TimeSeriesAligner',
]
