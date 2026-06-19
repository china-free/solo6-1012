"""
校正报告数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class CueAdjustment:
    """单条字幕的调整记录"""
    index: int
    original_start: float
    original_end: float
    new_start: float
    new_end: float

    @property
    def start_offset(self) -> float:
        return self.new_start - self.original_start

    @property
    def end_offset(self) -> float:
        return self.new_end - self.original_end

    @property
    def max_offset(self) -> float:
        return max(abs(self.start_offset), abs(self.end_offset))


@dataclass
class AdjustmentReport:
    """校正报告"""
    source_file: str = ''
    output_file: str = ''
    format: str = ''
    original_cue_count: int = 0
    adjusted_cue_count: int = 0
    adjustments: List[CueAdjustment] = field(default_factory=list)
    method: str = ''
    method_params: Dict[str, Any] = field(default_factory=dict)

    @property
    def unchanged_count(self) -> int:
        return self.original_cue_count - self.adjusted_cue_count

    @property
    def max_start_offset(self) -> float:
        if not self.adjustments:
            return 0.0
        return max((abs(a.start_offset) for a in self.adjustments), default=0.0)

    @property
    def max_end_offset(self) -> float:
        if not self.adjustments:
            return 0.0
        return max((abs(a.end_offset) for a in self.adjustments), default=0.0)

    @property
    def max_offset(self) -> float:
        return max(self.max_start_offset, self.max_end_offset)

    @property
    def avg_start_offset(self) -> float:
        if not self.adjustments:
            return 0.0
        return sum(abs(a.start_offset) for a in self.adjustments) / len(self.adjustments)

    @property
    def avg_end_offset(self) -> float:
        if not self.adjustments:
            return 0.0
        return sum(abs(a.end_offset) for a in self.adjustments) / len(self.adjustments)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_file': self.source_file,
            'output_file': self.output_file,
            'format': self.format,
            'original_cue_count': self.original_cue_count,
            'adjusted_cue_count': self.adjusted_cue_count,
            'unchanged_count': self.unchanged_count,
            'max_start_offset': self.max_start_offset,
            'max_end_offset': self.max_end_offset,
            'max_offset': self.max_offset,
            'avg_start_offset': self.avg_start_offset,
            'avg_end_offset': self.avg_end_offset,
            'method': self.method,
            'method_params': self.method_params,
        }

    def format_text(self, detailed: bool = False) -> str:
        """格式化为可读文本报告"""
        lines = []
        lines.append('=' * 60)
        lines.append('  字幕时间轴校正报告')
        lines.append('=' * 60)
        if self.source_file:
            lines.append(f'源文件:       {self.source_file}')
        if self.output_file:
            lines.append(f'输出文件:     {self.output_file}')
        lines.append(f'字幕格式:     {self.format.upper()}')
        method_names = {
            'offset': '整体偏移',
            'segmented': '分段偏移',
            'speed': '帧率转换',
            'linear_scale': '线性缩放',
            'align_reference': '参考对齐',
        }
        lines.append(f'校正方式:     {method_names.get(self.method, self.method)}')
        lines.append('-' * 60)
        lines.append(f'字幕总数:     {self.original_cue_count}')
        lines.append(f'已调整:       {self.adjusted_cue_count}')
        lines.append(f'未变化:       {self.unchanged_count}')
        lines.append('-' * 60)
        lines.append(f'最大起始偏移: {self.max_start_offset:.3f} 秒')
        lines.append(f'最大结束偏移: {self.max_end_offset:.3f} 秒')
        lines.append(f'最大偏移量:   {self.max_offset:.3f} 秒')
        lines.append(f'平均起始偏移: {self.avg_start_offset:.3f} 秒')
        lines.append(f'平均结束偏移: {self.avg_end_offset:.3f} 秒')
        if self.method_params:
            lines.append('-' * 60)
            lines.append('校正参数:')
            for key, value in self.method_params.items():
                lines.append(f'  {key}: {value}')
        if detailed and self.adjustments:
            lines.append('-' * 60)
            lines.append('详细调整记录:')
            lines.append(f'  {"序号":>6}  {"原起始":>12}  {"新起始":>12}  {"偏移":>10}')
            for adj in self.adjustments[:50]:
                lines.append(
                    f'  {adj.index:>6}  {adj.original_start:>10.3f}s  '
                    f'{adj.new_start:>10.3f}s  {adj.start_offset:>+9.3f}s'
                )
            if len(self.adjustments) > 50:
                lines.append(f'  ... (共 {len(self.adjustments)} 条，仅显示前 50 条)')
        lines.append('=' * 60)
        return '\n'.join(lines)

    def format_json(self, indent: int = 2) -> str:
        """格式化为 JSON 报告"""
        import json
        data = self.to_dict()
        if self.adjustments:
            data['adjustments'] = [
                {
                    'index': a.index,
                    'original_start': a.original_start,
                    'original_end': a.original_end,
                    'new_start': a.new_start,
                    'new_end': a.new_end,
                    'start_offset': a.start_offset,
                    'end_offset': a.end_offset,
                }
                for a in self.adjustments
            ]
        return json.dumps(data, ensure_ascii=False, indent=indent)

    def format_csv(self) -> str:
        """格式化为 CSV 报告（逐条调整记录）"""
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'index', 'original_start', 'original_end',
            'new_start', 'new_end', 'start_offset', 'end_offset'
        ])
        for adj in self.adjustments:
            writer.writerow([
                adj.index,
                f'{adj.original_start:.6f}',
                f'{adj.original_end:.6f}',
                f'{adj.new_start:.6f}',
                f'{adj.new_end:.6f}',
                f'{adj.start_offset:.6f}',
                f'{adj.end_offset:.6f}',
            ])
        return output.getvalue()


def format_batch_reports(reports: List['AdjustmentReport'],
                         detailed: bool = False) -> str:
    """格式化批量处理报告"""
    lines = []
    lines.append('=' * 60)
    lines.append('  批量字幕校正报告')
    lines.append('=' * 60)
    lines.append(f'处理文件数: {len(reports)}')
    total_cues = sum(r.original_cue_count for r in reports)
    total_adjusted = sum(r.adjusted_cue_count for r in reports)
    lines.append(f'字幕总数:   {total_cues}')
    lines.append(f'调整总数:   {total_adjusted}')
    lines.append('-' * 60)
    for i, report in enumerate(reports, 1):
        lines.append(f'[{i}] {report.source_file}')
        lines.append(f'    格式: {report.format.upper()} | '
                     f'调整: {report.adjusted_cue_count}/{report.original_cue_count} | '
                     f'最大偏移: {report.max_offset:.3f}s')
    lines.append('=' * 60)
    if detailed:
        for report in reports:
            lines.append('')
            lines.append(report.format_text(detailed=False))
    return '\n'.join(lines)

