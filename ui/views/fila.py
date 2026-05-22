import customtkinter as ctk
from ui.theme import TEXT_SOFT, TEXT_FAINT, BG_ELEV, BORDER, ACCENT


class FilaView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        ctk.CTkLabel(
            self,
            text="⬇",
            font=ctk.CTkFont(size=36),
            text_color=ACCENT,
        ).pack(pady=(48, 8))

        ctk.CTkLabel(
            self,
            text="Fila de downloads",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            self,
            text="Em breve — múltiplos downloads simultâneos com fila e progresso individual.",
            text_color=TEXT_SOFT,
            font=ctk.CTkFont(size=13),
            wraplength=380,
            justify="center",
        ).pack(pady=(8, 0))
