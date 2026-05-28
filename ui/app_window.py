import sys
import threading
from pathlib import Path

import customtkinter as ctk

from core import updater
from core.queue_manager import QueueManager
from state.app_state import AppState, DownloadJob
from state.presets import PresetManager
from ui.logo import LogoWidget
from ui.theme import (
    ACCENT, BG, BG_ELEV, BG_ELEV_2, BORDER,
    TEXT, TEXT_SOFT, TEXT_FAINT,
)
from ui.views.novo import NovoView
from ui.views.fila import FilaView
from ui.views.biblioteca import BibliotecaView


class VexApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Vex")
        self.geometry("720x660")
        self.minsize(600, 520)
        self.configure(fg_color=BG)

        self._set_icon()

        self._download_url: str | None = None
        self._state = AppState()
        self._queue = QueueManager(self._state)
        self._presets = PresetManager()

        self._build_header()
        self._build_update_banner()
        self._build_tabs()

        # Auto-detect clipboard when window regains focus
        self.bind("<FocusIn>", self._on_focus_in)

        # Keyboard shortcuts
        self.bind("<Control-Key-1>", lambda e: self._tabview.set("Novo"))
        self.bind("<Control-Key-2>", lambda e: self._tabview.set("Fila"))
        self.bind("<Control-Key-3>", lambda e: self._tabview.set("Biblioteca"))
        self.bind("<Control-n>", lambda e: self._tabview.set("Novo"))
        self.bind("<Control-l>", lambda e: (self._tabview.set("Novo"), self._novo_view._paste_and_analyze()))
        self.bind("<Escape>", self._on_escape)

        updater.check_update_async(
            on_new_version=lambda v, url: self.after(0, self._show_update_banner, v, url),
        )

    # ── Icon ──────────────────────────────────────────────────────────────────

    def _set_icon(self):
        try:
            base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent  # type: ignore[attr-defined]
            ico = base / "assets" / "app.ico"
            if ico.exists():
                # after() ensures the window handle exists before setting the icon
                self.after(100, lambda: self.iconbitmap(str(ico)))
        except Exception:
            pass

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x", padx=20, pady=(14, 0))
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="y")
        LogoWidget(left, size=34).pack(side="left", padx=(0, 10), pady=10)
        ctk.CTkLabel(
            left, text="vex",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT,
        ).pack(side="left", pady=10)

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", fill="y")
        self._check_update_btn = ctk.CTkButton(
            right, text="Verificar atualizações", width=168, height=32,
            fg_color="transparent", border_width=1, border_color=BORDER,
            text_color=TEXT_FAINT, hover_color=BG_ELEV_2,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._check_update_manual,
        )
        self._check_update_btn.pack(side="right", pady=12)

    # ── Update banner ─────────────────────────────────────────────────────────

    def _build_update_banner(self):
        self._update_banner = ctk.CTkFrame(
            self, fg_color="#1a2a1a", corner_radius=8,
            border_width=1, border_color="#2d4a2d",
        )
        self._update_label = ctk.CTkLabel(
            self._update_banner, text="",
            text_color="#90ee90", font=ctk.CTkFont(size=13),
        )
        self._update_label.pack(side="left", padx=(14, 8), pady=8)
        ctk.CTkButton(
            self._update_banner, text="Instalar", width=80, height=30,
            fg_color="#22c55e", hover_color="#16a34a",
            text_color="white", corner_radius=8,
            command=self._start_update,
        ).pack(side="right", padx=(0, 10), pady=8)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabview = ctk.CTkTabview(
            self,
            fg_color=BG,
            segmented_button_fg_color=BG_ELEV,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT,
            segmented_button_unselected_color=BG_ELEV,
            segmented_button_unselected_hover_color=BG_ELEV_2,
            text_color=TEXT_SOFT,
            text_color_disabled=TEXT_FAINT,
            border_width=0,
            corner_radius=10,
        )
        self._tabview.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        self._tabview.add("Novo")
        self._tabview.add("Fila")
        self._tabview.add("Biblioteca")

        self._novo_view = NovoView(
            self._tabview.tab("Novo"),
            on_start_download=self._on_start_download,
            preset_manager=self._presets,
        )
        self._novo_view.pack(fill="both", expand=True)

        FilaView(
            self._tabview.tab("Fila"),
            state=self._state,
            cancel_cb=self._queue.cancel,
        ).pack(fill="both", expand=True)

        BibliotecaView(
            self._tabview.tab("Biblioteca"),
            state=self._state,
        ).pack(fill="both", expand=True)

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _on_start_download(self, job: DownloadJob):
        self._queue.submit(job)
        self._tabview.set("Fila")

    # ── Focus / clipboard ─────────────────────────────────────────────────────

    def _on_focus_in(self, event):
        if event.widget == self:
            self.after(100, self._novo_view.check_clipboard)

    def _on_escape(self, event):
        if self._novo_view._state == "ANALYZING":
            self._novo_view._cancel()

    # ── Update check ──────────────────────────────────────────────────────────

    def _check_update_manual(self):
        self._check_update_btn.configure(state="disabled", text="Verificando...")

        def on_up():
            self.after(0, self._reset_update_btn)
            from tkinter import messagebox
            self.after(0, lambda: messagebox.showinfo("Vex", "Você já está na versão mais recente!"))

        updater.check_update_async(
            on_new_version=lambda v, url: (
                self.after(0, self._show_update_banner, v, url),
                self.after(0, self._reset_update_btn),
            ),
            on_up_to_date=on_up,
            on_error=lambda: self.after(0, self._reset_update_btn),
        )

    def _reset_update_btn(self):
        self._check_update_btn.configure(state="normal", text="Verificar atualizações")

    def _show_update_banner(self, latest: str, download_url: str | None):
        self._download_url = download_url
        self._update_label.configure(text=f"Nova versão {latest} disponível")
        self._update_banner.pack(fill="x", padx=20, pady=(8, 0))

    def _start_update(self):
        if not self._download_url:
            return

        def on_done():
            self.after(800, self.quit)

        updater.download_and_install(self._download_url, on_done, lambda: None)
