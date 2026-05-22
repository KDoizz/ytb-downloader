from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

VEX_DIR = Path.home() / ".vex"
LIBRARY_FILE = VEX_DIR / "library.json"


@dataclass
class DownloadOptions:
    fmt: str = "MP4"
    quality: str = "720p"
    subtitles: bool = False
    chapters: bool = False
    thumbnail_dl: bool = False
    metadata: bool = False


@dataclass
class DownloadJob:
    id: str
    url: str
    title: str
    platform: str
    thumbnail_url: str | None
    options: DownloadOptions
    output_dir: str
    state: Literal["queued", "active", "done", "error", "cancelled"] = "queued"
    progress: float = 0.0
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @staticmethod
    def new(
        url: str,
        title: str,
        platform: str,
        thumbnail_url: str | None,
        options: DownloadOptions,
        output_dir: str,
    ) -> "DownloadJob":
        return DownloadJob(
            id=str(uuid.uuid4()),
            url=url,
            title=title,
            platform=platform,
            thumbnail_url=thumbnail_url,
            options=options,
            output_dir=output_dir,
        )


class AppState:
    def __init__(self):
        self.jobs: list[DownloadJob] = []
        self.library: list[DownloadJob] = []
        self._job_subs: list[Callable] = []
        self._lib_subs: list[Callable] = []
        VEX_DIR.mkdir(exist_ok=True)
        self._load_library()

    def subscribe_jobs(self, cb: Callable):
        self._job_subs.append(cb)

    def subscribe_library(self, cb: Callable):
        self._lib_subs.append(cb)

    def add_job(self, job: DownloadJob):
        self.jobs.append(job)
        self._emit_jobs()

    def update_job(self, job_id: str, **kw):
        j = self._find(job_id)
        if j:
            for k, v in kw.items():
                setattr(j, k, v)
            self._emit_jobs()

    def finish_job(self, job_id: str, success: bool, error: str | None = None):
        j = self._find(job_id)
        if not j:
            return
        j.state = "done" if success else "error"
        j.error = error
        j.finished_at = datetime.now().isoformat()
        if success:
            self.library.insert(0, j)
            self._save_library()
            self._emit_library()
        self._emit_jobs()

    def cancel_job(self, job_id: str):
        j = self._find(job_id)
        if j and j.state in ("queued", "active"):
            j.state = "cancelled"
            self._emit_jobs()

    def clear_done(self):
        self.jobs = [j for j in self.jobs if j.state not in ("done", "error", "cancelled")]
        self._emit_jobs()

    def _find(self, job_id: str) -> DownloadJob | None:
        return next((j for j in self.jobs if j.id == job_id), None)

    def _emit_jobs(self):
        for cb in self._job_subs:
            try:
                cb()
            except Exception:
                pass

    def _emit_library(self):
        for cb in self._lib_subs:
            try:
                cb()
            except Exception:
                pass

    def _load_library(self):
        if not LIBRARY_FILE.exists():
            return
        try:
            for item in json.loads(LIBRARY_FILE.read_text("utf-8")):
                opts_raw = item.pop("options", {})
                valid = {k: v for k, v in opts_raw.items() if hasattr(DownloadOptions, k)}
                opts = DownloadOptions(**valid)
                self.library.append(DownloadJob(options=opts, **item))
        except Exception:
            pass

    def _save_library(self):
        try:
            items = [
                {
                    "id": j.id, "url": j.url, "title": j.title,
                    "platform": j.platform, "thumbnail_url": j.thumbnail_url,
                    "options": asdict(j.options), "output_dir": j.output_dir,
                    "state": j.state, "progress": j.progress, "error": j.error,
                    "started_at": j.started_at, "finished_at": j.finished_at,
                }
                for j in self.library[:300]
            ]
            LIBRARY_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass
