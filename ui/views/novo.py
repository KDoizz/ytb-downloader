import os
import re
import sys
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

import core.downloader as dl
from ui.theme import (
    ACCENT, BG_ELEV, BG_ELEV_2, BORDER,
    TEXT, TEXT_SOFT, TEXT_FAINT,
    SUCCESS, WARNING, DANGER,
)


class NovoView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._is_downloading = False
        self._download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self._build()
        self._init_ffmpeg()

    def _build(self):
        ctk.CTkLabel(
            self,
            text="Link do vídeo / mídia",
            text_color=TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=20, pady=(16, 4))

        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.pack(fill="x", padx=20)
        url_row.columnconfigure(0, weight=1)

        self._url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="https://youtube.com/... twitter.com/... instagram.com/...",
            height=42,
            fg_color=BG_ELEV_2,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            placeholder_text_color=TEXT_FAINT,
            corner_radius=8,
        )
        self._url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            url_row,
            text="Colar",
            width=72,
            height=42,
            fg_color=BG_ELEV_2,
            hover_color=BG_ELEV_2,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SOFT,
            corner_radius=8,
            command=self._paste_url,
        ).grid(row=0, column=1)

        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=20, pady=(14, 0))
        opts.columnconfigure(0, weight=1)
        opts.columnconfigure(1, weight=1)

        fmt_box = ctk.CTkFrame(
            opts, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        fmt_box.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        ctk.CTkLabel(
            fmt_box, text="Formato",
            text_color=TEXT_SOFT, font=ctk.CTkFont(size=12),
        ).pack(pady=(10, 4))
        self._format_var = ctk.StringVar(value="MP4")
        ctk.CTkSegmentedButton(
            fmt_box,
            values=["MP4", "MP3"],
            variable=self._format_var,
            command=self._on_format_change,
            fg_color=BG_ELEV_2,
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=BG_ELEV_2,
            unselected_hover_color=BG_ELEV_2,
            text_color=TEXT,
            corner_radius=8,
        ).pack(padx=12, pady=(0, 10))

        qual_box = ctk.CTkFrame(
            opts, fg_color=BG_ELEV, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        qual_box.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        ctk.CTkLabel(
            qual_box, text="Qualidade",
            text_color=TEXT_SOFT, font=ctk.CTkFont(size=12),
        ).pack(pady=(10, 4))
        self._quality_var = ctk.StringVar(value="720p")
        self._quality_menu = ctk.CTkOptionMenu(
            qual_box,
            variable=self._quality_var,
            values=["1080p", "720p", "480p", "360p", "240p"],
            width=140,
            fg_color=BG_ELEV_2,
            button_color=ACCENT,
            button_hover_color=ACCENT,
            text_color=TEXT,
            corner_radius=8,
        )
        self._quality_menu.pack(padx=12, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Pasta de destino",
            text_color=TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=20, pady=(14, 4))

        folder_row = ctk.CTkFrame(self, fg_color="transparent")
        folder_row.pack(fill="x", padx=20)
        folder_row.columnconfigure(0, weight=1)

        self._folder_entry = ctk.CTkEntry(
            folder_row,
            height=42,
            fg_color=BG_ELEV_2,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._folder_entry.insert(0, self._download_path)
        self._folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            folder_row,
            text="Buscar",
            width=72,
            height=42,
            fg_color=BG_ELEV_2,
            hover_color=BG_ELEV_2,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SOFT,
            corner_radius=8,
            command=self._choose_folder,
        ).grid(row=0, column=1)

        self._download_btn = ctk.CTkButton(
            self,
            text="Baixar",
            height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT,
            hover_color="#6344e0",
            text_color=TEXT,
            corner_radius=10,
            command=self._start_download,
        )
        self._download_btn.pack(fill="x", padx=20, pady=(20, 10))

        self._progress = ctk.CTkProgressBar(
            self,
            progress_color=ACCENT,
            fg_color=BG_ELEV_2,
            corner_radius=4,
            height=6,
        )
        self._progress.pack(fill="x", padx=20)
        self._progress.set(0)

        self._status = ctk.CTkLabel(
            self,
            text="Pronto para baixar",
            text_color=TEXT_FAINT,
            font=ctk.CTkFont(size=12),
        )
        self._status.pack(pady=(8, 4))

    def _init_ffmpeg(self):
        if getattr(sys, "frozen", False):
            return
        if not dl.BIN_FFMPEG.is_file():
            self._set_status("Configurando ffmpeg...", TEXT_FAINT)
            threading.Thread(target=self._ffmpeg_setup_worker, daemon=True).start()

    def _ffmpeg_setup_worker(self):
        ok = dl.setup_local_ffmpeg()
        if ok:
            dl.FFMPEG_PATH = str(dl.BIN_FFMPEG)
            dl.FFMPEG_AVAILABLE = True
            self.after(0, self._set_status, "Pronto para baixar", TEXT_FAINT)
        else:
            self.after(0, self._set_status, "ffmpeg não encontrado — MP3 indisponível", WARNING)

    def _set_status(self, text: str, color: str = TEXT_FAINT):
        self._status.configure(text=text, text_color=color)

    def _paste_url(self):
        try:
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, self.clipboard_get())
        except Exception:
            pass

    def _on_format_change(self, value: str):
        if value == "MP3":
            self._quality_menu.configure(values=["320kbps", "192kbps", "128kbps", "64kbps"])
            self._quality_var.set("192kbps")
        else:
            self._quality_menu.configure(values=["1080p", "720p", "480p", "360p", "240p"])
            self._quality_var.set("720p")

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self._folder_entry.get())
        if folder:
            self._folder_entry.delete(0, "end")
            self._folder_entry.insert(0, folder)

    def _validate(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showerror("Vex", "Insira o link do vídeo.")
            return None
        if not re.match(r"https?://", url):
            messagebox.showerror("Vex", "Link inválido. Insira uma URL válida (https://...).")
            return None
        url = dl.normalize_url(url)
        if self._format_var.get() == "MP3" and not dl.FFMPEG_AVAILABLE:
            messagebox.showerror("Vex", "ffmpeg não está disponível. Tente reiniciar o app.")
            return None
        output_dir = self._folder_entry.get().strip()
        if not os.path.isdir(output_dir):
            messagebox.showerror("Vex", "Pasta de destino não encontrada.")
            return None
        return url, output_dir

    def _start_download(self):
        if self._is_downloading:
            return
        result = self._validate()
        if result is None:
            return

        url, output_dir = result
        self._is_downloading = True
        self._download_btn.configure(state="disabled", text="Baixando...")
        self._progress.set(0)
        self._set_status("Iniciando...")

        def on_progress(pct: float):
            self.after(0, self._progress.set, pct)
            self.after(0, self._set_status, f"Baixando... {pct * 100:.1f}%", TEXT_SOFT)

        def on_processing():
            self.after(0, self._progress.set, 1.0)
            self.after(0, self._set_status, "Processando arquivo...", TEXT_SOFT)

        def on_done():
            self.after(0, self._finish, True, None)

        def on_error(msg: str):
            self.after(0, self._finish, False, msg)

        threading.Thread(
            target=dl.download,
            args=(url, output_dir, self._format_var.get(), self._quality_var.get(),
                  on_progress, on_processing, on_done, on_error),
            daemon=True,
        ).start()

    def _finish(self, success: bool, error: str | None):
        self._is_downloading = False
        self._download_btn.configure(state="normal", text="Baixar")
        if success:
            self._progress.set(1.0)
            self._set_status("Download concluído!", SUCCESS)
            messagebox.showinfo("Vex", "Download concluído com sucesso!")
            self._progress.set(0)
            self._set_status("Pronto para baixar")
        else:
            self._progress.set(0)
            self._set_status("Erro no download", DANGER)
            messagebox.showerror("Vex", f"Falha no download:\n\n{error}")
