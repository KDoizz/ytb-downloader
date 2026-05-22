import os
import re
import sys
import shutil
from pathlib import Path
from typing import Callable

import yt_dlp


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # core/downloader.py -> core/ -> project root
    return Path(__file__).parent.parent


_ROOT = _project_root()
BIN_DIR = _ROOT / "bin"
BIN_FFMPEG = BIN_DIR / "ffmpeg.exe"
BUNDLED_FFMPEG = (
    Path(sys._MEIPASS) / "bin" / "ffmpeg.exe"  # type: ignore[attr-defined]
    if getattr(sys, "frozen", False)
    else BIN_FFMPEG
)


def resolve_ffmpeg() -> str | None:
    if BIN_FFMPEG.is_file():
        return str(BIN_FFMPEG)
    if BUNDLED_FFMPEG.is_file():
        return str(BUNDLED_FFMPEG)
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def setup_local_ffmpeg() -> bool:
    if getattr(sys, "frozen", False):
        return resolve_ffmpeg() is not None
    if BIN_FFMPEG.is_file():
        return True
    try:
        import imageio_ffmpeg
        BIN_DIR.mkdir(exist_ok=True)
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), str(BIN_FFMPEG))
        return True
    except Exception:
        return False


FFMPEG_PATH: str | None = resolve_ffmpeg()
FFMPEG_AVAILABLE: bool = FFMPEG_PATH is not None

_TEMP_EXT = (".webm", ".m4a", ".part", ".ytdl")
_TEMP_FID = re.compile(r'\.\d+\.(mp4|webm|m4a|mkv|opus|ogg)$')


def normalize_url(url: str) -> str:
    return re.sub(r"^(https?://)(?:www\.)?x\.com/", r"\1twitter.com/", url)


def _cleanup_intermediates(output_dir: str, files_before: set):
    new_files = set(os.listdir(output_dir)) - files_before
    for f in new_files:
        if f.endswith(_TEMP_EXT) or _TEMP_FID.search(f):
            try:
                os.remove(os.path.join(output_dir, f))
            except OSError:
                pass


def _build_opts(
    output_dir: str,
    fmt: str,
    quality: str,
    on_progress: Callable[[float], None],
    on_processing: Callable[[], None],
) -> dict:
    def hook(d: dict):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                on_progress(downloaded / total)
        elif d["status"] == "finished":
            on_processing()

    base: dict = {
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
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": abr,
            }],
        }

    height = quality.replace("p", "")
    if FFMPEG_AVAILABLE:
        fmt_str = (
            f"bestvideo[height<={height}][ext=mp4]"
            f"+bestaudio[ext=m4a]"
            f"/best[height<={height}][ext=mp4]"
            f"/best[height<={height}]"
            f"/best"
        )
    else:
        fmt_str = f"best[height<={height}][ext=mp4]/best[height<={height}]/best"

    return {**base, "format": fmt_str, "merge_output_format": "mp4"}


def download(
    url: str,
    output_dir: str,
    fmt: str,
    quality: str,
    on_progress: Callable[[float], None],
    on_processing: Callable[[], None],
    on_done: Callable[[], None],
    on_error: Callable[[str], None],
):
    files_before = set(os.listdir(output_dir))
    try:
        opts = _build_opts(output_dir, fmt, quality, on_progress, on_processing)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        _cleanup_intermediates(output_dir, files_before)
        on_done()
    except PermissionError:
        # Windows may lock intermediate files after ffmpeg merge — final output was created.
        _cleanup_intermediates(output_dir, files_before)
        on_done()
    except Exception as exc:
        _cleanup_intermediates(output_dir, files_before)
        on_error(str(exc))
