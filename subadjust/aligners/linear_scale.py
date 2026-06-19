"""
LinearScaleAligner - 时间比例映射对齐器

通过找到对应的字幕条目（优先基于文本精确匹配，或等间距采样）后，
用最小二乘法拟合线性映射 y = scale * x + offset。
适合：字幕内容相同但帧率或偏移不同的场景。
"""

from typing import List, Tuple

from .base import BaseAligner, AlignerResult, register_aligner
from ..models import Subtitle


def _find_linear_mapping(src_points: List[float],
                     dst_points: List[float]) -> Tuple[float, float]:
    """最小二乘法拟合 y = scale * x + offset"""
    n = len(src_points)
    if n < 2:
        return 1.0, (dst_points[0] - src_points[0] if n >= 1 else 0.0)
    sum_x = sum(src_points)
    sum_y = sum(dst_points)
    sum_xy = sum(x * y for x, y in zip(src_points, dst_points))
    sum_xx = sum(x * x for x in src_points)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 1.0, (sum_y - sum_x) / n
    scale = (n * sum_xy - sum_x * sum_y) / denom
    offset = (sum_y - scale * sum_x) / n
    return scale, offset


def _collect_text_matches(source: Subtitle, reference: Subtitle) -> Tuple[List[float], List[float]]:
    """通过文本精确匹配收集对应点"""
    src_map = {}
    for cue in source.cues:
        text = cue.text.strip().lower()
        if text:
            src_map[text] = cue.start
    src_starts, dst_starts = [], []
    for ref_cue in reference.cues:
        text = ref_cue.text.strip().lower()
        if text and text in src_map:
            src_starts.append(src_map[text])
            dst_starts.append(ref_cue.start)
    return src_starts, dst_starts


def _collect_sample_points(source: Subtitle, reference: Subtitle,
                           num_points: int = 5) -> Tuple[List[float], List[float]]:
    """等间距采样（当文本匹配不够时）"""
    n = min(len(source.cues), len(reference.cues))
    if n < 2:
        return [], []
    src_starts, dst_starts = [], []
    step = max(1, n // num_points)
    for i in range(0, n, step):
        src_starts.append(source.cues[i].start)
        dst_starts.append(reference.cues[i].start)
    if (not src_starts) or src_starts[-1] != source.cues[n - 1].start:
        src_starts.append(source.cues[n - 1].start)
        dst_starts.append(reference.cues[n - 1].start)
    return src_starts, dst_starts


@register_aligner
class LinearScaleAligner(BaseAligner):
    """时间比例映射对齐器

    策略：先尝试文本精确匹配找对应点，不足则等间距采样，再用最小二乘法拟合线性映射。
    """

    name = 'linear_scale'
    description = '时间比例映射（线性回归拟合 scale + offset）'

    min_match_points = 2
    sample_points = 5

    def compute(self, source: Subtitle, reference: Subtitle) -> AlignerResult:
        if not reference.cues or not source.cues:
            return AlignerResult(method=self.name)

        src_starts, dst_starts = _collect_text_matches(source, reference)

        if len(src_starts) < self.min_match_points:
            sampled_src, sampled_dst = _collect_sample_points(
                source, reference, self.sample_points)
            if len(sampled_src) >= self.min_match_points:
                src_starts, dst_starts = sampled_src, sampled_dst

        if len(src_starts) < self.min_match_points:
            if reference.cues and source.cues:
                return AlignerResult(
                    scale=1.0,
                    offset=reference.cues[0].start - source.cues[0].start,
                    matched_points=[(source.cues[0].start, reference.cues[0].start)],
                    method=self.name
                )
            return AlignerResult(method=self.name)

        scale, offset = _find_linear_mapping(src_starts, dst_starts)
        matched = list(zip(src_starts, dst_starts))

        return AlignerResult(
            scale=scale,
            offset=offset,
            matched_points=matched,
            method=self.name,
            params={
                'matched_count': len(matched),
                'match_type': ('text'
                               if len(_collect_text_matches(source, reference)[0]) == len(src_starts)
                               else 'sample')
            }
        )
