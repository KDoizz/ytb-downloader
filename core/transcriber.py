from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

MODELS_DIR = Path.home() / ".vex" / "models"

_LANG_MAP: dict[str, str] = {
    "pt-BR": "pt", "pt-br": "pt", "pt": "pt",
    "en": "en", "es": "es", "fr": "fr",
    "de": "de", "it": "it", "ja": "ja",
    "zh": "zh-CN", "zh-CN": "zh-CN", "zh-cn": "zh-CN",
    "ko": "ko", "ru": "ru", "ar": "ar", "hi": "hi",
}


def google_lang(lang: str) -> str:
    return _LANG_MAP.get(lang, lang.split("-")[0])


def transcribe(
    audio_path: str,
    target_lang: str = "pt",
    model_size: str = "base",
    on_progress: Callable[[float], None] | None = None,
) -> list[dict]:
    """Transcribe audio and translate to target_lang. Returns [{start, end, text}]."""
    from faster_whisper import WhisperModel

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        model_size, device="cpu", compute_type="int8",
        download_root=str(MODELS_DIR),
    )

    segments_iter, info = model.transcribe(audio_path, beam_size=3)
    src_lang = info.language or "auto"
    duration = max(info.duration or 1.0, 1.0)

    raw: list[dict] = []
    for seg in segments_iter:
        raw.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        if on_progress:
            on_progress(min(seg.end / duration, 0.95))

    tgt_g = google_lang(target_lang)
    src_g = google_lang(src_lang)
    if src_g != tgt_g and raw:
        raw = _translate(raw, tgt_g)

    if on_progress:
        on_progress(1.0)

    return raw


def _translate(segments: list[dict], tgt: str) -> list[dict]:
    from deep_translator import GoogleTranslator

    SEP = "\n||||\n"
    BATCH = 40
    result = [dict(s) for s in segments]

    for i in range(0, len(segments), BATCH):
        batch = segments[i: i + BATCH]
        text_in = SEP.join(s["text"] for s in batch)
        try:
            text_out = GoogleTranslator(source="auto", target=tgt).translate(text_in) or text_in
            parts = re.split(r"\n?\|\|\|\|\n?", text_out)
            for j, part in enumerate(parts[: len(batch)]):
                result[i + j]["text"] = part.strip()
        except Exception:
            pass

    return result


def to_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.extend([str(i), f"{_ts(seg['start'])} --> {_ts(seg['end'])}", seg["text"], ""])
    return "\n".join(lines)


def _ts(s: float) -> str:
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
