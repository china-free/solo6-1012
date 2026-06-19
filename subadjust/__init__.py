"""
SubAdjust - 字幕时间轴批量校正工具
支持 SRT、ASS、VTT 三种常见字幕格式
"""

__version__ = '1.0.0'

from .models import Cue, Subtitle
from .report import AdjustmentReport, CueAdjustment, format_batch_reports
from .adjuster import (
    apply_offset,
    apply_segmented_offsets,
    apply_speed,
    apply_linear_scale,
    align_to_reference,
)
from .formats import (
    load_subtitle,
    save_subtitle,
    detect_format,
    parse_srt,
    write_srt,
    parse_ass,
    write_ass,
    parse_vtt,
    write_vtt,
)
from .aligners import (
    BaseAligner,
    AlignerResult,
    get_aligner,
    list_aligners,
    register_aligner,
    ALIGNERS,
    LinearScaleAligner,
    TextSimilarityAligner,
    TimeSeriesAligner,
)

__all__ = [
    '__version__',
    'Cue',
    'Subtitle',
    'AdjustmentReport',
    'CueAdjustment',
    'format_batch_reports',
    'apply_offset',
    'apply_segmented_offsets',
    'apply_speed',
    'apply_linear_scale',
    'align_to_reference',
    'load_subtitle',
    'save_subtitle',
    'detect_format',
    'parse_srt',
    'write_srt',
    'parse_ass',
    'write_ass',
    'parse_vtt',
    'write_vtt',
    'BaseAligner',
    'AlignerResult',
    'get_aligner',
    'list_aligners',
    'register_aligner',
    'ALIGNERS',
    'LinearScaleAligner',
    'TextSimilarityAligner',
    'TimeSeriesAligner',
]
