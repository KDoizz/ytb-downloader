import customtkinter as ctk
from ui.theme import ACCENT, TEXT


class LogoWidget(ctk.CTkFrame):
    """Monogram A — white V on purple rounded block."""

    def __init__(self, parent, size: int = 34, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            fg_color=ACCENT,
            corner_radius=8,
            **kwargs,
        )
        self.pack_propagate(False)
        ctk.CTkLabel(
            self,
            text="V",
            font=ctk.CTkFont(size=int(size * 0.55), weight="bold"),
            text_color=TEXT,
        ).pack(expand=True)
