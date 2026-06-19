"""
SRT 格式解析器和写入器
"""

import re
from typing import List
from ..models import Cue, Subtitle
from ..timing import parse_srt_time, format_srt_time


def parse_srt(content: str) -> Subtitle:
    """解析 SRT 格式字幕"""
    cues: List[Cue] = []
    content = content.lstrip('\ufeff')
    lines = content.splitlines()
    total = len(lines)
    i = 0
    cue_idx = 1

    while i < total:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.isdigit():
            current_idx = int(line)
            i += 1
        else:
            current_idx = cue_idx
        if i >= total:
            break
        time_line = lines[i].strip()
        i += 1
        time_match = re.search(
            r'(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})',
            time_line
        )
        if not time_match:
            continue
        try:
            start = parse_srt_time(time_match.group(1))
            end = parse_srt_time(time_match.group(2))
        except ValueError:
            continue
        text_lines: List[str] = []
        while i < total and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        if end < start:
            end = start
        cues.append(Cue(
            index=current_idx,
            start=start,
            end=end,
            text='\n'.join(text_lines)
        ))
        cue_idx = current_idx + 1

    return Subtitle(format='srt', cues=cues)


def write_srt(subtitle: Subtitle) -> str:
    """将字幕对象写入 SRT 格式字符串"""
    parts = []
    for cue in subtitle.cues:
        start_str = format_srt_time(cue.start)
        end_str = format_srt_time(cue.end)
        parts.append(str(cue.index))
        parts.append(f'{start_str} --> {end_str}')
        parts.append(cue.text)
        parts.append('')
    return '\n'.join(parts)
