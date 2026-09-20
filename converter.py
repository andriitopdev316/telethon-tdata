"""Core session ↔ tdata conversion helpers."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from opentele.api import API, UseCurrentSession
from opentele.td import TDesktop
from opentele.tl import TelegramClient

ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = ROOT / "sessions"
TDATAS_DIR = ROOT / "tdatas"

# Ensure vendor/ is importable for opentele tdata compat shim
_VENDOR = ROOT / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

import opentele_compat

opentele_compat.apply()

LogFn = Callable[[str], None]
# current (0-based completed or in-progress index), total, item name
ProgressFn = Callable[[int, int, str], None]

# Official Telegram Desktop API used for UseCurrentSession conversions
_DESKTOP_API = API.TelegramDesktop
_DESKTOP_API_ID = int(_DESKTOP_API.api_id)
_DESKTOP_API_HASH = str(_DESKTOP_API.api_hash)
# Match common session-json sidecars (opentele's built-in app_version is outdated)
_DESKTOP_APP_VERSION = "6.8.2 x64"
_DESKTOP_DEVICE = "Desktop"
_DESKTOP_SDK = "Windows 11"
_DESKTOP_LANG = "en"
_DESKTOP_SYSTEM_LANG = "en-US"
_DESKTOP_LANG_PACK = "tdesktop"


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
    normalize_flat_sessions(sessions_dir)
    preferred = sessions_dir / session_name / f"{session_name}.session"
    if preferred.is_file():
        return preferred
    folder = sessions_dir / session_name
    matches = list(folder.glob("*.session"))
    if matches:
        return matches[0]
    flat = sessions_dir / f"{session_name}.session"
    if flat.is_file():
        return flat
    raise FileNotFoundError(f"No .session file for {session_name}")


async def session_to_tdata(session_name: str, log: Optional[LogFn] = None) -> Path:
    ensure_dirs()
    log = log or (lambda _m: None)
    session_path = _find_session_file(session_name)
    out_name = session_name.split(".")[0]
    out_dir = TDATAS_DIR / f"tdata{out_name}"

    log(f"Converting session -> tdata: {session_name}")
    # UseCurrentSession must keep a stable official API (do not Generate() a new fingerprint).
    client = TelegramClient(str(session_path), api=API.TelegramDesktop)
    try:
        await client.connect()
        try:
            authorized = await client.is_user_authorized()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Session '{session_name}' cannot connect to Telegram: {exc}"
            ) from exc

        if not authorized:
            raise RuntimeError(
                f"Session '{session_name}' is not logged in "
                "(auth key unregistered, revoked, or login never finished). "
                "Create a fresh .session while logged in, then convert again."
            )

        me = await client.get_me()
        if me is None or me.id is None:
            raise RuntimeError(
                f"Session '{session_name}' did not return a user id. "
                "The session is incomplete or revoked."
            )

        # opentele SaveTData requires a real UserId; set it explicitly.
        client.UserId = int(me.id)
        log(f"Authorized as user_id={me.id}" + (f" phone={me.phone}" if me.phone else ""))

        tdesk = await client.ToTDesktop(
            flag=UseCurrentSession, api=API.TelegramDesktop
        )
        if out_dir.exists():
            shutil.rmtree(out_dir)
        try:
            tdesk.SaveTData(str(out_dir))
        except TypeError as exc:
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            raise RuntimeError(
                f"Failed to write tdata for '{session_name}' "
                f"(missing user id in session). Details: {exc}"
            ) from exc
    finally:
        await client.disconnect()

    log(f"Saved {out_dir}")
    return out_dir


async def tdata_to_session(
    folder_name: str,
    log: Optional[LogFn] = None,
    passcode: str = "",
) -> Path:
    ensure_dirs()
    log = log or (lambda _m: None)
    tdata_root = TDATAS_DIR / folder_name
    tdata_path = resolve_tdata_path(tdata_root)
    name = session_name_from_tdata_folder(folder_name)

    log(f"Converting tdata -> session: {folder_name}")
    try:
        tdesk = TDesktop(
            str(tdata_path),
            api=_DESKTOP_API,
            passcode=passcode or None,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "passcode" in msg.lower() or "password" in msg.lower():
            raise RuntimeError(
                f"tdata '{folder_name}' is locked with a Telegram Desktop "
                "local passcode. Remove the local passcode in Desktop, "
                "re-copy tdata, and try again."
            ) from exc
        if "No account has been loaded" in msg:
            raise RuntimeError(
                f"Could not load any account from '{folder_name}'. "
                "Use a full logged-in tdata folder (with key_datas), "
                "quit Telegram Desktop before copying, and ensure no local passcode."
            ) from exc
        raise RuntimeError(f"Failed to open tdata '{folder_name}': {exc}") from exc

    if not tdesk.isLoaded() or tdesk.accountsCount < 1:
        raise RuntimeError(
            f"Failed to load tdata at {tdata_path} (empty, locked, or wrong passcode)"
        )

    account = tdesk.mainAccount or tdesk.accounts[0]
    payload = _account_to_json_dict(account, session_name=name)

    out_dir = SESSIONS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    session_path = out_dir / f"{name}.session"
    json_path = out_dir / f"{name}.json"
    if session_path.exists():
        session_path.unlink()
    if json_path.exists():
        json_path.unlink()

    client = await tdesk.ToTelethon(
        session=str(session_path),
        flag=UseCurrentSession,
        api=_DESKTOP_API,
    )
    me = None
    try:
        await client.connect()
        try:
            authorized = await client.is_user_authorized()
        except Exception as exc:  # noqa: BLE001
            _cleanup_bad_session(session_path, out_dir)
            raise RuntimeError(
                f"tdata '{folder_name}' auth key was rejected by Telegram: {exc}"
            ) from exc

        if not authorized:
            _cleanup_bad_session(session_path, out_dir)
            raise RuntimeError(
                f"tdata '{folder_name}' is not logged in on Telegram's side "
                "(auth key unregistered or revoked). "
                "In Telegram Desktop: log in again, fully quit the app, "
                "then copy a fresh tdata folder here and convert again. "
                "Do not terminate that device/session after copying."
            )

        me = await client.get_me()
        if me:
            log(f"Saved {session_path} (user_id={me.id})")
        else:
            _cleanup_bad_session(session_path, out_dir)
            raise RuntimeError(
                f"tdata '{folder_name}' did not return a user. "
                "The Desktop session is incomplete or revoked — copy a fresh tdata."
            )
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        _cleanup_bad_session(session_path, out_dir)
        text = str(exc).lower()
        if "authorization key" in text or "unregistered" in text or "doesn't know" in text:
            raise RuntimeError(
                f"tdata '{folder_name}' auth key is unknown to Telegram "
                "(revoked, logged out, or terminated). "
                "Log into Telegram Desktop again, quit completely, "
                "re-copy tdata, then convert. "
                "Avoid 'Terminate other sessions' after copying."
            ) from exc
        raise
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    _enrich_json_from_user(payload, me)
    _write_session_json(json_path, payload)
    log(f"Saved {json_path}")
    return session_path


def _account_to_json_dict(account, session_name: str) -> Dict[str, Any]:
    """Build JSON in the same shape as input/*.json session sidecars."""
    user_id = int(account.UserId) if account.UserId else None
    phone_guess = session_name if session_name.isdigit() else None
    return {
        "phone": phone_guess,
        "app_id": _DESKTOP_API_ID,
        "app_hash": _DESKTOP_API_HASH,
        "session_file": session_name,
        "register_time": int(time.time()),
        "first_name": None,
        "last_name": None,
        "app_version": _DESKTOP_APP_VERSION,
        "device": _DESKTOP_DEVICE,
        "sdk": _DESKTOP_SDK,
        "lang_code": _DESKTOP_LANG,
        "system_lang_code": _DESKTOP_SYSTEM_LANG,
        "lang_pack": _DESKTOP_LANG_PACK,
        "tz_offset_sec": -int(time.timezone if time.daylight == 0 else time.altzone),
        "id": str(user_id) if user_id else None,
        "is_premium": False,
        "twoFA": None,
        "username": None,
    }


def _enrich_json_from_user(payload: Dict[str, Any], me) -> None:
    if me is None:
        return
    payload["id"] = str(int(me.id))
    phone = getattr(me, "phone", None)
    if phone:
        payload["phone"] = str(phone)
    payload["username"] = getattr(me, "username", None)
    payload["first_name"] = getattr(me, "first_name", None)
    payload["last_name"] = getattr(me, "last_name", None)
    payload["is_premium"] = bool(getattr(me, "premium", False))


def _write_session_json(json_path: Path, payload: Dict[str, Any]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep a stable key order matching the reference format
    ordered = {
        "phone": payload.get("phone"),
        "app_id": payload.get("app_id"),
        "app_hash": payload.get("app_hash"),
        "session_file": payload.get("session_file"),
        "register_time": payload.get("register_time"),
        "first_name": payload.get("first_name"),
        "last_name": payload.get("last_name"),
        "app_version": payload.get("app_version"),
        "device": payload.get("device"),
        "sdk": payload.get("sdk"),
        "lang_code": payload.get("lang_code"),
        "system_lang_code": payload.get("system_lang_code"),
        "lang_pack": payload.get("lang_pack"),
        "tz_offset_sec": payload.get("tz_offset_sec"),
        "id": payload.get("id"),
        "is_premium": payload.get("is_premium", False),
        "twoFA": payload.get("twoFA"),
        "username": payload.get("username"),
    }
    json_path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cleanup_bad_session(session_path: Path, out_dir: Path) -> None:
    """Remove session/json files that failed server verification."""
    stem = session_path.with_suffix("")
    for path in (
        session_path,
        Path(str(session_path) + "-journal"),
        stem.with_suffix(".json"),
    ):
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    try:
        if out_dir.is_dir() and not any(out_dir.iterdir()):
            out_dir.rmdir()
    except OSError:
        pass


async def convert_sessions(
    names: Iterable[str],
    log: Optional[LogFn] = None,
    progress: Optional[ProgressFn] = None,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    ok: List[str] = []
    failed: List[Tuple[str, str]] = []
    log = log or (lambda _m: None)
    items = list(names)
    total = len(items)
    for index, name in enumerate(items):
        if progress:
            progress(index, total, name)
        try:
            await session_to_tdata(name, log=log)
            ok.append(name)
        except Exception as exc:  # noqa: BLE001 - surface any conversion error to UI
            failed.append((name, str(exc)))
            log(f"ERROR {name}: {exc}")
    if progress and total:
        progress(total, total, "")
    return ok, failed


async def convert_tdatas(
    folder_names: Iterable[str],
    log: Optional[LogFn] = None,
    progress: Optional[ProgressFn] = None,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    ok: List[str] = []
    failed: List[Tuple[str, str]] = []
    log = log or (lambda _m: None)
    items = list(folder_names)
    total = len(items)
    for index, name in enumerate(items):
        if progress:
            progress(index, total, name)
        try:
            await tdata_to_session(name, log=log)
            ok.append(name)
        except Exception as exc:  # noqa: BLE001
            failed.append((name, str(exc)))
            log(f"ERROR {name}: {exc}")
    if progress and total:
        progress(total, total, "")
    return ok, failed


def run_async(coro):
    return asyncio.run(coro)
