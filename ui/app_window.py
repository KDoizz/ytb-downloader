import threading

import customtkinter as ctk

from core import updater
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
        self.geometry("720x620")
        self.minsize(600, 520)
        self.configure(fg_color=BG)

        self._download_url: str | None = None

        self._build_header()
        self._build_update_banner()
        self._build_tabs()

        updater.check_update_async(
            on_new_version=lambda v, url: self.after(0, self._show_update_banner, v, url),
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x", padx=20, pady=(14, 0))
        header.pack_propagate(False)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="y")

        LogoWidget(left, size=34).pack(side="left", padx=(0, 10), pady=10)
        ctk.CTkLabel(
            left,
            text="vex",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT,
        ).pack(side="left", pady=10)

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", fill="y")

        self._check_update_btn = ctk.CTkButton(
            right,
            text="Verificar atualizações",
            width=168,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_FAINT,
            hover_color=BG_ELEV_2,
            font=ctk.CTkFont(size=12),
            corner_radius=8,
            command=self._check_update_manual,
        )
        self._check_update_btn.pack(side="right", pady=12)

    def _build_update_banner(self):
        self._update_banner = ctk.CTkFrame(
            self,
            fg_color="#1a2a1a",
            corner_radius=8,
            border_width=1,
            border_color="#2d4a2d",
        )
        self._update_label = ctk.CTkLabel(
            self._update_banner,
            text="",
            text_color="#90ee90",
            font=ctk.CTkFont(size=13),
        )
        self._update_label.pack(side="left", padx=(14, 8), pady=8)
        ctk.CTkButton(
            self._update_banner,
            text="Instalar",
            width=80,
            height=30,
            fg_color="#22c55e",
            hover_color="#16a34a",
            text_color="white",
            corner_radius=8,
            command=self._start_update,
        ).pack(side="right", padx=(0, 10), pady=8)

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

        NovoView(self._tabview.tab("Novo")).pack(fill="both", expand=True)
        FilaView(self._tabview.tab("Fila")).pack(fill="both", expand=True)
        BibliotecaView(self._tabview.tab("Biblioteca")).pack(fill="both", expand=True)

    def _check_update_manual(self):
        self._check_update_btn.configure(state="disabled", text="Verificando...")

        def on_new(v, url):
            self.after(0, self._show_update_banner, v, url)
            self.after(0, self._reset_update_btn)

        def on_up_to_date():
            self.after(0, self._reset_update_btn)
            from tkinter import messagebox
            self.after(0, lambda: messagebox.showinfo("Vex", "Você já está na versão mais recente!"))

        def on_error():
            self.after(0, self._reset_update_btn)

        updater.check_update_async(
            on_new_version=on_new,
            on_up_to_date=on_up_to_date,
            on_error=on_error,
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

        def on_error():
            pass

        updater.download_and_install(self._download_url, on_done, on_error)
