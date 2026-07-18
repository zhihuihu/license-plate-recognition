from __future__ import annotations

import re
import unicodedata

from .base import PlateCandidate


_PROVINCE_CHARS = "京津冀晋蒙辽吉黑沪苏浙皖闽赣鲁豫鄂湘粤桂琼渝川贵云藏陕甘青宁新"
_PROVINCE = f"[{_PROVINCE_CHARS}]"
_PROVINCIAL_PLATE_PATTERNS = (
    # 教练、警用、挂车、试验等专用牌：末尾带专用汉字。
    re.compile(rf"{_PROVINCE}[A-Z][A-Z0-9]{{4,6}}[学警挂试]"),
    # 香港/澳门入出境车辆：粤Z1234港、粤Z1234澳。
    re.compile(rf"{_PROVINCE}Z[A-Z0-9]{{3,5}}[港澳]"),
    # 普通汽车、摩托车和新能源车牌：省份 + 发牌机关 + 5/6 位序号。
    re.compile(rf"{_PROVINCE}[A-Z][A-Z0-9]{{5,6}}"),
)
_SPECIAL_PLATE_PATTERNS = (
    # 武警等特殊白牌，例如 WJ·N22628。
    re.compile(r"WJ[A-Z0-9]{5,7}"),
    # 使馆、领馆车辆，常见形式为 使12345、领123456。
    re.compile(r"[使领][A-Z0-9]{3,6}"),
    # 军队及部分军用车辆常见前缀；具体编制号段不在图片 OCR 层校验。
    re.compile(r"[军海空北南沈兰济广成][A-Z0-9]{5,7}"),
)
_DOUBLE_LINE_TOP_PATTERN = re.compile(r"^[\u4e00-\u9fff][A-Z]$")
_ALPHANUMERIC_PATTERN = re.compile(r"^[A-Z0-9]+$")


def normalize_plate(text: str) -> str | None:
    """清理 OCR 分隔符和全角字符，并提取车牌号。"""
    normalized = unicodedata.normalize("NFKC", text).upper()
    normalized = re.sub(r"[\s·•.。:：_\-—|/\\()（）\[\]【】]", "", normalized)
    for plate_pattern in _PROVINCIAL_PLATE_PATTERNS:
        match = plate_pattern.search(normalized)
        if match:
            return match.group(0)
    for special_pattern in _SPECIAL_PLATE_PATTERNS:
        special_match = special_pattern.search(normalized)
        if special_match:
            return special_match.group(0)
    return None


def build_plate_candidates(lines: list[tuple[str, float]]) -> list[PlateCandidate]:
    """从 OCR 文本行生成单行和双层车牌候选。"""
    candidates: list[PlateCandidate] = []
    compact_lines: list[tuple[str, float]] = []

    for text, score in lines:
        confidence = max(0.0, min(1.0, float(score)))
        compact = _compact_line(text)
        compact_lines.append((compact, confidence))
        plate_number = normalize_plate(text)
        if plate_number:
            candidates.append(PlateCandidate(plate_number, confidence))

    # 摩托车双层黄牌通常被 OCR 识别为“省份+字母”和一行数字/字母，
    # 例如：川·A + 4X144。将两行拼接后再走统一车牌格式校验。
    for top_index, (top_line, top_confidence) in enumerate(compact_lines):
        if not _DOUBLE_LINE_TOP_PATTERN.fullmatch(top_line):
            continue
        for bottom_index, (bottom_line, bottom_confidence) in enumerate(compact_lines):
            if top_index == bottom_index:
                continue
            if not 3 <= len(bottom_line) <= 6 or not _ALPHANUMERIC_PATTERN.fullmatch(bottom_line):
                continue
            plate_number = normalize_plate(top_line + bottom_line)
            if plate_number:
                candidates.append(
                    PlateCandidate(
                        plate_number=plate_number,
                        confidence=min(top_confidence, bottom_confidence),
                    )
                )
    return candidates


def _compact_line(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).upper()
    return re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", normalized)
