"""
核心校正算法
支持：整体偏移、分段校正、倍速校正、参考字幕对齐
"""

from typing import List, Optional, Tuple
from .models import Subtitle, Cue
from .report import AdjustmentReport, CueAdjustment


def _record_adjustment(original_cue: Cue, new_cue: Cue,
                       adjustments: List[CueAdjustment]) -> None:
    """记录单条字幕的调整"""
    if (abs(original_cue.start - new_cue.start) > 1e-6 or
            abs(original_cue.end - new_cue.end) > 1e-6):
        adjustments.append(CueAdjustment(
            index=new_cue.index,
            original_start=original_cue.start,
            original_end=original_cue.end,
            new_start=new_cue.start,
            new_end=new_cue.end
        ))


def apply_offset(subtitle: Subtitle, offset_seconds: float,
                 start_from: Optional[float] = None) -> AdjustmentReport:
    """
    整体时间轴偏移校正

    Args:
        subtitle: 字幕对象
        offset_seconds: 偏移秒数，正数延后，负数提前
        start_from: 仅对该时间点（秒）之后的字幕应用偏移，None 表示全部

    Returns:
        校正报告
    """
    adjustments: List[CueAdjustment] = []
    original_cues = [cue.clone() for cue in subtitle.cues]

    for original, cue in zip(original_cues, subtitle.cues):
        if start_from is not None and cue.start < start_from:
            continue
        cue.start += offset_seconds
        cue.end += offset_seconds
        if cue.start < 0:
            cue.start = 0.0
        if cue.end < cue.start:
            cue.end = cue.start
        _record_adjustment(original, cue, adjustments)

    subtitle.sort_cues()

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='offset',
        method_params={
            'offset_seconds': offset_seconds,
            'start_from': start_from,
        }
    )


def apply_segmented_offsets(subtitle: Subtitle,
                            segments: List[Tuple[float, float]]) -> AdjustmentReport:
    """
    分段偏移校正

    Args:
        subtitle: 字幕对象
        segments: 分段列表，每个元素为 (start_time_seconds, offset_seconds)
                  按 start_time 升序排列，每个分段应用于 start_time 之后的字幕

    Returns:
        校正报告
    """
    segments = sorted(segments, key=lambda x: x[0])
    adjustments: List[CueAdjustment] = []
    original_cues = [cue.clone() for cue in subtitle.cues]

    def get_offset(time_point: float) -> float:
        offset = 0.0
        for seg_start, seg_offset in segments:
            if time_point >= seg_start:
                offset += seg_offset
            else:
                break
        return offset

    for original, cue in zip(original_cues, subtitle.cues):
        offset = get_offset(cue.start)
        if abs(offset) > 1e-6:
            cue.start += offset
            cue.end += offset
            if cue.start < 0:
                cue.start = 0.0
            if cue.end < cue.start:
                cue.end = cue.start
        _record_adjustment(original, cue, adjustments)

    subtitle.sort_cues()

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='segmented',
        method_params={
            'segments': [{'start': s, 'offset': o} for s, o in segments],
        }
    )


def apply_speed(subtitle: Subtitle, source_fps: float, target_fps: float,
                anchor: float = 0.0) -> AdjustmentReport:
    """
    倍速校正（帧率转换）

    Args:
        subtitle: 字幕对象
        source_fps: 原始帧率（如 23.976）
        target_fps: 目标帧率（如 25.0）
        anchor: 锚点时间（秒），该点时间不变，默认为 0

    Returns:
        校正报告
    """
    if source_fps <= 0 or target_fps <= 0:
        raise ValueError('帧率必须为正数')

    ratio = source_fps / target_fps
    adjustments: List[CueAdjustment] = []
    original_cues = [cue.clone() for cue in subtitle.cues]

    for original, cue in zip(original_cues, subtitle.cues):
        cue.start = anchor + (cue.start - anchor) * ratio
        cue.end = anchor + (cue.end - anchor) * ratio
        if cue.start < 0:
            cue.start = 0.0
        if cue.end < cue.start:
            cue.end = cue.start
        _record_adjustment(original, cue, adjustments)

    subtitle.sort_cues()

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='speed',
        method_params={
            'source_fps': source_fps,
            'target_fps': target_fps,
            'ratio': ratio,
            'anchor': anchor,
        }
    )


