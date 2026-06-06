import os
import re
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Callable

import yt_dlp


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
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


def _needs_recode(filepath: str, ffmpeg: str) -> bool:
    """Returns True unless the video is confirmed H.264 8-bit yuv420p SDR (Twitter/platform compatible)."""
    try:
        r = subprocess.run(
            [ffmpeg, "-i", filepath],
            capture_output=True, text=True, timeout=15,
        )
        info = (r.stdout + r.stderr).lower()
        # Must be H.264, not any HEVC variant
        is_h264 = "h264" in info and not any(x in info for x in ("hevc", "h265", "bytevc", "hvc1"))
        # Must be plain 8-bit yuv420p — yuv420p10le, yuv422p, yuv444p all fail Twitter
        is_8bit_420 = bool(re.search(r"yuv420p(?!\d)", info))
        # Must be SDR — HDR (bt2020/PQ/HLG) fails Twitter even in H.264
        is_sdr = not any(x in info for x in ("bt2020", "smpte2084", "arib-std-b67", "bt.2020", "hlg"))
        return not (is_h264 and is_8bit_420 and is_sdr)
    except Exception:
        return False


def _remux_faststart(filepath: str, ffmpeg: str) -> None:
    """Stream-copy into a faststart MP4 (moov at start). No re-encode — very fast."""
    p = Path(filepath)
    tmp = str(p.with_stem(p.stem + "_fstmp"))
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", tmp],
            check=True, capture_output=True, timeout=120,
        )
        os.replace(tmp, filepath)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _recode_to_h264(filepath: str, ffmpeg: str) -> None:
    """Re-encodes to H.264 8-bit SDR in-place. Raises on failure."""
    p = Path(filepath)
    tmp = str(p.with_stem(p.stem + "_h264tmp"))
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", filepath,
             "-c:v", "libx264", "-crf", "23", "-preset", "fast",
             "-pix_fmt", "yuv420p",         # force 8-bit
             "-colorspace", "bt709",         # force SDR color space metadata
             "-color_primaries", "bt709",
             "-color_trc", "bt709",
             "-c:a", "aac", "-movflags", "+faststart",
             tmp],
            check=True, capture_output=True, timeout=600,
        )
        os.replace(tmp, filepath)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def normalize_url(url: str) -> str:
    return re.sub(r"^(https?://)(?:www\.)?x\.com/", r"\1twitter.com/", url)


def extract_info(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "ignoreerrors": False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False) or {}


def get_available_heights(info: dict) -> list[str]:
    heights: set[int] = set()
    for f in info.get("formats", []):
        h = f.get("height")
        if h and f.get("vcodec", "none") != "none":
            heights.add(h)
    if not heights:
        return ["1080p", "720p", "480p", "360p"]
    return [f"{h}p" for h in sorted(heights, reverse=True)]


def get_subtitle_langs(info: dict) -> list[str]:
    langs: set[str] = set()
    langs.update(info.get("subtitles", {}).keys())
    langs.update(info.get("automatic_captions", {}).keys())
    priority = ["pt", "pt-BR", "pt-br", "en", "es"]
    ordered = [l for l in priority if l in langs]
    for l in sorted(langs):
        if l not in ordered:
            ordered.append(l)
    return ordered[:30]


def get_platform(info: dict) -> str:
    domain = info.get("webpage_url_domain") or info.get("extractor_key", "")
    return domain.replace("www.", "").replace(".com", "").strip() or "web"


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
    extra: dict | None = None,
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

    if extra:
        base.update(extra)

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
            # Prefer H.264 (avc) — avoids H.265/HEVC which breaks most messaging apps
            f"bestvideo[height<={height}][ext=mp4][vcodec^=avc]"
            f"+bestaudio[ext=m4a]"
            f"/bestvideo[height<={height}][ext=mp4]"
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
    extra: dict | None = None,
):
    files_before = set(os.listdir(output_dir))
    try:
        opts = _build_opts(output_dir, fmt, quality, on_progress, on_processing, extra)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        _cleanup_intermediates(output_dir, files_before)

        if FFMPEG_PATH and fmt == "MP4":
            new_files = set(os.listdir(output_dir)) - files_before
            for fname in new_files:
                fp = os.path.join(output_dir, fname)
                if not fname.lower().endswith(".mp4"):
                    continue
                if _needs_recode(fp, FFMPEG_PATH):
                    try:
                        _recode_to_h264(fp, FFMPEG_PATH)
                    except Exception:
                        pass  # keep original if recode fails
                else:
                    # Always remux for faststart even when codecs are fine —
                    # ensures moov atom is at the start (required by Twitter uploader)
                    try:
                        _remux_faststart(fp, FFMPEG_PATH)
                    except Exception:
                        pass

        on_done()
    except PermissionError:
        # Windows may lock intermediate files after ffmpeg merge — final output was created.
        _cleanup_intermediates(output_dir, files_before)
        on_done()
    except Exception as exc:
        _cleanup_intermediates(output_dir, files_before)
        on_error(str(exc))
