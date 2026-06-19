"""
字幕格式解析和写入模块
"""

from .registry import (
    PARSERS,
    WRITERS,
    EXTENSIONS,
    detect_format,
    get_parser,
    get_writer,
    load_subtitle,
    save_subtitle,
)
from .srt_format import parse_srt, write_srt
from .ass_format import parse_ass, write_ass
from .vtt_format import parse_vtt, write_vtt

__all__ = [
    'PARSERS',
    'WRITERS',
    'EXTENSIONS',
    'detect_format',
    'get_parser',
    'get_writer',
    'load_subtitle',
    'save_subtitle',
    'parse_srt',
    'write_srt',
    'parse_ass',
    'write_ass',
    'parse_vtt',
    'write_vtt',
]
