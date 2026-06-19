"""
TextSimilarityAligner - 基于文本相似度的对齐器

计算源字幕和参考字幕文本之间的相似度（使用 Levenshtein 比率），
找到最佳匹配的对应点，然后用线性回归计算映射参数。
适合：双语字幕或字幕文本不完全一致但语义相近的场景。
"""

import re
from typing import List, Tuple, Dict

from .base import BaseAligner, AlignerResult, register_aligner
from .linear_scale import _find_linear_mapping
from ..models import Subtitle, Cue


def _normalize_text(text: str) -> str:
    """标准化文本，移除标签、标点等干扰因素"""
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\s\-—_·.。，,、!！?？"\'()（）\[\]【】]+', ' ', text)
    text = text.strip().lower()
    return text


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """计算两个字符串的 Levenshtein 相似度 (0.0 ~ 1.0)"""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    if len1 < len2:
        s1, s2 = s2, s1
        len1, len2 = len2, len1
    if len2 == 0:
        return 1.0 if len1 == 0 else 0.0
    prev = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        curr = [i] + [0] * len2
        c1 = s1[i - 1]
        for j in range(1, len2 + 1):
            cost = 0 if c1 == s2[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    distance = prev[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)


def _subsequence_ratio(s1: str, s2: str) -> float:
    """计算公共子序列比率"""
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[len1][len2]
    min_len = min(len1, len2)
    return lcs / min_len if min_len > 0 else 0.0


def _similarity(s1: str, s2: str) -> float:
    """综合相似度：LCS 比率 + Levenshtein 比率"""
    norm1 = _normalize_text(s1)
    norm2 = _normalize_text(s2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
    lcs = _subsequence_ratio(norm1, norm2)
    lev = _levenshtein_ratio(norm1, norm2)
    return 0.6 * lcs + 0.4 * lev


def _find_matching_pairs(source: List[Cue], reference: List[Cue],
                         threshold: float = 0.75,
                         max_search_window: int = 50) -> List[Tuple[float, float]]:
    """
    寻找匹配的字幕对，采用贪心 + 窗口限制

    Args:
        source: 源字幕条目
        reference: 参考字幕条目
        threshold: 相似度阈值
        max_search_window: 搜索窗口大小（防止跨得太远）

    Returns:
        匹配对列表 [(src_start, ref_start), ...]
    """
    src_norm = [_normalize_text(c.text) for c in source]
    ref_norm = [_normalize_text(c.text) for c in reference]

    matches: List[Tuple[float, float]] = []
    used_src = set()
    used_ref = set()

    n_src, n_ref = len(source), len(reference)

    if n_src == 0 or n_ref == 0:
        return matches

    for i in range(n_src):
        if i in used_src:
            continue
        if not src_norm[i]:
            continue

        best_j = -1
        best_sim = 0.0

        ref_pos = int((i / n_src) * n_ref) if n_src > 0 else 0
        j_start = max(0, ref_pos - max_search_window)
        j_end = min(n_ref, ref_pos + max_search_window + 1)

        for j in range(j_start, j_end):
            if j in used_ref:
                continue
            if not ref_norm[j]:
                continue
            sim = _similarity(src_norm[i], ref_norm[j])
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_sim >= threshold and best_j >= 0:
            matches.append((source[i].start, reference[best_j].start))
            used_src.add(i)
            used_ref.add(best_j)

    return sorted(matches, key=lambda x: x[0])


@register_aligner
class TextSimilarityAligner(BaseAligner):
    """基于文本相似度的对齐器

    策略：对每一条源字幕在参考字幕中（比例对应的窗口内）寻找最相似的文本匹配，
    对高于阈值的匹配对进行线性回归。适合双语字幕或文本不完全一致的场景。
    """

    name = 'text_similarity'
    description = '文本相似度匹配（LCS + Levenshtein，双语字幕友好）'

    similarity_threshold = 0.75
    search_window = 50
    min_match_points = 3

    def compute(self, source: Subtitle, reference: Subtitle) -> AlignerResult:
        if not reference.cues or not source.cues:
            return AlignerResult(method=self.name)

        matches = _find_matching_pairs(
            source.cues, reference.cues,
            threshold=self.similarity_threshold,
            max_search_window=self.search_window
        )

        if len(matches) < self.min_match_points:
            from .linear_scale import LinearScaleAligner
            fallback = LinearScaleAligner()
            result = fallback.compute(source, reference)
            result.method = f'{self.name} (fallback: {result.method})'
            return result

        src_starts = [m[0] for m in matches]
        dst_starts = [m[1] for m in matches]
        scale, offset = _find_linear_mapping(src_starts, dst_starts)

        return AlignerResult(
            scale=scale,
            offset=offset,
            matched_points=matches,
            method=self.name,
            params={
                'matched_count': len(matches),
                'similarity_threshold': self.similarity_threshold,
                'avg_similarity': (
                    sum(
                        _similarity(source.cues[i].text, reference.cues[j].text)
                        for i in range(len(source.cues))
                        for j in range(len(reference.cues))
                    ) / max(1, len(matches) * len(matches))
                    if False else 0.0
                )
            }
        )
