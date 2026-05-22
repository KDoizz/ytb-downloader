from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import core.downloader as dl
from state.app_state import AppState, DownloadJob


class QueueManager:
    def __init__(self, state: AppState, max_workers: int = 2):
        self._state = state
        self._q: queue.Queue = queue.Queue()
        self._cancelled: set[str] = set()
        for _ in range(max_workers):
            threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, job: DownloadJob):
        self._state.add_job(job)
        self._q.put(job)

    def cancel(self, job_id: str):
        self._cancelled.add(job_id)
        self._state.cancel_job(job_id)

    def _worker(self):
        while True:
            job = self._q.get()
            try:
                if job.id not in self._cancelled:
                    self._run(job)
            finally:
                self._q.task_done()

    def _run(self, job: DownloadJob):
        self._state.update_job(job.id, state="active", started_at=datetime.now().isoformat())

        done = threading.Event()
        result: list = [True, None]

        def on_progress(pct: float):
            if job.id not in self._cancelled:
                self._state.update_job(job.id, progress=pct)

        def on_processing():
            self._state.update_job(job.id, progress=1.0)

        def on_done():
            result[0], result[1] = True, None
            done.set()

        def on_error(msg: str):
            result[0], result[1] = False, msg
            done.set()

        opts = job.options
        extra: dict = {}
        use_whisper = opts.subtitles and getattr(opts, "subtitle_source", "site") == "whisper"

        if opts.subtitles and not use_whisper:
            langs = opts.subtitle_langs or ["pt-BR", "en"]
            fmt = opts.subtitle_fmt or "srt"
            embed = fmt in ("embutido", "ambos")
            extra.update(writesubtitles=True, writeautomaticsub=True, subtitleslangs=langs)
            if fmt in ("srt", "ambos"):
                extra["subtitlesformat"] = "srt"
            if embed:
                extra["embedsubtitles"] = True
        if opts.chapters:
            extra["addchapters"] = True
        if opts.thumbnail_dl:
            extra.update(writethumbnail=True, embedthumbnail=True)
        if opts.metadata:
            extra.update(writedescription=True, writeinfojson=True)
        if opts.comments:
            extra.update(getcomments=True, writecomments=True)

        # Snapshot files before download to identify output file for Whisper
        files_before = set(Path(job.output_dir).iterdir()) if use_whisper else set()

        dl.download(
            job.url, job.output_dir,
            opts.fmt, opts.quality,
            on_progress, on_processing, on_done, on_error,
            extra=extra,
        )
        done.wait()

        if result[0] and use_whisper and job.id not in self._cancelled:
            try:
                self._run_whisper(job, files_before, on_progress)
            except Exception as exc:
                # Subtitle failure doesn't fail the whole job; log to error field
                self._state.update_job(job.id, error=f"Whisper: {exc}")

        self._state.finish_job(job.id, result[0], result[1])

    def _run_whisper(self, job: DownloadJob, files_before: set, on_progress):
        from core.transcriber import transcribe, to_srt

        opts = job.options
        output_dir = Path(job.output_dir)

        # Find the downloaded video/audio file (largest new file)
        files_after = set(output_dir.iterdir())
        new_files = [f for f in (files_after - files_before) if f.is_file()]
        if not new_files:
            return
        video_file = max(new_files, key=lambda p: p.stat().st_size)

        # Update state: transcribing (reuse progress bar)
        self._state.update_job(job.id, progress=0.0)

        temp_dir = tempfile.mkdtemp()
        try:
            audio_path = _extract_audio(str(video_file), temp_dir)
            langs = opts.subtitle_langs or ["pt-BR"]
            target = langs[0] if langs else "pt-BR"
            model_size = getattr(opts, "whisper_model", "base")

            segments = transcribe(
                audio_path, target_lang=target,
                model_size=model_size,
                on_progress=on_progress,
            )

            srt_content = to_srt(segments)
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", job.title[:80])
            lang_code = target.replace("-", "_")
            srt_path = output_dir / f"{safe_name}.{lang_code}.srt"
            srt_path.write_text(srt_content, "utf-8")

            fmt = getattr(opts, "subtitle_fmt", "srt")
            if fmt in ("embutido", "ambos") and dl.FFMPEG_PATH:
                _embed_srt(str(video_file), str(srt_path), dl.FFMPEG_PATH)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _extract_audio(video_path: str, temp_dir: str) -> str:
    if not dl.FFMPEG_PATH:
        raise RuntimeError("ffmpeg não encontrado")
    audio_path = os.path.join(temp_dir, "audio.wav")
    subprocess.run(
        [dl.FFMPEG_PATH, "-y", "-i", video_path,
         "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path],
        check=True, capture_output=True,
    )
    return audio_path


def _embed_srt(video_path: str, srt_path: str, ffmpeg: str):
    p = Path(video_path)
    out_path = str(p.with_stem(p.stem + "_legendado"))
    sub_codec = "mov_text" if p.suffix.lower() in (".mp4", ".m4v") else "srt"
    subprocess.run(
        [ffmpeg, "-y",
         "-i", video_path,
         "-i", srt_path,
         "-map", "0",
         "-map", "1",
         "-c:v", "copy",
         "-c:a", "copy",
         "-c:s", sub_codec,
         out_path],
        check=True, capture_output=True,
    )
