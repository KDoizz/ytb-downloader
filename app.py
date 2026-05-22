import customtkinter as ctk
from ui.app_window import VexApp

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

if __name__ == "__main__":
    app = VexApp()
    app.mainloop()
