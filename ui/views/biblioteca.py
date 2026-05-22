from __future__ import annotations

import os
import subprocess
from datetime import datetime

import customtkinter as ctk

from state.app_state import AppState, DownloadJob
from ui.theme import (
    ACCENT, BG_ELEV, BG_ELEV_2, BORDER,
    TEXT, TEXT_SOFT, TEXT_FAINT, SUCCESS,
)

_PLATFORM_COLORS = {
    "youtube":   "#FF0000",
    "twitter":   "#1DA1F2",
    "instagram": "#E1306C",
    "tiktok":    "#69C9D0",
    "vimeo":     "#1AB7EA",
    "soundcloud":"#FF5500",
}


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%y %H:%M")
    except Exception:
        return ""


class BibliotecaView(ctk.CTkFrame):
    def __init__(self, parent, state: AppState, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._state = state
        self._filter = "tudo"
        self._build()
        state.subscribe_library(lambda: self.after(0, self._refresh))

    def _build(self):
        # Filter bar
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=20, pady=(14, 8))

        self._filter_btns: dict[str, ctk.CTkButton] = {}
        filters = ["tudo", "vídeo", "áudio", "youtube", "twitter", "instagram"]
        for f in filters:
            btn = ctk.CTkButton(
                filter_row, text=f, width=72, height=28,
                fg_color=BG_ELEV if f != "tudo" else ACCENT,
                hover_color=BG_ELEV_2,
                border_width=1, border_color=BORDER,
                text_color=TEXT if f == "tudo" else TEXT_SOFT,
                corner_radius=20, font=ctk.CTkFont(size=12),
                command=lambda val=f: self._set_filter(val),
            )
            btn.pack(side="left", padx=(0, 4))
            self._filter_btns[f] = btn

        # Scrollable list
        self._list = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BG_ELEV_2,
            scrollbar_button_hover_color=BORDER,
        )
        self._list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._refresh()

    def _set_filter(self, f: str):
        self._filter = f
        for name, btn in self._filter_btns.items():
            active = name == f
            btn.configure(
                fg_color=ACCENT if active else BG_ELEV,
                text_color=TEXT if active else TEXT_SOFT,
            )
        self._refresh()

    def _refresh(self):
        for w in self._list.winfo_children():
            w.destroy()

        items = self._filtered()
        if not items:
            ctk.CTkLabel(
                self._list,
                text="Nenhum download encontrado." if self._filter == "tudo" else f'Nenhum item para "{self._filter}".',
                text_color=TEXT_FAINT, font=ctk.CTkFont(size=13),
            ).pack(pady=48)
            return

        for job in items:
            self._build_row(job)

    def _filtered(self) -> list[DownloadJob]:
        lib = self._state.library
        f = self._filter
        if f == "tudo":
            return lib
        if f == "vídeo":
            return [j for j in lib if j.options.fmt == "MP4"]
        if f == "áudio":
            return [j for j in lib if j.options.fmt == "MP3"]
        return [j for j in lib if f.lower() in j.platform.lower()]

    def _build_row(self, job: DownloadJob):
        row = ctk.CTkFrame(
            self._list, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        row.pack(fill="x", pady=(0, 6))

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        # Platform chip
        chip_color = _PLATFORM_COLORS.get(job.platform.lower(), ACCENT)
        chip = ctk.CTkFrame(inner, fg_color=chip_color, corner_radius=4, width=6)
        chip.pack(side="left", fill="y", padx=(0, 10))
        chip.pack_propagate(False)

        # Text block
        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)

        title = job.title if len(job.title) <= 65 else job.title[:62] + "..."
        ctk.CTkLabel(
            text_col, text=title, anchor="w",
            font=ctk.CTkFont(size=13), text_color=TEXT,
        ).pack(anchor="w")

        fmt_str = f"{job.options.fmt} · {job.options.quality}"
        meta = f"{job.platform} · {fmt_str} · {_fmt_date(job.finished_at)}"
        ctk.CTkLabel(
            text_col, text=meta, anchor="w",
            text_color=TEXT_FAINT, font=ctk.CTkFont(family="Consolas", size=11),
        ).pack(anchor="w", pady=(2, 0))

        # Open folder button
        ctk.CTkButton(
            inner, text="📂", width=36, height=36,
            fg_color=BG_ELEV_2, hover_color=BORDER,
            text_color=TEXT_SOFT, corner_radius=8, font=ctk.CTkFont(size=14),
            command=lambda d=job.output_dir: self._open_folder(d),
        ).pack(side="right")

    def _open_folder(self, path: str):
        try:
            if os.path.isdir(path):
                subprocess.Popen(["explorer", path])
        except Exception:
            pass
