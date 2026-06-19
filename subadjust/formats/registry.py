"""
字幕格式工厂 - 自动识别和统一接口
"""

import os
from typing import Callable, Dict, Optional
from ..models import Subtitle
from ..encoding import read_file, write_file
from .srt_format import parse_srt, write_srt
from .ass_format import parse_ass, write_ass
from .vtt_format import parse_vtt, write_vtt


Parser = Callable[[str], Subtitle]
Writer = Callable[[Subtitle], str]


PARSERS: Dict[str, Parser] = {
    'srt': parse_srt,
    'ass': parse_ass,
    'ssa': parse_ass,
    'vtt': parse_vtt,
    'webvtt': parse_vtt,
}

WRITERS: Dict[str, Writer] = {
    'srt': write_srt,
    'ass': write_ass,
    'ssa': write_ass,
    'vtt': write_vtt,
    'webvtt': write_vtt,
}

EXTENSIONS: Dict[str, str] = {
    '.srt': 'srt',
    '.ass': 'ass',
    '.ssa': 'ass',
    '.vtt': 'vtt',
}


def detect_format(filepath: str, content: Optional[str] = None) -> str:
    """根据文件扩展名或内容检测字幕格式"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in EXTENSIONS:
        return EXTENSIONS[ext]
    if content is None:
        try:
            content, _ = read_file(filepath)
        except Exception:
            pass
    if content is not None:
        content_stripped = content.lstrip('\ufeff').lstrip()
        if content_stripped.startswith('WEBVTT'):
            return 'vtt'
        if '[Script Info]' in content_stripped or 'Dialogue:' in content_stripped:
            return 'ass'
        if '-->' in content_stripped:
            return 'srt'
    raise ValueError(f'无法识别字幕格式: {filepath}')


def get_parser(fmt: str) -> Parser:
    """获取指定格式的解析器"""
    fmt = fmt.lower()
    if fmt not in PARSERS:
        raise ValueError(f'不支持的字幕格式: {fmt}')
    return PARSERS[fmt]


def get_writer(fmt: str) -> Writer:
    """获取指定格式的写入器"""
    fmt = fmt.lower()
    if fmt not in WRITERS:
        raise ValueError(f'不支持的字幕格式: {fmt}')
    return WRITERS[fmt]


def load_subtitle(filepath: str, fmt: Optional[str] = None) -> Subtitle:
    """加载字幕文件"""
    content, encoding = read_file(filepath)
    if fmt is None:
        fmt = detect_format(filepath, content)
    parser = get_parser(fmt)
    subtitle = parser(content)
    subtitle.encoding = encoding
    return subtitle


def save_subtitle(subtitle: Subtitle, filepath: str, fmt: Optional[str] = None,
                  encoding: Optional[str] = None) -> None:
    """保存字幕到文件"""
    if fmt is None:
        fmt = detect_format(filepath)
    writer = get_writer(fmt)
    content = writer(subtitle)
    if encoding is None:
        encoding = subtitle.encoding or 'utf-8'
    write_file(filepath, content, encoding)
