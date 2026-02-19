# Setup for hourly check

## GitHub Actions

1. In the repo: **Settings → Secrets and variables → Actions**.
2. Add repository secrets:
   - `VIN` — your car’s VIN (e.g. `5TDDK3DC4BS021726`)
   - `PLATE_NUMBER` — your plate (e.g. `Н777ХК190`)
   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHAT_ID` — your Telegram chat ID (e.g. from [@userinfobot](https://t.me/userinfobot))

The workflow runs every hour. If a listing is found, you get a Telegram alert and the run is marked as failed.

## Local run

**One-time setup** (from the repo root):

```powershell
pip install -r requirements.txt
playwright install chromium
```

**Each run** — use a `.env` file, the helper script, or set env manually.

**Option A — .env file (recommended for local):**

1. Copy the example: `copy .env.example .env` (or `cp .env.example .env` on macOS/Linux).
2. Edit `.env` and set your `VIN`, `PLATE_NUMBER`, and optionally `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. Run: `python run_check.py` (no need to set env in the shell; `.env` is loaded automatically and is gitignored).

**Option B — Helper script (Windows PowerShell):**

1. Open `run_local.ps1`, set your `VIN` and `PLATE_NUMBER`.
2. Optionally set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (uncomment the lines).
3. Run:
   ```powershell
   .\run_local.ps1
   ```

**Option C — Manual env (PowerShell):**

```powershell
$env:VIN = "5TDDK3DC4BS021726"
$env:PLATE_NUMBER = "Н777ХК190"
# $env:TELEGRAM_BOT_TOKEN = "..."
# $env:TELEGRAM_CHAT_ID = "..."
python run_check.py
```

**Bash (Linux/macOS):**

```bash
export VIN=5TDDK3DC4BS021726
export PLATE_NUMBER=Н777ХК190
python run_check.py
```

Exit codes: `0` = no listing, `1` = listing found (alert sent), `2` = config error.

**Konfiskat (konfiskat-gov.ru)** may block headless browsers locally. If you see "verification/block page", run with a **visible browser** so the site may allow it: set `HEADLESS=0` in `.env` or run `$env:HEADLESS=0; python run_check.py`. A Chrome window will open briefly. The hourly GitHub Action runs headless and often still reaches Konfiskat (different IP).

## Testing

- **No listing (happy path):** Run with your real VIN/plate; you should see "No listings found" and exit 0.
- **Listing found + Telegram:** Use a VIN that appears on Konfiskat to trigger the alert, e.g.  
  `VIN=KN98H4MDDBCB9K305` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set. You should get a Telegram message and exit 1.
- **CI (full check):** Push the repo and in **Actions** open "Check car listings" → "Run workflow". This runs both Konfiskat and Rosim (Playwright) on Ubuntu; if Playwright fails locally (e.g. Windows), the workflow still validates the full flow.
