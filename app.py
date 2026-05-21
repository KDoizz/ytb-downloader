import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import yt_dlp
import threading
import os
import re
import shutil
import urllib.request
import json
import webbrowser

from version import __version__, GITHUB_REPO

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# When frozen by PyInstaller, __file__ points inside a temp dir (_MEIPASS).
# The .exe itself lives in a different directory — use sys.executable for that.
def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _bundle_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()
BIN_DIR = os.path.join(APP_DIR, "bin")
BIN_FFMPEG = os.path.join(BIN_DIR, "ffmpeg.exe")
# ffmpeg bundled inside the PyInstaller package
BUNDLED_FFMPEG = os.path.join(_bundle_dir(), "bin", "ffmpeg.exe")


def _resolve_ffmpeg() -> str | None:
    """Return path to ffmpeg.exe. Priority: ./bin > PyInstaller bundle > system PATH > imageio."""
    if os.path.isfile(BIN_FFMPEG):
        return BIN_FFMPEG
    if os.path.isfile(BUNDLED_FFMPEG):
        return BUNDLED_FFMPEG
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _setup_local_ffmpeg() -> bool:
    """Dev mode only: copy ffmpeg from imageio-ffmpeg into ./bin/."""
    if getattr(sys, "frozen", False):
        return FFMPEG_PATH is not None
    if os.path.isfile(BIN_FFMPEG):
        return True
    try:
        import imageio_ffmpeg
        os.makedirs(BIN_DIR, exist_ok=True)
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), BIN_FFMPEG)
        return True
    except Exception:
        return False


FFMPEG_PATH = _resolve_ffmpeg()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None


class YTBDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Vex")
        self.geometry("520x500")
        self.resizable(False, False)

        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.is_downloading = False

        self._build_ui()
        self._init_ffmpeg()
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _init_ffmpeg(self):
        # In frozen mode ffmpeg is bundled inside _internal/bin/ — nothing to copy.
        if getattr(sys, "frozen", False):
            return
        if not os.path.isfile(BIN_FFMPEG):
            self._set_status("Configurando ffmpeg...", "gray")
            threading.Thread(target=self._ffmpeg_setup_worker, daemon=True).start()

    def _ffmpeg_setup_worker(self):
        ok = _setup_local_ffmpeg()
        global FFMPEG_PATH, FFMPEG_AVAILABLE
        if ok:
            FFMPEG_PATH = BIN_FFMPEG
            FFMPEG_AVAILABLE = True
            self.after(0, self._set_status, "Pronto para baixar", "gray")
        else:
            self.after(0, self._set_status, "ffmpeg nao encontrado — MP3 indisponivel", "orange")

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Vex",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(20, 10))

        # Update banner (hidden by default)
        self._update_banner = ctk.CTkFrame(self, fg_color="#2a4a2a", corner_radius=8)
        self._update_label = ctk.CTkLabel(
            self._update_banner, text="", text_color="#90ee90"
        )
        self._update_label.pack(side="left", padx=(12, 8), pady=6)
        ctk.CTkButton(
            self._update_banner,
            text="Baixar",
            width=70,
            height=28,
            fg_color="#4caf50",
            hover_color="#388e3c",
            command=self._start_update,
        ).pack(side="right", padx=(0, 8), pady=6)

        # URL row
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(url_frame, text="Link do vídeo / mídia:").pack(anchor="w")

        row = ctk.CTkFrame(url_frame, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            row,
            placeholder_text="https://youtube.com/... twitter.com/... instagram.com/...",
            height=38,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            row, text="Colar", width=65, height=38, command=self._paste_url
        ).grid(row=0, column=1)

        # Format + Quality row
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=20, pady=10)
        opts.columnconfigure(0, weight=1)
        opts.columnconfigure(1, weight=1)

        fmt_box = ctk.CTkFrame(opts)
        fmt_box.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        ctk.CTkLabel(fmt_box, text="Formato").pack(pady=(8, 4))
        self.format_var = ctk.StringVar(value="MP4")
        ctk.CTkSegmentedButton(
            fmt_box,
            values=["MP4", "MP3"],
            variable=self.format_var,
            command=self._on_format_change,
        ).pack(padx=10, pady=(0, 8))

        qual_box = ctk.CTkFrame(opts)
        qual_box.grid(row=0, column=1, padx=(5, 0), sticky="nsew")
        ctk.CTkLabel(qual_box, text="Qualidade").pack(pady=(8, 4))
        self.quality_var = ctk.StringVar(value="720p")
        self.quality_menu = ctk.CTkOptionMenu(
            qual_box,
            variable=self.quality_var,
            values=["1080p", "720p", "480p", "360p", "240p"],
            width=130,
        )
        self.quality_menu.pack(padx=10, pady=(0, 8))

        # Output folder row
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(folder_frame, text="Pasta de destino:").pack(anchor="w")

        frow = ctk.CTkFrame(folder_frame, fg_color="transparent")
        frow.pack(fill="x")
        frow.columnconfigure(0, weight=1)

        self.folder_entry = ctk.CTkEntry(frow, height=38)
        self.folder_entry.insert(0, self.download_path)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            frow, text="Buscar", width=70, height=38, command=self._choose_folder
        ).grid(row=0, column=1)

        # Download button
        self.download_btn = ctk.CTkButton(
            self,
            text="Baixar",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", padx=20, pady=(15, 8))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20)
        self.progress_bar.set(0)

        # Status label
        self.status_label = ctk.CTkLabel(self, text="Pronto para baixar", text_color="gray")
        self.status_label.pack(pady=(8, 2))

        # Check updates button
        self._check_update_btn = ctk.CTkButton(
            self,
            text="Verificar atualizações",
            width=180,
            height=26,
            fg_color="transparent",
            border_width=1,
            text_color="gray",
            hover_color="#2a2a2a",
            font=ctk.CTkFont(size=12),
            command=self._check_update_manual,
        )
        self._check_update_btn.pack(pady=(0, 12))

    # ── update check ─────────────────────────────────────────────────────────

    def _check_update_manual(self):
        self._check_update_btn.configure(state="disabled", text="Verificando...")
        threading.Thread(target=self._check_update_worker, args=(True,), daemon=True).start()

    def _check_update_worker(self, manual: bool = False):
        try:
            api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(api, headers={"User-Agent": "ytb-downloader"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            latest = data["tag_name"].lstrip("v")
            download_url = next(
                (a["browser_download_url"] for a in data.get("assets", []) if a["name"].endswith("Setup.exe")),
                None,
            )
            if latest != __version__:
                self.after(0, self._show_update_banner, latest, download_url)
            elif manual:
                self.after(0, self._set_status, "Você está na versão mais recente!", "green")
        except Exception:
            if manual:
                self.after(0, self._set_status, "Não foi possível verificar atualizações", "orange")
        finally:
            if manual:
                self.after(0, lambda: self._check_update_btn.configure(state="normal", text="Verificar atualizações"))

    def _show_update_banner(self, latest: str, download_url: str | None):
        self._download_url = download_url
        self._update_label.configure(text=f"Nova versão {latest} disponível")
        self._update_banner.pack(fill="x", padx=20, pady=(0, 8))

    def _start_update(self):
        if not getattr(self, "_download_url", None):
            return
        threading.Thread(target=self._download_and_install, daemon=True).start()

    def _download_and_install(self):
        import tempfile, subprocess
        try:
            tmp = tempfile.mktemp(suffix="_setup.exe")

            def reporthook(count, block_size, total):
                if total > 0:
                    pct = min(count * block_size / total, 1.0)
                    self.after(0, self.progress_bar.set, pct)
                    self.after(0, self._set_status, f"Baixando atualização... {pct * 100:.0f}%")

            urllib.request.urlretrieve(self._download_url, tmp, reporthook=reporthook)
            self.after(0, self._set_status, "Instalando...")
            subprocess.Popen([tmp, "/SILENT"])
            self.after(800, self.quit)
        except Exception:
            self.after(0, self._set_status, "Erro ao baixar atualização", "red")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "gray"):
        self.status_label.configure(text=text, text_color=color)

    def _paste_url(self):
        try:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, self.clipboard_get())
        except Exception:
            pass

    def _on_format_change(self, value):
        if value == "MP3":
            self.quality_menu.configure(values=["320kbps", "192kbps", "128kbps", "64kbps"])
            self.quality_var.set("192kbps")
        else:
            self.quality_menu.configure(values=["1080p", "720p", "480p", "360p", "240p"])
            self.quality_var.set("720p")

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_entry.get())
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _validate_inputs(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Erro", "Por favor, insira o link do vídeo.")
            return None

        if not re.match(r"https?://", url):
            messagebox.showerror("Erro", "Link inválido. Insira uma URL válida (https://...).")
            return None

        if self.format_var.get() == "MP3" and not FFMPEG_AVAILABLE:
            messagebox.showerror("Erro", "ffmpeg não está disponível. Tente reiniciar o app.")
            return None

        output_dir = self.folder_entry.get().strip()
        if not os.path.isdir(output_dir):
            messagebox.showerror("Erro", "Pasta de destino não encontrada.")
            return None

        return url, output_dir

    # ── download ─────────────────────────────────────────────────────────────

    def _start_download(self):
        if self.is_downloading:
            return

        result = self._validate_inputs()
        if result is None:
            return

        url, output_dir = result
        self.is_downloading = True
        self.download_btn.configure(state="disabled", text="Baixando...")
        self.progress_bar.set(0)
        self._set_status("Iniciando...")

        threading.Thread(
            target=self._download_worker, args=(url, output_dir), daemon=True
        ).start()

    def _build_ydl_opts(self, output_dir):
        fmt = self.format_var.get()
        quality = self.quality_var.get()

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    pct = downloaded / total
                    self.after(0, self.progress_bar.set, pct)
                    self.after(0, self._set_status, f"Baixando... {pct * 100:.1f}%")
            elif d["status"] == "finished":
                self.after(0, self.progress_bar.set, 1)
                self.after(0, self._set_status, "Processando arquivo...")

        base = {
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [hook],
            "noplaylist": True,
        }

        if FFMPEG_PATH:
            base["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

        if fmt == "MP3":
            abr = quality.replace("kbps", "")
            return {
                **base,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": abr,
                    }
                ],
            }

        height = quality.replace("p", "")
        if FFMPEG_AVAILABLE:
            fmt_str = (
                f"bestvideo[height<={height}][ext=mp4]"
                f"+bestaudio[ext=m4a]"
                f"/best[height<={height}][ext=mp4]"
                f"/best[height<={height}]"
            )
        else:
            fmt_str = f"best[height<={height}][ext=mp4]/best[height<={height}]"

        return {**base, "format": fmt_str, "merge_output_format": "mp4"}

    def _download_worker(self, url, output_dir):
        files_before = set(os.listdir(output_dir))
        success, error = False, None
        try:
            opts = self._build_ydl_opts(output_dir)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            success = True
        except PermissionError:
            # Windows bloqueia arquivos intermediários após ffmpeg — o output final foi criado.
            success = True
        except Exception as exc:
            error = str(exc)
        finally:
            self._cleanup_intermediates(output_dir, files_before)
        self.after(0, self._on_done, success, error)

    def _cleanup_intermediates(self, output_dir, files_before):
        new_files = set(os.listdir(output_dir)) - files_before
        # Arquivos temporários do yt-dlp: streams com format-ID (title.f137.mp4, title.f140.m4a)
        # e extensões que nunca são output final neste app
        temp_ext = (".webm", ".m4a", ".part", ".ytdl")
        temp_fid = re.compile(r'\.\d+\.(mp4|webm|m4a|mkv|opus|ogg)$')
        for f in new_files:
            if f.endswith(temp_ext) or temp_fid.search(f):
                try:
                    os.remove(os.path.join(output_dir, f))
                except OSError:
                    pass

    def _on_done(self, success, error):
        self.is_downloading = False
        self.download_btn.configure(state="normal", text="Baixar")

        if success:
            self.progress_bar.set(1)
            self._set_status("Download concluído!", "green")
            messagebox.showinfo("Sucesso", "Download concluído com sucesso!")
            self.progress_bar.set(0)
            self._set_status("Pronto para baixar")
        else:
            self.progress_bar.set(0)
            self._set_status("Erro no download", "red")
            messagebox.showerror("Erro", f"Falha no download:\n\n{error}")


if __name__ == "__main__":
    app = YTBDownloader()
    app.mainloop()
