"""
时间轴工具函数
"""

import re
from typing import Tuple


def time_to_seconds(hours: int, minutes: int, seconds: int, milliseconds: int = 0) -> float:
    """将时分秒毫秒转换为秒数"""
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def seconds_to_time(seconds: float) -> Tuple[int, int, int, int]:
    """将秒数转换为 (时, 分, 秒, 毫秒)"""
    if seconds < 0:
        sign = -1
        seconds = abs(seconds)
    else:
        sign = 1
    hours = int(seconds // 3600)
    remaining = seconds - hours * 3600
    minutes = int(remaining // 60)
    remaining -= minutes * 60
    secs = int(remaining // 1)
    milliseconds = int(round((remaining - secs) * 1000))
    if milliseconds == 1000:
        secs += 1
        milliseconds = 0
    if secs == 60:
        minutes += 1
        secs = 0
    if minutes == 60:
        hours += 1
        minutes = 0
    return (sign * hours, minutes, secs, milliseconds)


def format_srt_time(seconds: float) -> str:
    """格式化为 SRT 时间字符串 HH:MM:SS,mmm"""
    hours, minutes, secs, milliseconds = seconds_to_time(seconds)
    abs_hours = abs(hours)
    sign = '-' if hours < 0 else ''
    return f'{sign}{abs_hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}'


def format_ass_time(seconds: float) -> str:
    """格式化为 ASS 时间字符串 H:MM:SS.cc"""
    hours, minutes, secs, milliseconds = seconds_to_time(seconds)
    abs_hours = abs(hours)
    sign = '-' if hours < 0 else ''
    centiseconds = int(round(milliseconds / 10))
    if centiseconds == 100:
        secs += 1
        centiseconds = 0
    return f'{sign}{abs_hours:d}:{minutes:02d}:{secs:02d}.{centiseconds:02d}'


def format_vtt_time(seconds: float) -> str:
    """格式化为 VTT 时间字符串 HH:MM:SS.mmm"""
    hours, minutes, secs, milliseconds = seconds_to_time(seconds)
    abs_hours = abs(hours)
    sign = '-' if hours < 0 else ''
    return f'{sign}{abs_hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}'


SRT_TIME_RE = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})'
)

ASS_TIME_RE = re.compile(
    r'(\d+):(\d{2}):(\d{2})[.](\d{1,2})'
)

VTT_TIME_RE = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})|(\d{2}):(\d{2})[.,](\d{1,3})'
)


def parse_srt_time(time_str: str) -> float:
    """解析 SRT 时间字符串"""
    match = SRT_TIME_RE.search(time_str.strip())
    if not match:
        raise ValueError(f'无法解析 SRT 时间: {time_str}')
    hours, minutes, seconds, milliseconds = match.groups()
    ms = int(milliseconds.ljust(3, '0'))
    return time_to_seconds(int(hours), int(minutes), int(seconds), ms)


def parse_ass_time(time_str: str) -> float:
    """解析 ASS 时间字符串"""
    match = ASS_TIME_RE.search(time_str.strip())
    if not match:
        raise ValueError(f'无法解析 ASS 时间: {time_str}')
    hours, minutes, seconds, centiseconds = match.groups()
    ms = int(centiseconds.ljust(3, '0'))
    return time_to_seconds(int(hours), int(minutes), int(seconds), ms)


def parse_vtt_time(time_str: str) -> float:
    """解析 VTT 时间字符串"""
    match = VTT_TIME_RE.search(time_str.strip())
    if not match:
        raise ValueError(f'无法解析 VTT 时间: {time_str}')
    groups = match.groups()
    if groups[0] is not None:
        hours, minutes, seconds, milliseconds = groups[0], groups[1], groups[2], groups[3]
    else:
        hours = '0'
        minutes, seconds, milliseconds = groups[4], groups[5], groups[6]
    ms = int(milliseconds.ljust(3, '0'))
    return time_to_seconds(int(hours), int(minutes), int(seconds), ms)
