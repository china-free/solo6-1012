"""
TimeSeriesAligner - 基于时间序列规整的对齐器

利用字幕时间轴的相对结构进行对齐：
1. 计算两个字幕时间序列的锚点（起始点、中点、结束点、四分位数点）
2. 对锚点进行动态规划匹配，最小化 (src_pos - ref_pos) 的偏差
3. 拟合出分段或全局线性映射

适合：字幕条数大致相同、整体结构相似但文本差异大（不同语言）的场景。
"""

from typing import List, Tuple

from .base import BaseAligner, AlignerResult, register_aligner
from .linear_scale import _find_linear_mapping
from ..models import Subtitle, Cue


def _get_keypoints(cues: List[Cue], num_points: int = 9) -> List[float]:
    """提取关键时间点：起始 + 均匀分位数 + 结束"""
    if not cues:
        return []
    starts = [c.start for c in cues]
    n = len(starts)
    if n == 0:
        return []
    if n == 1:
        return [starts[0], starts[0]]
    total = starts[-1] - starts[0]
    keypoints = []
    for i in range(num_points):
        ratio = i / (num_points - 1)
        idx = int(ratio * (n - 1))
        keypoints.append(starts[idx])
    if starts[0] not in keypoints:
        keypoints.insert(0, starts[0])
    if starts[-1] not in keypoints:
        keypoints.append(starts[-1])
    return keypoints


def _dynamic_align(src_points: List[float], ref_points: List[float],
                   skew_penalty: float = 0.1) -> List[Tuple[float, float]]:
    """
    基于动态规划的关键点匹配：最小化 (ref_pos - (scale * src_pos + offset)) 的偏差

    简化实现：枚举两端点组合，找使得中间点总偏差最小的映射参数，
    然后在这个全局映射基础上过滤出匹配对。
    """
    n_s, n_r = len(src_points), len(ref_points)
    if n_s < 2 or n_r < 2:
        return list(zip(src_points, ref_points))

    best_scale, best_offset = 1.0, 0.0
    best_error = float('inf')

    for s_start in [0, min(1, n_s - 1)]:
        for r_start in [0, min(1, n_r - 1)]:
            for s_end in [n_s - 1, max(n_s - 2, 0)]:
                for r_end in [n_r - 1, max(n_r - 2, 0)]:
                    if s_end <= s_start or r_end <= r_start:
                        continue
                    src_dur = src_points[s_end] - src_points[s_start]
                    ref_dur = ref_points[r_end] - ref_points[r_start]
                    if abs(src_dur) < 1e-6:
                        continue
                    scale = ref_dur / src_dur
                    if scale < 0.1 or scale > 10.0:
                        continue
                    offset = ref_points[r_start] - scale * src_points[s_start]
                    err = 0.0
                    samples = min(n_s, n_r, 20)
                    for i in range(samples):
                        s_idx = int((i / max(1, samples - 1)) * (n_s - 1))
                        r_idx = int((i / max(1, samples - 1)) * (n_r - 1))
                        pred = scale * src_points[s_idx] + offset
                        err += abs(pred - ref_points[r_idx])
                    err += skew_penalty * abs(scale - 1.0) * 100
                    if err < best_error:
                        best_error = err
                        best_scale = scale
                        best_offset = offset

    matched: List[Tuple[float, float]] = []
    used_r = set()
    for s_idx, sp in enumerate(src_points):
        pred = best_scale * sp + best_offset
        best_r = -1
        best_d = float('inf')
        for r_idx, rp in enumerate(ref_points):
            if r_idx in used_r:
                continue
            d = abs(rp - pred)
            if d < best_d:
                best_d = d
                best_r = r_idx
        if best_r >= 0 and best_d < max(10.0, abs(best_scale * sp + best_offset) * 0.5 + 5):
            matched.append((sp, ref_points[best_r]))
            used_r.add(best_r)

    if len(matched) < 2:
        matched = [(src_points[0], ref_points[0]), (src_points[-1], ref_points[-1])]

    return matched


@register_aligner
class TimeSeriesAligner(BaseAligner):
    """基于时间序列结构的对齐器

    策略：从两个字幕序列提取关键时间点，用动态规划找最优的 scale/offset，
    然后在此基础上进行关键点匹配。
    适合：文本差异大但字幕时间结构相似的场景（如完全不同的语言、仅结构对齐）。
    """

    name = 'time_series'
    description = '时间序列规整（仅利用时间轴结构，不依赖文本内容）'

    keypoint_count = 9

    def compute(self, source: Subtitle, reference: Subtitle) -> AlignerResult:
        if not reference.cues or not source.cues:
            return AlignerResult(method=self.name)

        src_keypoints = _get_keypoints(source.cues, self.keypoint_count)
        ref_keypoints = _get_keypoints(reference.cues, self.keypoint_count)

        if len(src_keypoints) < 2 or len(ref_keypoints) < 2:
            if source.cues and reference.cues:
                return AlignerResult(
                    scale=1.0,
                    offset=reference.cues[0].start - source.cues[0].start,
                    matched_points=[(source.cues[0].start, reference.cues[0].start)],
                    method=self.name
                )
            return AlignerResult(method=self.name)

        matched = _dynamic_align(src_keypoints, ref_keypoints)

        src_starts = [m[0] for m in matched]
        dst_starts = [m[1] for m in matched]
        scale, offset = _find_linear_mapping(src_starts, dst_starts)

        return AlignerResult(
            scale=scale,
            offset=offset,
            matched_points=matched,
            method=self.name,
            params={
                'matched_count': len(matched),
                'src_keypoint_count': len(src_keypoints),
                'ref_keypoint_count': len(ref_keypoints),
            }
        )
