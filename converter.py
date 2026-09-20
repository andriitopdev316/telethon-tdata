"""Core session ↔ tdata conversion helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from opentele.api import API, UseCurrentSession
from opentele.td import TDesktop
from opentele.tl import TelegramClient

ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = ROOT / "sessions"
TDATAS_DIR = ROOT / "tdatas"

LogFn = Callable[[str], None]


def ensure_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    TDATAS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_flat_sessions(sessions_dir: Path = SESSIONS_DIR) -> List[str]:
    """Move sessions/NAME.session -> sessions/NAME/NAME.session. Returns moved names."""
    ensure_dirs()
    moved: List[str] = []
    for path in list(sessions_dir.glob("*.session")):
        name = path.stem
        dest_dir = sessions_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{name}.session"
        if path.resolve() != dest.resolve():
            if dest.exists():
                path.unlink()
            else:
                shutil.move(str(path), str(dest))
            moved.append(name)
    return moved


def discover_session_names(sessions_dir: Path = SESSIONS_DIR) -> List[str]:
    normalize_flat_sessions(sessions_dir)
    names: List[str] = []
    if not sessions_dir.is_dir():
        return names
    for entry in sorted(sessions_dir.iterdir()):
        if not entry.is_dir():
            continue
        session_file = entry / f"{entry.name}.session"
        if session_file.is_file():
            names.append(entry.name)
            continue
        # Allow any .session inside the folder
        matches = list(entry.glob("*.session"))
        if matches:
            names.append(entry.name)
    return names


def discover_tdata_folders(tdatas_dir: Path = TDATAS_DIR) -> List[Path]:
    if not tdatas_dir.is_dir():
        return []
    return sorted([p for p in tdatas_dir.iterdir() if p.is_dir()])


def session_name_from_tdata_folder(folder_name: str) -> str:
    if folder_name.lower().startswith("tdata") and len(folder_name) > 5:
        return folder_name[5:]
    return folder_name


def resolve_tdata_path(tdata_dir: Path) -> Path:
    nested = tdata_dir / "tdata"
    if nested.is_dir():
        return nested
    return tdata_dir


def import_session_file(src: Path, sessions_dir: Path = SESSIONS_DIR) -> str:
    """Copy a .session file into sessions/NAME/NAME.session. Returns NAME."""
    ensure_dirs()
    src = Path(src)
    if not src.is_file() or src.suffix.lower() != ".session":
        raise ValueError(f"Not a .session file: {src}")
    name = src.stem
    dest_dir = sessions_dir / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}.session"
    if src.resolve() != dest.resolve():
        shutil.copy2(str(src), str(dest))
    return name


def import_tdata_folder(src: Path, tdatas_dir: Path = TDATAS_DIR) -> str:
    """
    Copy a tdata folder into tdatas/<name>/.
    Accepts a folder named tdata, a parent that contains tdata/, or a full tdata tree.
    Returns the destination folder name under tdatas/.
    """
    ensure_dirs()
    src = Path(src)
    if not src.is_dir():
        raise ValueError(f"Not a folder: {src}")

    if src.name.lower() == "tdata":
        label = src.parent.name or "account"
        resolved = src
    elif (src / "tdata").is_dir():
        label = src.name
        resolved = src / "tdata"
    else:
        label = src.name
        resolved = src

    name = label if label.lower().startswith("tdata") else f"tdata{label}"
    if name.lower() == "tdata":
        name = "tdata_account"

    dest = tdatas_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(resolved, dest)
    return name


def _find_session_file(session_name: str, sessions_dir: Path = SESSIONS_DIR) -> Path:
    preferred = sessions_dir / session_name / f"{session_name}.session"
    if preferred.is_file():
        return preferred
    folder = sessions_dir / session_name
    matches = list(folder.glob("*.session"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"No .session file for {session_name}")


async def session_to_tdata(session_name: str, log: Optional[LogFn] = None) -> Path:
    ensure_dirs()
    log = log or (lambda _m: None)
    session_path = _find_session_file(session_name)
    out_name = session_name.split(".")[0]
    out_dir = TDATAS_DIR / f"tdata{out_name}"

    log(f"Converting session -> tdata: {session_name}")
    api = API.TelegramDesktop.Generate()
    client = TelegramClient(str(session_path), api)
    tdesk = await client.ToTDesktop(flag=UseCurrentSession, api=api)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tdesk.SaveTData(str(out_dir))
    log(f"Saved {out_dir}")
    return out_dir


async def tdata_to_session(folder_name: str, log: Optional[LogFn] = None) -> Path:
    ensure_dirs()
    log = log or (lambda _m: None)
    tdata_root = TDATAS_DIR / folder_name
    tdata_path = resolve_tdata_path(tdata_root)
    name = session_name_from_tdata_folder(folder_name)

    log(f"Converting tdata -> session: {folder_name}")
    tdesk = TDesktop(str(tdata_path), api=API.TelegramDesktop)
    if not tdesk.isLoaded():
        raise RuntimeError(
            f"Failed to load tdata at {tdata_path} (empty, locked, or wrong passcode)"
        )

    out_dir = SESSIONS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    session_path = out_dir / f"{name}.session"
    if session_path.exists():
        session_path.unlink()

    client = await tdesk.ToTelethon(
        session=str(session_path),
        flag=UseCurrentSession,
        api=API.TelegramDesktop,
    )
    try:
        await client.connect()
        me = await client.get_me()
        if me:
            log(f"Saved {session_path} (user_id={me.id})")
        else:
            log(f"Saved {session_path}")
    finally:
        await client.disconnect()
    return session_path


async def convert_sessions(
    names: Iterable[str],
    log: Optional[LogFn] = None,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    ok: List[str] = []
    failed: List[Tuple[str, str]] = []
    log = log or (lambda _m: None)
    for name in names:
        try:
            await session_to_tdata(name, log=log)
            ok.append(name)
        except Exception as exc:  # noqa: BLE001 - surface any conversion error to UI
            failed.append((name, str(exc)))
            log(f"ERROR {name}: {exc}")
    return ok, failed


async def convert_tdatas(
    folder_names: Iterable[str],
    log: Optional[LogFn] = None,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    ok: List[str] = []
    failed: List[Tuple[str, str]] = []
    log = log or (lambda _m: None)
    for name in folder_names:
        try:
            await tdata_to_session(name, log=log)
            ok.append(name)
        except Exception as exc:  # noqa: BLE001
            failed.append((name, str(exc)))
            log(f"ERROR {name}: {exc}")
    return ok, failed


def run_async(coro):
    return asyncio.run(coro)
