"""
命令行接口 (CLI)
"""

import argparse
import os
import sys
from typing import List, Optional, Tuple

from . import __version__
from .models import Subtitle
from .formats import load_subtitle, save_subtitle, detect_format, EXTENSIONS
from .adjuster import (
    apply_offset,
    apply_segmented_offsets,
    apply_speed,
    apply_linear_scale,
    align_to_reference,
)
from .report import AdjustmentReport, format_batch_reports


def _parse_time(time_str: str) -> float:
    """解析时间字符串，支持秒数或 HH:MM:SS 或 HH:MM:SS.mmm 格式"""
    import re
    time_str = time_str.strip()
    try:
        return float(time_str)
    except ValueError:
        pass
    hms_match = re.match(r'^(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,3}))?$', time_str)
    if hms_match:
        hours = int(hms_match.group(1))
        minutes = int(hms_match.group(2))
        seconds = int(hms_match.group(3))
        ms_str = hms_match.group(4) or '0'
        milliseconds = int(ms_str.ljust(3, '0'))
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
    ms_match = re.match(r'^(\d{2}):(\d{2})(?:[.,](\d{1,3}))?$', time_str)
    if ms_match:
        minutes = int(ms_match.group(1))
        seconds = int(ms_match.group(2))
        ms_str = ms_match.group(3) or '0'
        milliseconds = int(ms_str.ljust(3, '0'))
        return minutes * 60 + seconds + milliseconds / 1000.0
    from .timing import parse_srt_time, parse_vtt_time, parse_ass_time
    for parser in (parse_srt_time, parse_vtt_time, parse_ass_time):
        try:
            return parser(time_str)
        except ValueError:
            continue
    raise ValueError(f'无法解析时间: {time_str}，支持秒数或 HH:MM:SS 或 HH:MM:SS.mmm 格式')


def _parse_segment(seg_str: str) -> Tuple[float, float]:
    """解析分段参数，格式为 "时间点=偏移秒数" 或 "时间点:偏移秒数"（从右往左分割一次）"""
    if '=' in seg_str:
        parts = seg_str.split('=', 1)
    else:
        parts = seg_str.rsplit(':', 1)
    if len(parts) != 2:
        raise ValueError(f'分段参数格式错误: {seg_str}，应为 "时间点=偏移秒数"')
    return _parse_time(parts[0]), float(parts[1])


def _collect_files(paths: List[str], recursive: bool = False) -> List[str]:
    """收集字幕文件路径"""
    files = []
    for path in paths:
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in EXTENSIONS:
                files.append(os.path.abspath(path))
        elif os.path.isdir(path):
            if recursive:
                for root, _, filenames in os.walk(path):
                    for fn in filenames:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in EXTENSIONS:
                            files.append(os.path.abspath(os.path.join(root, fn)))
            else:
                for fn in os.listdir(path):
                    full = os.path.join(path, fn)
                    if os.path.isfile(full):
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in EXTENSIONS:
                            files.append(os.path.abspath(full))
        else:
            print(f'警告: 路径不存在或无法访问: {path}', file=sys.stderr)
    return sorted(set(files))


def _get_output_path(input_path: str, output: Optional[str],
                     suffix: str) -> str:
    """计算输出文件路径"""
    if output:
        if os.path.isdir(output):
            basename = os.path.basename(input_path)
            return os.path.join(output, basename)
        return output
    base, ext = os.path.splitext(input_path)
    return f'{base}{suffix}{ext}'


