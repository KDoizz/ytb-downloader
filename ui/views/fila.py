from __future__ import annotations

import customtkinter as ctk

from state.app_state import AppState, DownloadJob
from ui.theme import (
    ACCENT, BG_ELEV, BG_ELEV_2, BORDER,
    TEXT, TEXT_SOFT, TEXT_FAINT,
    SUCCESS, DANGER, WARNING,
)

_STATE_COLORS = {
    "queued":    TEXT_FAINT,
    "active":    ACCENT,
    "done":      SUCCESS,
    "error":     DANGER,
    "cancelled": TEXT_FAINT,
}

_STATE_LABELS = {
    "queued":    "na fila",
    "active":    "baixando",
    "done":      "✓ pronto",
    "error":     "erro",
    "cancelled": "cancelado",
}


class FilaView(ctk.CTkFrame):
    def __init__(self, parent, state: AppState, cancel_cb=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._state = state
        self._cancel_cb = cancel_cb
        self._build()
        state.subscribe_jobs(lambda: self.after(0, self._refresh))

    def _build(self):
        # Header bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 8))

        self._counter_lbl = ctk.CTkLabel(
            header, text="", text_color=TEXT_SOFT, font=ctk.CTkFont(size=13),
        )
        self._counter_lbl.pack(side="left")

        ctk.CTkButton(
            header, text="Limpar prontos", width=120, height=28,
            fg_color="transparent", hover_color=BG_ELEV_2,
            border_width=1, border_color=BORDER,
            text_color=TEXT_FAINT, corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._clear_done,
        ).pack(side="right")

        # Scrollable job list
        self._list = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BG_ELEV_2,
            scrollbar_button_hover_color=BORDER,
        )
        self._list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._refresh()

    def _refresh(self):
        # Destroy and rebuild job rows
        for w in self._list.winfo_children():
            w.destroy()

        jobs = self._state.jobs
        if not jobs:
            ctk.CTkLabel(
                self._list, text="Nenhum download na fila.",
                text_color=TEXT_FAINT, font=ctk.CTkFont(size=13),
            ).pack(pady=48)
            self._counter_lbl.configure(text="")
            return

        active = sum(1 for j in jobs if j.state == "active")
        queued = sum(1 for j in jobs if j.state == "queued")
        done   = sum(1 for j in jobs if j.state == "done")
        parts  = []
        if active: parts.append(f"{active} ativo{'s' if active > 1 else ''}")
        if queued: parts.append(f"{queued} na fila")
        if done:   parts.append(f"{done} pronto{'s' if done > 1 else ''}")
        self._counter_lbl.configure(text=" · ".join(parts))

        for job in jobs:
            self._build_job_row(job)

    def _build_job_row(self, job: DownloadJob):
        row = ctk.CTkFrame(
            self._list, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        row.pack(fill="x", pady=(0, 6))

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))

        # Title
        title = job.title if len(job.title) <= 60 else job.title[:57] + "..."
        ctk.CTkLabel(
            top, text=title, anchor="w",
            font=ctk.CTkFont(size=13), text_color=TEXT,
        ).pack(side="left", fill="x", expand=True)

        # State chip
        color = _STATE_COLORS.get(job.state, TEXT_FAINT)
        ctk.CTkLabel(
            top, text=_STATE_LABELS.get(job.state, job.state),
            text_color=color, font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="right", padx=(8, 0))

        # Meta row
        meta = ctk.CTkFrame(row, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 4))

        fmt_str = f"{job.options.fmt} {job.options.quality}"
        ctk.CTkLabel(
            meta, text=f"{job.platform} · {fmt_str}",
            text_color=TEXT_FAINT, font=ctk.CTkFont(family="Consolas", size=11),
        ).pack(side="left")

        # Cancel button (only for active/queued)
        if job.state in ("active", "queued") and self._cancel_cb:
            ctk.CTkButton(
                meta, text="cancelar", width=70, height=22,
                fg_color="transparent", hover_color=BG_ELEV_2,
                border_width=1, border_color=BORDER,
                text_color=TEXT_FAINT, corner_radius=6, font=ctk.CTkFont(size=11),
                command=lambda jid=job.id: self._cancel_cb(jid),
            ).pack(side="right")

        # Error message
        if job.state == "error" and job.error:
            ctk.CTkLabel(
                row, text=job.error[:120], text_color=DANGER,
                font=ctk.CTkFont(size=11), wraplength=480, justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 4))

        # Progress bar (active jobs only)
        if job.state == "active":
            pb = ctk.CTkProgressBar(
                row, progress_color=ACCENT, fg_color=BG_ELEV_2,
                corner_radius=3, height=4,
            )
            pb.pack(fill="x", padx=12, pady=(0, 10))
            pb.set(job.progress)
        elif job.state == "done":
            pb = ctk.CTkProgressBar(
                row, progress_color=SUCCESS, fg_color=BG_ELEV_2,
                corner_radius=3, height=4,
            )
            pb.pack(fill="x", padx=12, pady=(0, 10))
            pb.set(1.0)
        else:
            # Spacer
            ctk.CTkFrame(row, fg_color="transparent", height=10).pack()

    def _clear_done(self):
        self._state.clear_done()
