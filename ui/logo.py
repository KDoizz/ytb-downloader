import sys
from pathlib import Path

import customtkinter as ctk
from PIL import Image


def _asset(name: str) -> Path:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent  # type: ignore[attr-defined]
    return base / "assets" / name


class LogoWidget(ctk.CTkLabel):
    def __init__(self, parent, size: int = 34, **kwargs):
        img = Image.open(_asset("logo.png"))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        super().__init__(parent, image=ctk_img, text="", fg_color="transparent", **kwargs)
        self._img_ref = ctk_img  # prevent garbage collection
