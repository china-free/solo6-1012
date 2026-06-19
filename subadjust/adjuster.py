"""
核心校正算法
支持：整体偏移、分段校正、倍速校正、参考字幕对齐（可插拔对齐算法）
"""

from typing import List, Optional, Tuple, Union
from .models import Subtitle, Cue
from .report import AdjustmentReport, CueAdjustment
from .aligners import (
    BaseAligner, AlignerResult,
    get_aligner, list_aligners, ALIGNERS,
)


DEFAULT_ALIGNER = 'linear_scale'


def _apply_linear_mapping(subtitle: Subtitle, scale: float, offset: float) -> List[CueAdjustment]:
    """应用线性映射到所有字幕并返回调整记录"""
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
    return adjustments


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


def align_to_reference(subtitle: Subtitle, reference: Subtitle,
                       algorithm: Optional[Union[str, BaseAligner]] = None
                       ) -> AdjustmentReport:
    """
    根据参考字幕对齐时间轴（可插拔算法）

    Args:
        subtitle: 待校正字幕
        reference: 参考字幕（正确时间轴）
        algorithm: 对齐算法，可选字符串名称或 BaseAligner 实例
                   可用: 'linear_scale'（默认）、'text_similarity'、'time_series'

    Returns:
        校正报告
    """
    if algorithm is None:
        algorithm = DEFAULT_ALIGNER
    if isinstance(algorithm, str):
        aligner = get_aligner(algorithm)
    elif isinstance(algorithm, BaseAligner):
        aligner = algorithm
    else:
        raise ValueError(f'algorithm 必须是字符串或 BaseAligner 实例，实际: {type(algorithm)}')

    if not reference.cues or not subtitle.cues:
        return AdjustmentReport(
            format=subtitle.format,
            original_cue_count=len(subtitle.cues),
            adjusted_cue_count=0,
            adjustments=[],
            method='align_reference',
            method_params={'algorithm': aligner.name}
        )

    result = aligner.compute(subtitle, reference)
    adjustments = _apply_linear_mapping(subtitle, result.scale, result.offset)

    params = {
        'algorithm': aligner.name,
        'scale': result.scale,
        'offset': result.offset,
        **result.params,
    }
    if result.matched_points:
        params['matched_points_count'] = len(result.matched_points)
        if len(result.matched_points) <= 10:
            params['matched_points'] = [
                {'src': s, 'ref': r} for s, r in result.matched_points
            ]

    return AdjustmentReport(
        format=subtitle.format,
        original_cue_count=len(subtitle.cues),
        adjusted_cue_count=len(adjustments),
        adjustments=adjustments,
        method='align_reference',
        method_params=params
    )
