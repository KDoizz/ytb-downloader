from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from state.app_state import VEX_DIR

PRESETS_FILE = VEX_DIR / "presets.json"


@dataclass
class Preset:
    name: str
    fmt: str = "MP4"
    quality: str = "720p"
    subtitles: bool = False
    subtitle_source: str = "site"
    subtitle_langs: list[str] = field(default_factory=list)
    subtitle_fmt: str = "srt"
    whisper_model: str = "base"
    chapters: bool = False
    thumbnail_dl: bool = False
    metadata: bool = False
    comments: bool = False


class PresetManager:
    def __init__(self):
        self.presets: list[Preset] = []
        self._load()

    def save(self, preset: Preset):
        self.presets = [p for p in self.presets if p.name != preset.name]
        self.presets.insert(0, preset)
        self._persist()

    def delete(self, name: str):
        self.presets = [p for p in self.presets if p.name != name]
        self._persist()

    def get(self, name: str) -> Preset | None:
        return next((p for p in self.presets if p.name == name), None)

    def names(self) -> list[str]:
        return [p.name for p in self.presets]

    def _load(self):
        if not PRESETS_FILE.exists():
            return
        try:
            valid_keys = {f for f in Preset.__dataclass_fields__}
            for item in json.loads(PRESETS_FILE.read_text("utf-8")):
                clean = {k: v for k, v in item.items() if k in valid_keys}
                self.presets.append(Preset(**clean))
        except Exception:
            pass

    def _persist(self):
        try:
            PRESETS_FILE.parent.mkdir(exist_ok=True)
            PRESETS_FILE.write_text(
                json.dumps([asdict(p) for p in self.presets], indent=2, ensure_ascii=False),
                "utf-8",
            )
        except Exception:
            pass