def _process_file(input_path: str, args: argparse.Namespace) -> Optional[AdjustmentReport]:
    """处理单个字幕文件"""
    try:
        subtitle = load_subtitle(input_path)
    except Exception as e:
        print(f'错误: 无法加载 {input_path}: {e}', file=sys.stderr)
        return None

    report: Optional[AdjustmentReport] = None

    if args.command == 'offset':
        start_from = _parse_time(args.start_from) if args.start_from else None
        report = apply_offset(subtitle, args.offset, start_from)

    elif args.command == 'segment':
        segments = [_parse_segment(s) for s in args.segments]
        report = apply_segmented_offsets(subtitle, segments)

    elif args.command == 'speed':
        anchor = _parse_time(args.anchor) if args.anchor else 0.0
        report = apply_speed(subtitle, args.source_fps, args.target_fps, anchor)

    elif args.command == 'scale':
        anchor = _parse_time(args.anchor) if args.anchor else 0.0
        report = apply_linear_scale(subtitle, args.scale, anchor)

    elif args.command == 'align':
        try:
            reference = load_subtitle(args.reference)
        except Exception as e:
            print(f'错误: 无法加载参考字幕 {args.reference}: {e}', file=sys.stderr)
            return None
        report = align_to_reference(subtitle, reference)

    if report is None:
        return None

    report.source_file = input_path
    output_path = _get_output_path(input_path, args.output, args.suffix)
    report.output_file = output_path

    try:
        save_subtitle(subtitle, output_path)
    except Exception as e:
        print(f'错误: 无法写入 {output_path}: {e}', file=sys.stderr)
        return None

    return report


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='subadjust',
        description='字幕时间轴批量校正工具 - 支持 SRT/ASS/VTT 格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用示例:
  # 整体延后 2.5 秒
  subadjust offset -t 2.5 subtitle.srt

  # 从 10 分钟开始延后 3 秒
  subadjust offset -t 3 --start-from 00:10:00 subtitle.srt

  # 分段校正：0秒后+1秒，5分钟后+3秒
  subadjust segment -s "0=1" -s "00:05:00=3" subtitle.srt

  # 23.976fps 转 25fps
  subadjust speed --source-fps 23.976 --target-fps 25 subtitle.ass

  # 根据参考字幕对齐
  subadjust align -r correct_en.srt chinese.srt

  # 批量处理目录
  subadjust offset -t 1.5 -o ./output -R ./subtitles
        """
    )

    parser.add_argument('--version', action='version',
                        version=f'subadjust {__version__}')

    subparsers = parser.add_subparsers(dest='command', required=True,
                                       help='校正方式')

    offset_parser = subparsers.add_parser('offset', help='整体偏移校正')
    offset_parser.add_argument('-t', '--offset', type=float, required=True,
                               help='偏移秒数，正数延后，负数提前')
    offset_parser.add_argument('--start-from', type=str, default=None,
                               help='仅对该时间点之后的字幕应用偏移（秒数或 HH:MM:SS.mmm）')

    segment_parser = subparsers.add_parser('segment', help='分段偏移校正')
    segment_parser.add_argument('-s', '--segment', dest='segments',
                                action='append', required=True,
                                help='分段参数 "时间点=偏移秒数"，可指定多次')

    speed_parser = subparsers.add_parser('speed', help='帧率转换校正')
    speed_parser.add_argument('--source-fps', type=float, required=True,
                              help='原始帧率，如 23.976')
    speed_parser.add_argument('--target-fps', type=float, required=True,
                              help='目标帧率，如 25.0')
    speed_parser.add_argument('--anchor', type=str, default=None,
                              help='锚点时间（秒），该点时间不变，默认 0')

    scale_parser = subparsers.add_parser('scale', help='线性缩放校正')
    scale_parser.add_argument('--scale', type=float, required=True,
                              help='缩放系数，>1 拉长，<1 压缩')
    scale_parser.add_argument('--anchor', type=str, default=None,
                              help='锚点时间（秒），该点时间不变，默认 0')

    align_parser = subparsers.add_parser('align', help='根据参考字幕对齐')
    align_parser.add_argument('-r', '--reference', type=str, required=True,
                              help='参考字幕文件（正确时间轴）')

    for sub in (offset_parser, segment_parser, speed_parser,
                scale_parser, align_parser):
        sub.add_argument('inputs', nargs='+',
                         help='输入字幕文件或目录')
        sub.add_argument('-o', '--output', type=str, default=None,
                         help='输出文件或目录（不指定则添加后缀）')
        sub.add_argument('--suffix', type=str, default='.adjusted',
                         help='输出文件名后缀，默认 .adjusted')
        sub.add_argument('-R', '--recursive', action='store_true',
                         help='递归处理子目录')
        sub.add_argument('--in-place', action='store_true',
                         help='原地修改（覆盖原文件）')
        sub.add_argument('--report', choices=['text', 'json', 'csv', 'none'],
                         default='text', help='报告格式，默认 text')
        sub.add_argument('--report-file', type=str, default=None,
                         help='报告输出文件，不指定则输出到标准输出')
        sub.add_argument('--detailed', action='store_true',
                         help='显示详细的逐条调整记录')
        sub.add_argument('-q', '--quiet', action='store_true',
                         help='静默模式，不输出进度信息')

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """主入口函数"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, 'in_place', False):
        args.suffix = ''

    files = _collect_files(args.inputs, getattr(args, 'recursive', False))

    if not files:
        print('错误: 未找到任何字幕文件', file=sys.stderr)
        return 1

    if not args.quiet:
        print(f'找到 {len(files)} 个字幕文件')

    reports: List[AdjustmentReport] = []
    for i, f in enumerate(files, 1):
        if not args.quiet:
            print(f'[{i}/{len(files)}] 处理: {f}')
        report = _process_file(f, args)
        if report:
            reports.append(report)
            if not args.quiet:
                print(f'    完成: 调整 {report.adjusted_cue_count}/{report.original_cue_count} '
                      f'条，最大偏移 {report.max_offset:.3f}s -> {report.output_file}')
        else:
            if not args.quiet:
                print(f'    失败')

    if not reports:
        print('错误: 所有文件处理失败', file=sys.stderr)
        return 2

    report_text = ''
    report_format = args.report

    if report_format == 'text':
        if len(reports) == 1:
            report_text = reports[0].format_text(detailed=args.detailed)
        else:
            report_text = format_batch_reports(reports, detailed=args.detailed)
    elif report_format == 'json':
        import json
        if len(reports) == 1:
            report_text = reports[0].format_json()
        else:
            report_text = json.dumps(
                [r.to_dict() for r in reports],
                ensure_ascii=False, indent=2
            )
    elif report_format == 'csv':
        parts = []
        for r in reports:
            csv_content = r.format_csv()
            if len(reports) > 1:
                parts.append(f'# {r.source_file}')
            parts.append(csv_content)
        report_text = '\n'.join(parts)

    if report_text:
        if args.report_file:
            try:
                with open(args.report_file, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                if not args.quiet:
                    print(f'报告已写入: {args.report_file}')
            except Exception as e:
                print(f'错误: 无法写入报告文件: {e}', file=sys.stderr)
                print(report_text)
        else:
            if not args.quiet and len(reports) > 0:
                print()
            print(report_text)

    failed = len(files) - len(reports)
    if failed > 0:
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
