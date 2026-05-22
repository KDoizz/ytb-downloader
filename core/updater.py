import json
import subprocess
import tempfile
import threading
import urllib.request
from typing import Callable

from version import __version__, GITHUB_REPO


def check_update(
    on_new_version: Callable[[str, str | None], None],
    on_up_to_date: Callable[[], None] | None = None,
    on_error: Callable[[], None] | None = None,
):
    try:
        api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(api, headers={"User-Agent": "vex-downloader"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        latest = data["tag_name"].lstrip("v")
        download_url = next(
            (
                a["browser_download_url"]
                for a in data.get("assets", [])
                if a["name"].endswith("Setup.exe")
            ),
            None,
        )
        if latest != __version__:
            on_new_version(latest, download_url)
        elif on_up_to_date:
            on_up_to_date()
    except Exception:
        if on_error:
            on_error()


def check_update_async(
    on_new_version: Callable[[str, str | None], None],
    on_up_to_date: Callable[[], None] | None = None,
    on_error: Callable[[], None] | None = None,
):
    threading.Thread(
        target=check_update,
        args=(on_new_version, on_up_to_date, on_error),
        daemon=True,
    ).start()


def download_and_install(
    download_url: str,
    on_done: Callable[[], None],
    on_error: Callable[[], None],
):
    def _run():
        try:
            tmp = tempfile.mktemp(suffix="_setup.exe")
            urllib.request.urlretrieve(download_url, tmp)
            subprocess.Popen([tmp, "/SILENT"])
            on_done()
        except Exception:
            on_error()

    threading.Thread(target=_run, daemon=True).start()