def apply_linear_scale(subtitle: Subtitle, scale: float,
                       anchor: float = 0.0) -> AdjustmentReport:
    """
    线性缩放校正

    Args:
        subtitle: 字幕对象
        scale: 缩放系数，>1 拉长时间轴，<1 压缩
        anchor: 锚点时间（秒），该点时间不变

    Returns:
        校正报告
    """
    if scale <= 0:
        raise ValueError('缩放系数必须为正数')

    adjustments: List[CueAdjustment] = []
    original_cues = [cue.clone() for cue in subtitle.cues]

    for original, cue in zip(original_cues, subtitle.cues):
        cue.start = anchor + (cue.start - anchor) * scale
        cue.end = anchor + (cue.end - anchor) * scale
        if cue.start < 0:
            cue.start = 0.0
        if cue.end < cue.start:
            cue.end = cue.start
        _record_adjustment(original, cue, adjustments)

    subtitle.sort_cues()

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='linear_scale',
        method_params={
            'scale': scale,
            'anchor': anchor,
        }
    )


def _find_linear_mapping(src_points: List[float],
                         dst_points: List[float]) -> Tuple[float, float]:
    """
    通过两组对应点计算线性映射系数 y = scale * x + offset
    使用最小二乘法
    """
    n = len(src_points)
    if n < 2:
        return 1.0, (dst_points[0] - src_points[0]) if n >= 1 else 0.0
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


def align_to_reference(subtitle: Subtitle, reference: Subtitle) -> AdjustmentReport:
    """
    根据参考字幕对齐时间轴

    通过匹配字幕文本或时间顺序找到对应点，计算线性映射进行对齐

    Args:
        subtitle: 待校正字幕
        reference: 参考字幕（正确时间轴）

    Returns:
        校正报告
    """
    if not reference.cues or not subtitle.cues:
        return AdjustmentReport(
            format=subtitle.format,
            original_cue_count=len(subtitle.cues),
            adjusted_cue_count=0,
            adjustments=[],
            method='align_reference',
            method_params={}
        )

    src_starts: List[float] = []
    dst_starts: List[float] = []

    src_text_map = {}
    for cue in subtitle.cues:
        text = cue.text.strip().lower()
        if text:
            src_text_map[text] = cue.start

    for ref_cue in reference.cues:
        text = ref_cue.text.strip().lower()
        if text and text in src_text_map:
            src_starts.append(src_text_map[text])
            dst_starts.append(ref_cue.start)

    if len(src_starts) < 2:
        n = min(len(subtitle.cues), len(reference.cues))
        if n >= 2:
            src_starts = [subtitle.cues[i].start for i in range(0, n, max(1, n // 5))]
            dst_starts = [reference.cues[i].start for i in range(0, n, max(1, n // 5))]
            if len(src_starts) < 2 and n >= 2:
                src_starts = [subtitle.cues[0].start, subtitle.cues[-1].start]
                dst_starts = [reference.cues[0].start, reference.cues[-1].start]

    if len(src_starts) < 2:
        if reference.cues and subtitle.cues:
            offset = reference.cues[0].start - subtitle.cues[0].start
            return apply_offset(subtitle, offset)
        return AdjustmentReport(
            format=subtitle.format,
            original_cue_count=len(subtitle.cues),
            adjusted_cue_count=0,
            adjustments=[],
            method='align_reference',
            method_params={}
        )

    scale, offset = _find_linear_mapping(src_starts, dst_starts)

    adjustments: List[CueAdjustment] = []
    original_cues = [cue.clone() for cue in subtitle.cues]

    for original, cue in zip(original_cues, subtitle.cues):
        cue.start = cue.start * scale + offset
        cue.end = cue.end * scale + offset
        if cue.start < 0:
            cue.start = 0.0
        if cue.end < cue.start:
            cue.end = cue.start
        _record_adjustment(original, cue, adjustments)

    subtitle.sort_cues()

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='align_reference',
        method_params={
            'matched_points': len(src_starts),
            'scale': scale,
            'offset': offset,
        }
    )
