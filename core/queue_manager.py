import queue
import threading
from datetime import datetime

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
        self._state.update_job(
            job.id, state="active", started_at=datetime.now().isoformat()
        )

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
        if opts.subtitles:
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

        dl.download(
            job.url, job.output_dir,
            opts.fmt, opts.quality,
            on_progress, on_processing, on_done, on_error,
            extra=extra,
        )
        done.wait()
        self._state.finish_job(job.id, result[0], result[1])
