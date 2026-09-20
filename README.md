# Session ↔ tdata Converter

Convert Telethon `.session` files and Telegram Desktop `tdata` folders both ways.

**Use only with accounts you own.** Internet is required during conversion.

---

## Easiest way (Windows)

1. Double-click **`RUN.bat`**
2. Choose a direction:
   - **Session → tdata**
   - **tdata → Session**
3. Click **Add…** to pick files/folders, or **Load from sessions/tdatas**
4. Click **Convert**
5. Open the output folder when prompted

That’s it — no need to nest folders by hand.

---

## What the buttons do

| Button | Action |
|--------|--------|
| **Add .session files…** | Pick one or more `.session` files from anywhere |
| **Add tdata folders…** | Pick a Desktop `tdata` folder (or a parent that contains `tdata`) |
| **Load from sessions/** | Queue everything already in `sessions/` |
| **Load from tdatas/** | Queue everything already in `tdatas/` |
| **Convert** | Run the queue; progress bar shows item-by-item status |

After a successful run you can open the output folder from the prompt.

Output:

- Session → tdata → `tdatas/tdataNAME/`
- tdata → Session → `sessions/NAME/NAME.session` **and** `sessions/NAME/NAME.json`

---

## Use tdata in Telegram Desktop

1. Quit Telegram Desktop completely
2. Backup `%APPDATA%\Telegram Desktop\tdata`
3. Copy the **contents** of `tdatas/tdataXXXX` into a new Desktop `tdata` folder
4. Start Telegram Desktop

---

## Optional: CLI

```bash
python main.py                 # all of sessions/ → tdatas/
python tdata_to_session.py     # all of tdatas/ → sessions/
python app.py                  # GUI only (after deps are installed)
```

---

## First-time setup (manual)

`RUN.bat` does this for you. Manual equivalent:

```bash
pip install -r requirements.txt
pip install opentele==1.15.1 --no-deps
pip install "Telethon>=1.36"
```

```powershell
$site = python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
New-Item -ItemType Directory -Force -Path "$site\tgcrypto" | Out-Null
Copy-Item "vendor\tgcrypto\__init__.py" "$site\tgcrypto\__init__.py" -Force
```

> Native `TgCrypto` is skipped on purpose (needs MSVC). This project uses `vendor/tgcrypto`.

---

## Notes

- Session → tdata needs a **logged-in** `.session` (not revoked).
- tdata → Session needs a **full** Desktop `tdata` (`key_datas` + account folder). Quit Telegram Desktop before copying. Local passcode must be off (or conversion cannot decrypt).
- Modern Telegram Desktop tdata is supported via `vendor/opentele_compat.py` (stock opentele alone fails with “No account has been loaded”).

## Requirements

- Windows + Python 3.10+ on PATH
- Internet connection
