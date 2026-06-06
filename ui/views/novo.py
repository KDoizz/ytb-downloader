from __future__ import annotations

import io
import os
import re
import sys
import threading
import urllib.request
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import core.downloader as dl
from state.app_state import DownloadJob, DownloadOptions
from state.presets import PresetManager, Preset
from ui.theme import (
    ACCENT, BG_ELEV, BG_ELEV_2, BORDER,
    TEXT, TEXT_SOFT, TEXT_FAINT,
    DANGER, WARNING,
)

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

_SPINNER = "⣾⣽⣻⢿⡿⣟⣯⣷"


class NovoView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_start_download: Callable[[DownloadJob], None] | None = None,
        preset_manager: PresetManager | None = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_start_download = on_start_download
        self._presets = preset_manager or PresetManager()
        self._state = "EMPTY"
        self._info: dict | None = None
        self._cancel_event = threading.Event()
        self._spinner_idx = 0
        self._sugg_url = ""
        self._current_url = ""
        self._download_path = str(Path.home() / "Downloads")

        self._build_url_bar()
        self._build_empty()
        self._build_analyzing()
        self._build_result()
        self._go("EMPTY")

        # Check clipboard after UI is ready
        self.after(400, self.check_clipboard)

    # ── URL bar ───────────────────────────────────────────────────────────────

    def _build_url_bar(self):
        self._frame_url_bar = ctk.CTkFrame(
            self, fg_color=BG_ELEV, corner_radius=8,
            border_width=1, border_color=BORDER,
        )
        self._url_display = ctk.CTkLabel(
            self._frame_url_bar, text="", text_color=TEXT_SOFT,
            font=ctk.CTkFont(family="Consolas", size=11), anchor="w",
        )
        self._url_display.pack(side="left", fill="x", expand=True, padx=(12, 0), pady=8)
        ctk.CTkButton(
            self._frame_url_bar, text="✕", width=32, height=28,
            fg_color="transparent", hover_color=BG_ELEV_2,
            text_color=TEXT_FAINT, corner_radius=6,
            command=self._cancel,
        ).pack(side="right", padx=6, pady=4)

    # ── EMPTY state ───────────────────────────────────────────────────────────

    def _build_empty(self):
        self._frame_empty = ctk.CTkFrame(self, fg_color="transparent")
        self._frame_empty.rowconfigure(0, weight=1)
        self._frame_empty.rowconfigure(1, weight=0)
        self._frame_empty.columnconfigure(0, weight=1)

        # Drop zone
        dropzone = ctk.CTkFrame(
            self._frame_empty, fg_color=BG_ELEV, corner_radius=16,
            border_width=2, border_color=ACCENT,
        )
        dropzone.grid(row=0, column=0, sticky="nsew", padx=20, pady=(12, 6))

        inner = ctk.CTkFrame(dropzone, fg_color="transparent")
        inner.place(relx=0.5, rely=0.48, anchor="center")

        ctk.CTkLabel(
            inner, text="⬇", font=ctk.CTkFont(size=42), text_color=ACCENT,
        ).pack()
        ctk.CTkLabel(
            inner, text="cole qualquer link aqui",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT,
        ).pack(pady=(6, 4))
        ctk.CTkLabel(
            inner,
            text="youtube · twitter/x · instagram · tiktok · vimeo · soundcloud · +1000",
            text_color=TEXT_FAINT, font=ctk.CTkFont(family="Consolas", size=11),
        ).pack()

        chip_row = ctk.CTkFrame(inner, fg_color="transparent")
        chip_row.pack(pady=(16, 0))
        ctk.CTkButton(
            chip_row, text="Ctrl+V  colar", width=120, height=30,
            fg_color=BG_ELEV_2, hover_color=BORDER,
            border_width=1, border_color=BORDER,
            text_color=TEXT_SOFT, corner_radius=20, font=ctk.CTkFont(size=12),
            command=self._paste_and_analyze,
        ).pack(side="left", padx=4)

        # Clipboard suggestion (hidden by default)
        self._sugg_frame = ctk.CTkFrame(self._frame_empty, fg_color="transparent")
        ctk.CTkLabel(
            self._sugg_frame, text="SUGESTÃO DO CLIPBOARD",
            text_color=TEXT_FAINT, font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        self._sugg_btn = ctk.CTkButton(
            self._sugg_frame, text="", anchor="w",
            fg_color=BG_ELEV, hover_color=BG_ELEV_2,
            border_width=1, border_color=BORDER,
            text_color=TEXT_SOFT, corner_radius=8, height=34,
            font=ctk.CTkFont(family="Consolas", size=11),
            command=self._use_suggestion,
        )
        self._sugg_btn.pack(fill="x", padx=20, pady=(0, 8))

    # ── ANALYZING state ───────────────────────────────────────────────────────

    def _build_analyzing(self):
        self._frame_analyzing = ctk.CTkFrame(self, fg_color="transparent")
        inner = ctk.CTkFrame(self._frame_analyzing, fg_color="transparent")
        inner.place(relx=0.5, rely=0.42, anchor="center")
        self._spinner_lbl = ctk.CTkLabel(
            inner, text="⣾  analisando link...",
            text_color=TEXT_SOFT, font=ctk.CTkFont(size=14),
        )
        self._spinner_lbl.pack()

    # ── RESULT state ──────────────────────────────────────────────────────────

    def _build_result(self):
        self._frame_result = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BG_ELEV_2,
            scrollbar_button_hover_color=BORDER,
        )

        # Info card
        info_card = ctk.CTkFrame(
            self._frame_result, fg_color=BG_ELEV, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        info_card.pack(fill="x", padx=4, pady=(4, 10))

        card_row = ctk.CTkFrame(info_card, fg_color="transparent")
        card_row.pack(fill="x", padx=12, pady=12)

        self._thumb_lbl = ctk.CTkLabel(
            card_row, text="", width=120, height=68,
            fg_color=BG_ELEV_2, corner_radius=6,
        )
        self._thumb_lbl.pack(side="left", padx=(0, 12))

        meta_col = ctk.CTkFrame(card_row, fg_color="transparent")
        meta_col.pack(side="left", fill="both", expand=True)

        self._title_lbl = ctk.CTkLabel(
            meta_col, text="", wraplength=340, justify="left",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT, anchor="w",
        )
        self._title_lbl.pack(anchor="w")
        self._meta_lbl = ctk.CTkLabel(
            meta_col, text="", text_color=TEXT_SOFT,
            font=ctk.CTkFont(family="Consolas", size=11), anchor="w",
        )
        self._meta_lbl.pack(anchor="w", pady=(2, 0))

        # Preset row
        preset_row = ctk.CTkFrame(self._frame_result, fg_color="transparent")
        preset_row.pack(fill="x", padx=4, pady=(0, 8))
        ctk.CTkLabel(
            preset_row, text="Preset",
            text_color=TEXT_SOFT, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(2, 8))
        self._preset_var = ctk.StringVar(value="Nenhum")
        self._preset_menu = ctk.CTkOptionMenu(
            preset_row, variable=self._preset_var,
            values=["Nenhum"], width=140, height=30,
            fg_color=BG_ELEV_2, button_color=ACCENT, button_hover_color=ACCENT,
            text_color=TEXT, corner_radius=6, command=self._apply_preset,
        )
        self._preset_menu.pack(side="left")
        ctk.CTkButton(
            preset_row, text="Salvar preset", width=110, height=30,
            fg_color="transparent", hover_color=BG_ELEV_2,
            border_width=1, border_color=BORDER,
            text_color=TEXT_SOFT, corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._save_preset,
        ).pack(side="left", padx=(8, 0))

        # MÍDIA
        ctk.CTkLabel(
            self._frame_result, text="MÍDIA",
            text_color=TEXT_FAINT, font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w", padx=6, pady=(2, 4))

        media_card = ctk.CTkFrame(
            self._frame_result, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        media_card.pack(fill="x", padx=4, pady=(0, 10))

        self._media_var = ctk.IntVar(value=0)

        v_row = ctk.CTkFrame(media_card, fg_color="transparent")
        v_row.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkRadioButton(
            v_row, text="Vídeo + áudio", variable=self._media_var, value=0,
            fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT,
            command=self._update_dl_btn,
        ).pack(side="left")
        ctk.CTkLabel(v_row, text="MP4", text_color=TEXT_SOFT, font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 4))
        self._quality_var = ctk.StringVar(value="720p")
        self._quality_menu = ctk.CTkOptionMenu(
            v_row, variable=self._quality_var, values=["720p"], width=90, height=28,
            fg_color=BG_ELEV_2, button_color=ACCENT, button_hover_color=ACCENT,
            text_color=TEXT, corner_radius=6, command=lambda _: self._update_dl_btn(),
        )
        self._quality_menu.pack(side="left")

        a_row = ctk.CTkFrame(media_card, fg_color="transparent")
        a_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkRadioButton(
            a_row, text="Só áudio", variable=self._media_var, value=1,
            fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT,
            command=self._update_dl_btn,
        ).pack(side="left")
        ctk.CTkLabel(a_row, text="MP3", text_color=TEXT_SOFT, font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 4))
        self._bitrate_var = ctk.StringVar(value="192kbps")
        ctk.CTkOptionMenu(
            a_row, variable=self._bitrate_var,
            values=["320kbps", "192kbps", "128kbps", "64kbps"],
            width=100, height=28, fg_color=BG_ELEV_2, button_color=ACCENT,
            button_hover_color=ACCENT, text_color=TEXT, corner_radius=6,
        ).pack(side="left")

        # EXTRAS
        ctk.CTkLabel(
            self._frame_result, text="EXTRAS",
            text_color=TEXT_FAINT, font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w", padx=6, pady=(0, 4))

        extras_card = ctk.CTkFrame(
            self._frame_result, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        extras_card.pack(fill="x", padx=4, pady=(0, 10))

        # Row 1: Legendas + lang/fmt selectors (shown when checked)
        subs_row = ctk.CTkFrame(extras_card, fg_color="transparent")
        subs_row.pack(fill="x", padx=14, pady=(10, 4))

        self._subs_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            subs_row, text="Legendas", variable=self._subs_var,
            fg_color=ACCENT, hover_color=ACCENT, border_color=BORDER,
            command=self._on_subs_toggle,
        ).pack(side="left")

        self._subs_extras = ctk.CTkFrame(subs_row, fg_color="transparent")

        # Source toggle: Site | Whisper
        self._subs_source_var = ctk.StringVar(value="Site")
        ctk.CTkSegmentedButton(
            self._subs_extras,
            values=["Site", "Whisper ✦"],
            variable=self._subs_source_var,
            width=160, height=26,
            fg_color=BG_ELEV_2,
            selected_color=ACCENT, selected_hover_color=ACCENT,
            unselected_color=BG_ELEV_2, unselected_hover_color=BG_ELEV_2,
            text_color=TEXT, font=ctk.CTkFont(size=12),
            command=self._on_subs_source_change,
        ).pack(side="left", padx=(8, 4))

        # Language (target for Whisper, filter for Site)
        self._subs_lang_var = ctk.StringVar(value="pt-BR")
        self._subs_lang_menu = ctk.CTkOptionMenu(
            self._subs_extras, variable=self._subs_lang_var,
            values=["pt-BR", "en", "es", "fr", "de", "ja", "zh-CN", "ko", "ru", "ar"],
            width=90, height=26,
            fg_color=BG_ELEV_2, button_color=ACCENT, button_hover_color=ACCENT,
            text_color=TEXT, corner_radius=6,
        )
        self._subs_lang_menu.pack(side="left", padx=(0, 4))

        # Format
        self._subs_fmt_var = ctk.StringVar(value="srt")
        ctk.CTkOptionMenu(
            self._subs_extras, variable=self._subs_fmt_var,
            values=["srt", "embutido", "ambos"],
            width=90, height=26,
            fg_color=BG_ELEV_2, button_color=ACCENT, button_hover_color=ACCENT,
            text_color=TEXT, corner_radius=6,
        ).pack(side="left", padx=(0, 4))

        # Whisper model (shown only when Whisper selected)
        self._whisper_model_var = ctk.StringVar(value="base")
        self._whisper_model_menu = ctk.CTkOptionMenu(
            self._subs_extras, variable=self._whisper_model_var,
            values=["tiny", "base", "small", "medium"],
            width=80, height=26,
            fg_color=BG_ELEV_2, button_color=ACCENT, button_hover_color=ACCENT,
            text_color=TEXT, corner_radius=6,
        )

        # Row 2: Capítulos + Thumbnail + Metadados + Comentários
        ex_row2 = ctk.CTkFrame(extras_card, fg_color="transparent")
        ex_row2.pack(fill="x", padx=14, pady=(0, 10))

        self._chaps_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ex_row2, text="Capítulos", variable=self._chaps_var,
            fg_color=ACCENT, hover_color=ACCENT, border_color=BORDER,
            command=self._update_dl_btn,
        ).pack(side="left", padx=(0, 14))

        self._thumb_dl_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ex_row2, text="Thumbnail", variable=self._thumb_dl_var,
            fg_color=ACCENT, hover_color=ACCENT, border_color=BORDER,
            command=self._update_dl_btn,
        ).pack(side="left", padx=(0, 14))

        self._meta_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ex_row2, text="Metadados", variable=self._meta_var,
            fg_color=ACCENT, hover_color=ACCENT, border_color=BORDER,
            command=self._update_dl_btn,
        ).pack(side="left", padx=(0, 14))

        self._comments_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ex_row2, text="Comentários", variable=self._comments_var,
            fg_color=ACCENT, hover_color=ACCENT, border_color=BORDER,
            command=self._update_dl_btn,
        ).pack(side="left")

        # Folder
        ctk.CTkLabel(
            self._frame_result, text="Pasta de destino",
            text_color=TEXT_SOFT, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=6, pady=(0, 4))

        folder_row = ctk.CTkFrame(self._frame_result, fg_color="transparent")
        folder_row.pack(fill="x", padx=4, pady=(0, 8))
        folder_row.columnconfigure(0, weight=1)

        self._folder_entry = ctk.CTkEntry(
            folder_row, height=36, fg_color=BG_ELEV_2, border_color=BORDER,
            border_width=1, text_color=TEXT, corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._folder_entry.insert(0, self._download_path)
        self._folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            folder_row, text="Trocar", width=72, height=36,
            fg_color=BG_ELEV_2, hover_color=BG_ELEV_2,
            border_width=1, border_color=BORDER,
            text_color=TEXT_SOFT, corner_radius=8, command=self._choose_folder,
        ).grid(row=0, column=1)

        # Error label (hidden by default)
        self._error_lbl = ctk.CTkLabel(
            self._frame_result, text="", text_color=DANGER,
            font=ctk.CTkFont(size=12), wraplength=480, justify="left",
        )

        # Download button
        self._dl_btn = ctk.CTkButton(
            self._frame_result, text="Baixar 1 item", height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT, hover_color="#6344e0",
            text_color=TEXT, corner_radius=10,
            command=self._start_download,
        )
        self._dl_btn.pack(fill="x", padx=4, pady=(4, 12))

    # ── State machine ─────────────────────────────────────────────────────────

    def _go(self, state: str):
        self._state = state
        self._frame_url_bar.pack_forget()
        self._frame_empty.pack_forget()
        self._frame_analyzing.pack_forget()
        self._frame_result.pack_forget()

        if state == "EMPTY":
            self._frame_empty.pack(fill="both", expand=True)
        elif state == "ANALYZING":
            self._frame_url_bar.pack(fill="x", padx=20, pady=(12, 0))
            self._frame_analyzing.pack(fill="both", expand=True)
            self._tick_spinner()
        elif state == "RESULT":
            self._frame_url_bar.pack(fill="x", padx=20, pady=(12, 0))
            self._frame_result.pack(fill="both", expand=True, padx=16, pady=(4, 0))

    def _tick_spinner(self):
        if self._state != "ANALYZING":
            return
        char = _SPINNER[self._spinner_idx % len(_SPINNER)]
        self._spinner_lbl.configure(text=f"{char}  analisando link...")
        self._spinner_idx += 1
        self.after(120, self._tick_spinner)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _paste_and_analyze(self):
        try:
            url = self.clipboard_get().strip()
            if re.match(r"https?://", url):
                self._analyze(dl.normalize_url(url))
        except Exception:
            pass

    def _use_suggestion(self):
        if self._sugg_url:
            self._analyze(self._sugg_url)

    def _cancel(self):
        self._cancel_event.set()
        self._go("EMPTY")

    def check_clipboard(self):
        if self._state != "EMPTY":
            return
        try:
            text = self.clipboard_get().strip()
            if re.match(r"https?://", text) and text != self._sugg_url:
                self._sugg_url = dl.normalize_url(text)
                truncated = text if len(text) <= 62 else text[:59] + "..."
                self._sugg_btn.configure(text=truncated)
                self._sugg_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        except Exception:
            pass

    def _analyze(self, url: str):
        self._current_url = url
        short = url if len(url) <= 62 else url[:59] + "..."
        self._url_display.configure(text=short)
        self._cancel_event = threading.Event()
        self._go("ANALYZING")

        cancel = self._cancel_event

        def worker():
            try:
                info = dl.extract_info(url)
                if not cancel.is_set():
                    self.after(0, self._on_info, info)
            except Exception as exc:
                if not cancel.is_set():
                    self.after(0, self._on_analyze_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_info(self, info: dict):
        if self._state != "ANALYZING":
            return
        self._info = info

        # Populate info card
        title = info.get("title") or "Sem título"
        platform = dl.get_platform(info)
        uploader = info.get("uploader") or info.get("channel") or ""
        duration = info.get("duration_string") or ""
        meta = " · ".join(filter(None, [platform, uploader, duration]))

        self._title_lbl.configure(text=title)
        self._meta_lbl.configure(text=meta)

        # Quality options
        heights = dl.get_available_heights(info)
        self._quality_menu.configure(values=heights)
        self._quality_var.set(heights[0] if heights else "720p")

        self._go("RESULT")
        self._refresh_preset_menu()
        self._preset_var.set("Nenhum")

        # Subtitle langs from info
        langs = dl.get_subtitle_langs(info)
        if langs:
            opts = list(dict.fromkeys(["pt-BR, en"] + langs[:4]))
            self._subs_lang_menu.configure(values=opts)

        self._update_dl_btn()

        # Thumbnail in background
        thumb_url = info.get("thumbnail")
        if thumb_url and _PIL:
            threading.Thread(target=self._load_thumb, args=(thumb_url,), daemon=True).start()

    def _load_thumb(self, url: str):
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGB").resize((120, 68), Image.LANCZOS)

            def _apply(image=img):
                try:
                    ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=(120, 68))
                    self._thumb_img = ctk_img  # prevent GC
                    self._thumb_lbl.configure(image=ctk_img, text="")
                except Exception:
                    pass

            self.after(0, _apply)
        except Exception:
            pass

    def _on_analyze_error(self, msg: str):
        if self._state != "ANALYZING":
            return
        self._go("RESULT")
        self._info = {}
        self._title_lbl.configure(text="Não foi possível analisar este link")
        self._meta_lbl.configure(text="")
        self._error_lbl.configure(text=msg)
        self._error_lbl.pack(fill="x", padx=4, pady=(0, 6), before=self._dl_btn)
        self._update_dl_btn()

    def _on_subs_toggle(self):
        if self._subs_var.get():
            self._subs_extras.pack(side="left")
            self._on_subs_source_change(self._subs_source_var.get())
        else:
            self._subs_extras.pack_forget()
        self._update_dl_btn()

    def _on_subs_source_change(self, value: str):
        if value == "Whisper ✦":
            self._whisper_model_menu.pack(side="left")
        else:
            self._whisper_model_menu.pack_forget()

    def _refresh_preset_menu(self, select: str | None = None):
        names = ["Nenhum"] + self._presets.names()
        self._preset_menu.configure(values=names)
        if select and select in names:
            self._preset_var.set(select)

    def _apply_preset(self, name: str):
        if name == "Nenhum":
            return
        preset = self._presets.get(name)
        if not preset:
            return
        is_audio = preset.fmt == "MP3"
        self._media_var.set(1 if is_audio else 0)
        if is_audio:
            self._bitrate_var.set(preset.quality)
        else:
            self._quality_var.set(preset.quality)
        self._subs_var.set(preset.subtitles)
        src = getattr(preset, "subtitle_source", "site")
        self._subs_source_var.set("Whisper ✦" if src == "whisper" else "Site")
        self._on_subs_toggle()
        if preset.subtitle_langs:
            lang = preset.subtitle_langs[0]
            cur_vals = list(self._subs_lang_menu.cget("values") or [])
            if lang not in cur_vals:
                self._subs_lang_menu.configure(values=cur_vals + [lang])
            self._subs_lang_var.set(lang)
        self._subs_fmt_var.set(preset.subtitle_fmt or "srt")
        self._whisper_model_var.set(getattr(preset, "whisper_model", "base"))
        self._chaps_var.set(preset.chapters)
        self._thumb_dl_var.set(preset.thumbnail_dl)
        self._meta_var.set(preset.metadata)
        self._comments_var.set(preset.comments)
        self._update_dl_btn()

    def _save_preset(self):
        dialog = ctk.CTkInputDialog(text="Nome do preset:", title="Salvar preset")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()
        is_audio = self._media_var.get() == 1
        is_whisper = self._subs_source_var.get() == "Whisper ✦"
        lang = self._subs_lang_var.get().strip()
        from state.presets import Preset
        preset = Preset(
            name=name,
            fmt="MP3" if is_audio else "MP4",
            quality=self._bitrate_var.get() if is_audio else self._quality_var.get(),
            subtitles=self._subs_var.get(),
            subtitle_source="whisper" if is_whisper else "site",
            subtitle_langs=[lang] if lang else [],
            subtitle_fmt=self._subs_fmt_var.get(),
            whisper_model=self._whisper_model_var.get(),
            chapters=self._chaps_var.get(),
            thumbnail_dl=self._thumb_dl_var.get(),
            metadata=self._meta_var.get(),
            comments=self._comments_var.get(),
        )
        self._presets.save(preset)
        self._refresh_preset_menu(select=name)

    def _update_dl_btn(self):
        extras = sum([
            self._subs_var.get(),
            self._chaps_var.get(),
            self._thumb_dl_var.get(),
            self._meta_var.get(),
            self._comments_var.get(),
        ])
        n = 1 + extras
        label = "item" if n == 1 else "itens"
        self._dl_btn.configure(text=f"Baixar {n} {label}")

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self._folder_entry.get())
        if folder:
            self._folder_entry.delete(0, "end")
            self._folder_entry.insert(0, folder)

    def _start_download(self):
        if not self._info and not self._current_url:
            return

        output_dir = self._folder_entry.get().strip()
        if not os.path.isdir(output_dir):
            from tkinter import messagebox
            messagebox.showerror("Vex", "Pasta de destino não encontrada.")
            return

        is_audio = self._media_var.get() == 1
        sub_source = self._subs_source_var.get()
        is_whisper = sub_source == "Whisper ✦"
        subtitle_langs = [self._subs_lang_var.get().strip()] if self._subs_var.get() else []
        opts = DownloadOptions(
            fmt="MP3" if is_audio else "MP4",
            quality=self._bitrate_var.get() if is_audio else self._quality_var.get(),
            subtitles=self._subs_var.get(),
            subtitle_source="whisper" if is_whisper else "site",
            subtitle_langs=subtitle_langs,
            subtitle_fmt=self._subs_fmt_var.get(),
            whisper_model=self._whisper_model_var.get(),
            chapters=self._chaps_var.get(),
            thumbnail_dl=self._thumb_dl_var.get(),
            metadata=self._meta_var.get(),
            comments=self._comments_var.get(),
        )

        title = (self._info or {}).get("title") or self._current_url
        platform = dl.get_platform(self._info or {}) if self._info else "web"
        thumb_url = (self._info or {}).get("thumbnail")

        job = DownloadJob.new(
            url=self._current_url,
            title=title,
            platform=platform,
            thumbnail_url=thumb_url,
            options=opts,
            output_dir=output_dir,
        )

        if self._on_start_download:
            self._on_start_download(job)

        self._go("EMPTY")
        self._info = None
        self._current_url = ""
        self._thumb_lbl.configure(image=None, text="")
        self._error_lbl.pack_forget()
        self._subs_var.set(False)
        self._subs_source_var.set("Site")
        self._subs_extras.pack_forget()
        self._chaps_var.set(False)
        self._thumb_dl_var.set(False)
        self._meta_var.set(False)
        self._comments_var.set(False)
