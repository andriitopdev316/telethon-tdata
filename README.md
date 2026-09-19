# session_to_tdata

Convert Telethon `.session` files into Telegram Desktop `tdata`.

**Use only with accounts you own.**

---

## Easiest way (Windows) - double-click

1. Put your `.session` file(s) into the `sessions` folder.
2. Double-click **`RUN.bat`**.
3. Wait until the window says **Done**.
4. Find the result in the `tdatas` folder (e.g. `tdatas/tdata12272346391`).

`RUN.bat` installs dependencies, applies the crypto shim (no Visual C++ Build Tools needed), fixes flat session files into the required folder layout, and runs the converter.

---

## Session folder layout

You can drop files flat:

```text
sessions/
  12272346391.session
```

Or use the nested layout the script expects:

```text
sessions/
  12272346391/
    12272346391.session
```

`RUN.bat` converts flat files to nested automatically.

---

## Manual run (optional)

```bash
pip install -r requirements.txt
pip install opentele==1.15.1 --no-deps
pip install "Telethon>=1.36"
```

Copy the shim once:

```powershell
$site = python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
New-Item -ItemType Directory -Force -Path "$site\tgcrypto" | Out-Null
Copy-Item "vendor\tgcrypto\__init__.py" "$site\tgcrypto\__init__.py" -Force
```

Then:

```bash
python main.py
```

> **Note:** Native `TgCrypto` is skipped on purpose. Building it needs Microsoft C++ Build Tools. This project uses `vendor/tgcrypto` instead.

---

## Use the output in Telegram Desktop

1. Fully quit Telegram Desktop.
2. Backup `%APPDATA%\Telegram Desktop\tdata` (rename it to `tdata_backup`).
3. Copy the **contents** of `tdatas/tdataXXXX` into a new `%APPDATA%\Telegram Desktop\tdata` folder.
4. Start Telegram Desktop.

If the session is still valid, Desktop opens already logged in.

---

## Requirements

- Windows + Python 3.10+ on PATH
- Internet (conversion talks to Telegram)
