from __future__ import annotations


def strip_leading_bom_mojibake(text: str) -> str:
    cleaned = text.lstrip("锘?")
    slash_index = cleaned.find("/")
    if 0 < slash_index <= 3:
        prefix = cleaned[:slash_index]
        if all((ord(ch) > 127) or ch == "?" or (0xDC00 <= ord(ch) <= 0xDFFF) for ch in prefix):
            return cleaned[slash_index:]
    return cleaned


def normalize_cli_input(raw_input: str) -> str:
    return strip_leading_bom_mojibake(raw_input).replace("\x00", "").strip()
