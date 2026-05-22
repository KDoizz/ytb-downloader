import customtkinter as ctk
from ui.theme import TEXT_SOFT, ACCENT


class BibliotecaView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        ctk.CTkLabel(
            self,
            text="▦",
            font=ctk.CTkFont(size=36),
            text_color=ACCENT,
        ).pack(pady=(48, 8))

        ctk.CTkLabel(
            self,
            text="Biblioteca",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            self,
            text="Em breve — histórico de downloads com thumbnails, filtros por plataforma e acesso rápido aos arquivos.",
            text_color=TEXT_SOFT,
            font=ctk.CTkFont(size=13),
            wraplength=380,
            justify="center",
        ).pack(pady=(8, 0))
