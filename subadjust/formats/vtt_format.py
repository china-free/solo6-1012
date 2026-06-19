"""
VTT (WebVTT) 格式解析器和写入器
"""

import re
from typing import List
from ..models import Cue, Subtitle
from ..timing import parse_vtt_time, format_vtt_time


VTT_TIME_RE = re.compile(
    r'(\d{1,2}:)?\d{2}:\d{2}[.,]\d{1,3}\s*-->\s*(\d{1,2}:)?\d{2}:\d{2}[.,]\d{1,3}'
)

VTT_CUE_ID_RE = re.compile(r'^[^\s\-][^\r\n]*$')


def parse_vtt(content: str) -> Subtitle:
    """解析 VTT 格式字幕"""
    content = content.lstrip('\ufeff')
    lines = content.splitlines()
    total = len(lines)
    cues: List[Cue] = []
    header_lines: List[str] = []
    i = 0

    if i < total and lines[i].strip().startswith('WEBVTT'):
        header_lines.append(lines[i])
        i += 1
        while i < total and lines[i].strip():
            header_lines.append(lines[i])
            i += 1

    cue_idx = 1
    while i < total:
        if not lines[i].strip():
            i += 1
            continue
        cue_id = None
        line = lines[i].strip()
        if not VTT_TIME_RE.search(line):
            if VTT_CUE_ID_RE.match(line):
                cue_id = line
                i += 1
            if i >= total:
                break
        if i >= total:
            break
        time_line = lines[i].strip()
        i += 1
        time_match = re.search(
            r'((?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{1,3})',
            time_line
        )
        if not time_match:
            continue
        try:
            start = parse_vtt_time(time_match.group(1))
            end = parse_vtt_time(time_match.group(2))
        except ValueError:
            continue
        text_lines: List[str] = []
        while i < total and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        if end < start:
            end = start
        cues.append(Cue(
            index=cue_idx,
            start=start,
            end=end,
            text='\n'.join(text_lines),
            extra={'cue_id': cue_id} if cue_id else {}
        ))
        cue_idx += 1

    return Subtitle(
        format='vtt',
        cues=cues,
        header='\n'.join(header_lines) + '\n' if header_lines else ''
    )


def write_vtt(subtitle: Subtitle) -> str:
    """将字幕对象写入 VTT 格式字符串"""
    parts: List[str] = []
    header = subtitle.header.rstrip('\n')
    if header and header.startswith('WEBVTT'):
        parts.append(header)
    else:
        parts.append('WEBVTT')
    parts.append('')

    for cue in subtitle.cues:
        cue_id = cue.extra.get('cue_id')
        if cue_id:
            parts.append(str(cue_id))
        start_str = format_vtt_time(cue.start)
        end_str = format_vtt_time(cue.end)
        parts.append(f'{start_str} --> {end_str}')
        parts.append(cue.text)
        parts.append('')

    return '\n'.join(parts)
