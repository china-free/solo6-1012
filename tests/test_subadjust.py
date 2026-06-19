"""
测试用例 - 验证字幕时间轴校正工具的各项功能
"""

import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subadjust.timing import (
    time_to_seconds,
    seconds_to_time,
    format_srt_time,
    format_ass_time,
    format_vtt_time,
    parse_srt_time,
    parse_ass_time,
    parse_vtt_time,
)
from subadjust.formats import (
    parse_srt, write_srt,
    parse_ass, write_ass,
    parse_vtt, write_vtt,
    load_subtitle, save_subtitle,
    detect_format,
)
from subadjust.adjuster import (
    apply_offset,
    apply_segmented_offsets,
    apply_speed,
    apply_linear_scale,
    align_to_reference,
)
from subadjust.models import Cue, Subtitle
from subadjust.report import AdjustmentReport, format_batch_reports

TEST_SRT = """1
00:00:01,000 --> 00:00:03,000
第一条字幕

2
00:00:05,000 --> 00:00:07,500
第二条字幕

3
00:00:10,000 --> 00:00:12,000
第三条字幕
"""

TEST_ASS = """[Script Info]
Title: Test
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,First line
Dialogue: 0,0:00:05.00,0:00:07.50,Default,,0,0,0,,Second line
Dialogue: 0,0:00:10.00,0:00:12.00,Default,,0,0,0,,Third line
"""

TEST_VTT = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
First caption

2
00:00:05.000 --> 00:00:07.500
Second caption

3
00:00:10.000 --> 00:00:12.000
Third caption
"""


def test_timing():
    print('  测试时间轴工具函数...')
    assert abs(time_to_seconds(1, 30, 45, 500) - 5445.5) < 1e-6
    assert seconds_to_time(3661.5) == (1, 1, 1, 500)
    assert seconds_to_time(-3661.5) == (-1, 1, 1, 500)
    assert format_srt_time(3661.5) == '01:01:01,500'
    assert format_ass_time(3661.5) == '1:01:01.50'
    assert format_vtt_time(3661.5) == '01:01:01.500'
    assert abs(parse_srt_time('01:01:01,500') - 3661.5) < 1e-6
    assert abs(parse_ass_time('1:01:01.50') - 3661.5) < 1e-6
    assert abs(parse_vtt_time('01:01:01.500') - 3661.5) < 1e-6
    assert abs(parse_vtt_time('01:01.500') - 61.5) < 1e-6
    print('    ✓ 时间轴工具函数测试通过')


def test_srt_format():
    print('  测试 SRT 格式解析和写入...')
    sub = parse_srt(TEST_SRT)
    assert sub.cue_count == 3
    assert abs(sub.cues[0].start - 1.0) < 1e-6
    assert abs(sub.cues[0].end - 3.0) < 1e-6
    assert sub.cues[0].text == '第一条字幕'
    assert abs(sub.cues[1].start - 5.0) < 1e-6
    assert abs(sub.cues[2].start - 10.0) < 1e-6
    output = write_srt(sub)
    sub2 = parse_srt(output)
    assert sub2.cue_count == 3
    for a, b in zip(sub.cues, sub2.cues):
        assert abs(a.start - b.start) < 1e-3
        assert abs(a.end - b.end) < 1e-3
        assert a.text == b.text
    print('    ✓ SRT 格式测试通过')


def test_ass_format():
    print('  测试 ASS 格式解析和写入...')
    sub = parse_ass(TEST_ASS)
    assert sub.cue_count == 3
    assert abs(sub.cues[0].start - 1.0) < 1e-6
    assert abs(sub.cues[0].end - 3.0) < 1e-6
    assert sub.cues[0].text == 'First line'
    assert sub.cues[0].style == 'Default'
    output = write_ass(sub)
    sub2 = parse_ass(output)
    assert sub2.cue_count == 3
    for a, b in zip(sub.cues, sub2.cues):
        assert abs(a.start - b.start) < 1e-2
        assert abs(a.end - b.end) < 1e-2
    assert sub.metadata.get('_format_fields') == [
        'Layer', 'Start', 'End', 'Style', 'Name', 'MarginL',
        'MarginR', 'MarginV', 'Effect', 'Text'
    ]

    TEST_ASS_CUSTOM_ORDER = """[Script Info]
Title: Test Custom

