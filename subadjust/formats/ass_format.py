"""
ASS/SSA 格式解析器和写入器
"""

import re
from typing import List, Tuple, Dict
from ..models import Cue, Subtitle
from ..timing import parse_ass_time, format_ass_time


ASS_DIALOGUE_RE = re.compile(
    r'^Dialogue:\s*(.*)$',
    re.IGNORECASE | re.MULTILINE
)

FORMAT_LINE_RE = re.compile(
    r'^Format:\s*(.*)$',
    re.IGNORECASE | re.MULTILINE
)


def _parse_ass_fields(format_line: str) -> List[str]:
    """解析 Format 行的字段列表"""
    if not format_line:
        return ['Layer', 'Start', 'End', 'Style', 'Name', 'MarginL', 'MarginR', 'MarginV', 'Effect', 'Text']
    fields = [f.strip() for f in format_line.split(',')]
    return fields


def _split_dialogue(text: str, field_count: int) -> List[str]:
    """按逗号分割对话行，最后一个字段（Text）不分割"""
    parts = []
    current = []
    in_brace = 0
    idx = 0
    for char in text:
        if char == '{' and idx < field_count - 1:
            in_brace += 1
        elif char == '}' and in_brace > 0:
            in_brace -= 1
        elif char == ',' and in_brace == 0 and idx < field_count - 1:
            parts.append(''.join(current).strip())
            current = []
            idx += 1
            continue
        current.append(char)
    parts.append(''.join(current).strip())
    while len(parts) < field_count:
        parts.append('')
    return parts


def parse_ass(content: str) -> Subtitle:
    """解析 ASS/SSA 格式字幕"""
    content = content.lstrip('\ufeff')
    lines = content.splitlines()
    cues: List[Cue] = []
    header_lines: List[str] = []
    footer_lines: List[str] = []
    in_events = False
    format_fields: List[str] = []
    event_lines: List[str] = []
    metadata: Dict[str, str] = {}
    current_section = ''

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped[1:-1].lower()
            if current_section == 'events':
                in_events = True
            elif in_events:
                in_events = False
            header_lines.append(line)
            continue
        if in_events:
            if re.match(r'^Format:\s*', stripped, re.IGNORECASE):
                format_match = FORMAT_LINE_RE.match(line)
                if format_match:
                    format_fields = _parse_ass_fields(format_match.group(1))
                header_lines.append(line)
            elif re.match(r'^Dialogue:\s*', stripped, re.IGNORECASE):
                event_lines.append(line)
            else:
                header_lines.append(line)
        else:
            header_lines.append(line)
            if '=' in stripped and not stripped.startswith(';'):
                key, _, val = stripped.partition('=')
                metadata[key.strip()] = val.strip()

    start_idx = format_fields.index('Start') if 'Start' in format_fields else 1
    end_idx = format_fields.index('End') if 'End' in format_fields else 2
    style_idx = format_fields.index('Style') if 'Style' in format_fields else 3
    text_idx = format_fields.index('Text') if 'Text' in format_fields else len(format_fields) - 1

    for cue_num, event_line in enumerate(event_lines, 1):
        dialogue_match = ASS_DIALOGUE_RE.match(event_line)
        if not dialogue_match:
            continue
        dialogue_content = dialogue_match.group(1)
        fields = _split_dialogue(dialogue_content, len(format_fields))
        try:
            start = parse_ass_time(fields[start_idx])
            end = parse_ass_time(fields[end_idx])
        except (ValueError, IndexError):
            continue
        if end < start:
            end = start
        style = fields[style_idx] if style_idx < len(fields) else None
        text = fields[text_idx] if text_idx < len(fields) else ''
        extra = {}
        for i, field_name in enumerate(format_fields):
            if field_name not in ('Start', 'End', 'Style', 'Text') and i < len(fields):
                extra[field_name] = fields[i]
        cues.append(Cue(
            index=cue_num,
            start=start,
            end=end,
            text=text,
            style=style,
            extra=extra
        ))

    return Subtitle(
        format='ass',
        cues=cues,
        header='\n'.join(header_lines) + '\n',
        footer='',
        metadata={**metadata, '_format_fields': format_fields}
    )


def write_ass(subtitle: Subtitle) -> str:
    """将字幕对象写入 ASS 格式字符串"""
    lines: List[str] = []
    header = subtitle.header.rstrip('\n')
    if header:
        lines.append(header)

    format_fields = subtitle.metadata.get('_format_fields') or [
        'Layer', 'Start', 'End', 'Style', 'Name', 'MarginL',
        'MarginR', 'MarginV', 'Effect', 'Text'
    ]

    default_values = {
        'Layer': '0',
        'Start': '0:00:00.00',
        'End': '0:00:00.00',
        'Style': 'Default',
        'Name': '',
        'MarginL': '0000',
        'MarginR': '0000',
        'MarginV': '0000',
        'Effect': '',
        'Text': '',
    }

    for cue in subtitle.cues:
        extra = dict(cue.extra)
        field_values = {}
        for fname in format_fields:
            if fname == 'Start':
                field_values[fname] = format_ass_time(cue.start)
            elif fname == 'End':
                field_values[fname] = format_ass_time(cue.end)
            elif fname == 'Style':
                field_values[fname] = cue.style or extra.get('Style', default_values['Style'])
            elif fname == 'Text':
                field_values[fname] = cue.text
            else:
                field_values[fname] = extra.get(fname, default_values.get(fname, ''))

        ordered_values = [field_values.get(fname, default_values.get(fname, ''))
                          for fname in format_fields]
        dialogue = 'Dialogue: ' + ','.join(ordered_values)
        lines.append(dialogue)

    if subtitle.footer:
        lines.append(subtitle.footer)

    return '\n'.join(lines) + '\n'
