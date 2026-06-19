"""
文件编码检测
"""

import os
from typing import Tuple


def detect_encoding(filepath: str) -> Tuple[str, float]:
    """检测文件编码"""
    try:
        import chardet
        with open(filepath, 'rb') as f:
            raw = f.read()
        result = chardet.detect(raw)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0.0)
        if encoding and encoding.lower() in ('gb2312', 'gbk', 'gb18030'):
            encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'gb18030'
        if encoding is None:
            encoding = 'utf-8'
        return encoding, confidence
    except ImportError:
        return 'utf-8', 0.0


def read_file(filepath: str) -> Tuple[str, str]:
    """读取字幕文件内容并返回 (内容, 编码)"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f'文件不存在: {filepath}')
    encoding, _ = detect_encoding(filepath)
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            content = f.read()
    except (UnicodeDecodeError, LookupError):
        for fallback in ('utf-8', 'utf-8-sig', 'gb18030', 'cp1252', 'latin-1'):
            try:
                with open(filepath, 'r', encoding=fallback) as f:
                    content = f.read()
                    encoding = fallback
                    break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            raise UnicodeDecodeError(
                encoding or 'unknown', b'', 0, 1, f'无法解码文件: {filepath}'
            )
    return content, encoding


def write_file(filepath: str, content: str, encoding: str = 'utf-8') -> None:
    """写入字幕文件"""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, 'w', encoding=encoding, newline='\n') as f:
        f.write(content)