[Events]
Format: Style, Name, Layer, Start, End, Text, Effect, MarginL, MarginR, MarginV
Dialogue: Default,Alice,0,0:00:01.00,0:00:03.00,Hello world,,0,0,0
Dialogue: Default,Bob,0,0:00:05.00,0:00:07.50,Hi there,,0,0,0
"""
    sub3 = parse_ass(TEST_ASS_CUSTOM_ORDER)
    assert sub3.cue_count == 2
    assert sub3.cues[0].style == 'Default'
    assert sub3.cues[0].extra.get('Name') == 'Alice'
    assert abs(sub3.cues[0].start - 1.0) < 1e-6
    assert abs(sub3.cues[0].end - 3.0) < 1e-6
    assert sub3.cues[0].text == 'Hello world'
    assert sub3.cues[1].extra.get('Name') == 'Bob'
    assert sub3.cues[1].text == 'Hi there'

    output3 = write_ass(sub3)
    assert 'Style, Name, Layer, Start, End, Text, Effect, MarginL, MarginR, MarginV' in output3
    lines_out = output3.splitlines()
    for line in lines_out:
        if line.startswith('Dialogue:'):
            parts = line[len('Dialogue: '):].split(',', 5)
            assert parts[0] == 'Default', f'第一个字段应为 Style，实际: {parts[0]}'
            assert parts[2] == '0', f'第三个字段应为 Layer，实际: {parts[2]}'
            break
    sub4 = parse_ass(output3)
    assert sub4.cue_count == 2
    assert sub4.cues[0].style == 'Default'
    assert sub4.cues[0].extra.get('Name') == 'Alice'
    assert abs(sub4.cues[0].start - 1.0) < 1e-2
    print('    ✓ ASS 格式测试通过')


def test_vtt_format():
    print('  测试 VTT 格式解析和写入...')
    sub = parse_vtt(TEST_VTT)
    assert sub.cue_count == 3
    assert abs(sub.cues[0].start - 1.0) < 1e-6
    assert abs(sub.cues[0].end - 3.0) < 1e-6
    assert sub.cues[0].text == 'First caption'
    output = write_vtt(sub)
    assert output.startswith('WEBVTT')
    sub2 = parse_vtt(output)
    assert sub2.cue_count == 3
    for a, b in zip(sub.cues, sub2.cues):
        assert abs(a.start - b.start) < 1e-3
        assert abs(a.end - b.end) < 1e-3
    print('    ✓ VTT 格式测试通过')


def test_offset_adjust():
    print('  测试整体偏移校正...')
    sub = parse_srt(TEST_SRT)
    report = apply_offset(sub, 2.5)
    assert report.adjusted_cue_count == 3
    assert abs(sub.cues[0].start - 3.5) < 1e-6
    assert abs(sub.cues[2].start - 12.5) < 1e-6
    assert abs(report.max_offset - 2.5) < 1e-6

    sub2 = parse_srt(TEST_SRT)
    report2 = apply_offset(sub2, -1.0, start_from=6.0)
    assert report2.adjusted_cue_count == 1
    assert abs(sub2.cues[0].start - 1.0) < 1e-6
    assert abs(sub2.cues[1].start - 5.0) < 1e-6
    assert abs(sub2.cues[2].start - 9.0) < 1e-6
    print('    ✓ 整体偏移校正测试通过')


def test_segmented_adjust():
    print('  测试分段偏移校正...')
    sub = parse_srt(TEST_SRT)
    report = apply_segmented_offsets(sub, [(0, 1.0), (6.0, 2.0)])
    assert report.adjusted_cue_count == 3
    assert abs(sub.cues[0].start - 2.0) < 1e-6
    assert abs(sub.cues[1].start - 6.0) < 1e-6
    assert abs(sub.cues[2].start - 13.0) < 1e-6

    sub2 = parse_srt(TEST_SRT)
    report2 = apply_segmented_offsets(sub2, [(0, 1.0), (6.0, 3.0)])
    assert report2.adjusted_cue_count == 3
    assert abs(sub2.cues[0].start - 2.0) < 1e-6
    assert abs(sub2.cues[1].start - 6.0) < 1e-6
    assert abs(sub2.cues[2].start - 14.0) < 1e-6
    print('    ✓ 分段偏移校正测试通过')


def test_speed_adjust():
    print('  测试帧率转换校正...')
    sub = parse_srt(TEST_SRT)
    report = apply_speed(sub, 23.976, 25.0)
    ratio = 23.976 / 25.0
    assert abs(sub.cues[0].start - 1.0 * ratio) < 1e-4
    assert abs(sub.cues[2].start - 10.0 * ratio) < 1e-4
    assert report.adjusted_cue_count == 3

    sub2 = parse_srt(TEST_SRT)
    report2 = apply_speed(sub2, 25.0, 23.976, anchor=5.0)
    assert abs(sub2.cues[1].start - 5.0) < 1e-4
    print('    ✓ 帧率转换校正测试通过')


def test_linear_scale():
    print('  测试线性缩放校正...')
    sub = parse_srt(TEST_SRT)
    report = apply_linear_scale(sub, 2.0)
    assert abs(sub.cues[0].start - 2.0) < 1e-6
    assert abs(sub.cues[2].start - 20.0) < 1e-6
    print('    ✓ 线性缩放校正测试通过')


def test_align_reference():
    print('  测试参考字幕对齐...')
    ref = parse_srt(TEST_SRT)
    target = parse_srt(TEST_SRT)
    apply_offset(target, 10.0)
    apply_linear_scale(target, 1.1)
    report = align_to_reference(target, ref)
    assert report.adjusted_cue_count == 3
    assert abs(target.cues[0].start - 1.0) < 0.5
    assert abs(target.cues[2].start - 10.0) < 0.5
    print('    ✓ 参考字幕对齐测试通过')


def test_report_output():
    print('  测试报告输出...')
    sub = parse_srt(TEST_SRT)
    report = apply_offset(sub, 2.5)
    report.source_file = 'test.srt'
    report.output_file = 'test.adjusted.srt'
    text = report.format_text()
    assert '字幕时间轴校正报告' in text
    assert 'test.srt' in text
    assert '调整:       3' in text

    json_str = report.format_json()
    assert '"adjusted_cue_count": 3' in json_str
    assert '"source_file": "test.srt"' in json_str

    csv_str = report.format_csv()
    assert 'index,original_start' in csv_str
    assert len(csv_str.splitlines()) == 4

    reports = [report, report]
    batch = format_batch_reports(reports)
    assert '批量字幕校正报告' in batch
    assert '处理文件数: 2' in batch
    print('    ✓ 报告输出测试通过')


def test_file_io():
    print('  测试文件读写...')
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = os.path.join(tmpdir, 'test.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(TEST_SRT)
        assert detect_format(srt_path) == 'srt'
        sub = load_subtitle(srt_path)
        assert sub.cue_count == 3
        assert sub.format == 'srt'

        apply_offset(sub, 1.5)
        out_path = os.path.join(tmpdir, 'out.srt')
        save_subtitle(sub, out_path)
        sub2 = load_subtitle(out_path)
        assert abs(sub2.cues[0].start - 2.5) < 1e-6
    print('    ✓ 文件读写测试通过')


def test_cli_module():
    print('  测试 CLI 模块导入和参数解析...')
    from subadjust.cli import build_parser, _parse_time, _parse_segment
    parser = build_parser()
    args = parser.parse_args(['offset', '-t', '2.5', 'test.srt'])
    assert args.command == 'offset'
    assert args.offset == 2.5
    assert args.inputs == ['test.srt']

    assert abs(_parse_time('120.5') - 120.5) < 1e-6
    assert abs(_parse_time('00:02:00.500') - 120.5) < 1e-6
    t, o = _parse_segment('00:01:00=2.5')
    assert abs(t - 60.0) < 1e-6
    assert abs(o - 2.5) < 1e-6
    t2, o2 = _parse_segment('60=2.5')
    assert abs(t2 - 60.0) < 1e-6
    assert abs(o2 - 2.5) < 1e-6
    print('    ✓ CLI 模块测试通过')


def run_all():
    print('\n' + '=' * 60)
    print('  SubAdjust 字幕时间轴校正工具 - 运行测试用例')
    print('=' * 60 + '\n')

    tests = [
        test_timing,
        test_srt_format,
        test_ass_format,
        test_vtt_format,
        test_offset_adjust,
        test_segmented_adjust,
        test_speed_adjust,
        test_linear_scale,
        test_align_reference,
        test_report_output,
        test_file_io,
        test_cli_module,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f'    ✗ {test.__name__} 失败: {e}')
            traceback.print_exc()

    print('\n' + '=' * 60)
    print(f'  测试完成: {passed} 通过, {failed} 失败')
    print('=' * 60 + '\n')
    return failed == 0


if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)
