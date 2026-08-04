# Deploying Heavenly Dao on Wispbyte (Free 24/7)

This guide gets the Heavenly Dao Engine running 24/7 on **wispbyte** — a free,
always-on container host that needs **no credit card** and supports Python
Discord bots out of the box. Total setup time: ~30 minutes.

> **Why wispbyte works for this bot:**
> - **Always-on** — containers never sleep (unlike Render/Replit free tiers),
>   so the Discord websocket stays connected 24/7.
> - **Persistent disk (~1 GB free)** — the SQLite database file
>   (`heavenly_dao.db`) survives restarts.
> - **Free tier fits** — ~512 MB RAM / ~35% CPU is plenty: the bot idles at
>   100–200 MB even with 700 members and Groq calls.
> - **No card required** — sign up with just an email.
>
> **⚠️ The one rule you MUST respect:** log into the wispbyte panel at least
> **once every 14 days**, or the server is flagged inactive and **purged**.
> Set a phone reminder now. The code survives (it's on GitHub), but the player
> database would not — so also follow the backup section below.

---

## 0. What you need before starting

| Item | Where to get it |
|---|---|
| The code | Already on GitHub: `https://github.com/rifasziaudeen-prog/Project-Heavenly-Dao-DC` |
| Discord bot token | https://discord.com/developers/applications → your app → **Bot** → *Reset Token* |
| Message Content Intent | Discord Developer Portal → **Bot** → *Privileged Gateway Intents* → enable **MESSAGE CONTENT INTENT** (required for passive Qi from chat) |
| Your server ID | Discord → Settings → *Advanced* → enable **Developer Mode** → right-click your server → *Copy Server ID* |
| Groq key *(optional)* | https://console.groq.com/keys (free tier) |

---

## 1. Create the server on wispbyte

1. Go to **https://wispbyte.com** → **Sign up** (email only, no card).
2. Log into the client panel → **Create Server** (or **Deploy**).
3. Configure:
   - **Application type:** **Python** (wispbyte pre-builds a Python runtime image).
   - **Version:** **3.11 or 3.12** (any 3.10+ works; `requirements.txt` has no
     version pins that conflict).
   - **Plan:** the **free plan** (512 MB RAM / 1 GB disk). Don't add extras.
   - **Name:** `Heavenly-Dao` (or anything you like).
4. Click **Create / Deploy** and wait for the container to finish provisioning.

> If wispbyte asks for a *startup/install command* at this stage, leave it
> blank — we set the exact command in step 4.

---

## 2. Upload the code (SFTP)

The server's working directory is `/home/container/`. Every path below is
relative to that directory. **`run.py` must end up at the root**
(`/home/container/run.py`).

### Via SFTP (recommended)

1. In the wispbyte panel, open your server → **Settings / File Manager** → find
   the **SFTP details** (host, port, username, password).
2. Connect with any SFTP client (**WinSCP**, **FileZilla**, or `sftp` in
   Terminal).
3. Upload the **contents of the repository** so the layout is exactly:

```
/home/container/
├── run.py                  ← must be here
├── requirements.txt
├── .env.example            ← (template, safe to upload)
├── bot/                    (main.py, utils.py)
├── cogs/                   (12 cogs)
├── config/                 (default.py, postgres.py)
├── core/                   (16 modules)
├── db/                     (database.py, queries.py, ...)
├── migrations/             (001–012 SQL)
├── templates/              (JSON narrative templates)
├── scripts/                (setup_discord_server.py, ...)
├── tests/                  (optional on the server)
├── README.md
├── CHANGELOG.md
└── MIGRATION.md
```

4. **Do NOT upload** your local `.env`, `heavenly_dao.db`, or `backups/` —
   those are machine-local and you'll recreate `.env` in the panel (step 3).
   Ignore `.freebuff/` and `.zcode/` — not needed on the server.

> If wispbyte can't do SFTP, the panel's built-in **File Manager** works too —
> create the folders and upload file-by-file. Slower, same result.

---

## 3. Create the `.env` file in the panel

The bot reads its configuration from a `.env` file next to `run.py`
(see `config/default.py` — it calls `load_dotenv` at import). GitHub does not
contain your secrets; **you create the `.env` directly on the server** with the
real values. Use the panel's **File Manager** → navigate to `/home/container/`
→ **New File** → name it `.env` (no extension) → paste and save:

```ini
# --- REQUIRED ---------------------------------------------------------------
DISCORD_TOKEN=YOUR_REAL_BOT_TOKEN_HERE

# --- Optional: Discord ------------------------------------------------------
# Set to your server's numeric ID for INSTANT slash-command sync.
# Leave empty to sync globally (can take ~1 hour to appear).
DEV_GUILD_ID=

# --- Storage & Database -----------------------------------------------------
# Keep sqlite on wispbyte's free tier (zero-cost, persistent disk).
DATABASE_TYPE=sqlite
DATABASE_PATH=heavenly_dao.db
DATABASE_URL=postgresql://user:password@localhost:5432/heavenly_dao   # only if DATABASE_TYPE=postgres
DB_MIN_CONNECTIONS=5
DB_MAX_CONNECTIONS=20

# Daily auto-backups are written here (relative to project root).
BACKUP_DIR=backups

# --- Groq free-tier LLM (OPTIONAL — DISABLED BY DEFAULT) -------------------
# Leave blank to keep the $0 budget — the bot is fully playable with the
# template engine alone. Set to "true" + a real key to enable AI narrative.
GROQ_API_KEY=
ENABLE_GROQ=false

# --- Off-server GitHub backup mirror (RECOMMENDED) --------------------------
# Pushes each daily DB snapshot to a PRIVATE GitHub repo's db-backups branch.
# Fine-grained PAT with "Contents: read and write" on that repo only.
GITHUB_BACKUP_TOKEN=
GITHUB_BACKUP_REPO=yourname/heavenly-dao-backups
GITHUB_BACKUP_BRANCH=db-backups
GITHUB_BACKUP_KEEP=14
```

**Minimal version** — if you're in a hurry, only the first line is mandatory:

```ini
DISCORD_TOKEN=YOUR_REAL_BOT_TOKEN_HERE
```

> **Secrets stay safe:** `.env` is in `.gitignore`, so nothing here can ever be
> pushed to GitHub by accident. If the server is ever purged, only the code is
> lost — never your token's repo history. (Rotate the token if a purge ever
> happens and you're unsure.)

---

## 4. Set the startup command

In the panel, open your server → **Startup** (or **Settings → Startup**) and
set the **Startup Command** to:

```bash
pip install -r requirements.txt && python run.py
```

- `pip install` is idempotent — after the first boot it's a no-op check, so
  it's safe to keep in the command (and it auto-updates deps after future
  code pulls).
- **Alternative:** if wispbyte lets you configure an *install command* separate
  from the *start command*, put `pip install -r requirements.txt` in install
  and `python run.py` in start.

---

## 5. First boot & verification checklist

1. Press **Start** in the panel.
2. Open the **Console** tab and wait ~10–20 seconds. You should see
   `Logged in as ...` (discord.py's startup banner) — not a traceback.
3. On first boot the bot creates `heavenly_dao.db` and applies `migrations/`
   automatically. In the **File Manager** confirm `/home/container/heavenly_dao.db`
   now exists.
4. In your Discord server, run `/help`. If commands don't appear within a
   minute, your `DEV_GUILD_ID` was empty — global sync can take up to an hour.
   (Or restart with `DEV_GUILD_ID` set to sync instantly.)
5. `/register` with a test account → then `/cultivate`. If you see a result
   embed, **the Dao is live.**
6. *(Optional, one-time)* Run the server auto-setup script from the console to
   create all channels/roles and post the welcome guide:

   ```bash
   python scripts/setup_discord_server.py
   ```
   (Requires `DISCORD_TOKEN` and `DEV_GUILD_ID` to be set in `.env` first.)

> **Restarts:** the bot auto-reconnects on transient network drops
> (`run.py` calls `bot.start(..., reconnect=True)`). Restart the server from
> the panel after any code update — the DB persists across restarts.

---

## 6. Daily operations & backups

### 🔑 The 14-day login rule
Log into the wispbyte panel **at least every 14 days** or the free server gets
purged. **Set a recurring phone alarm** — this is the #1 way free servers die.

### 💾 Backing up the player database
The bot writes a daily snapshot into `backups/` **and mirrors it to a private
GitHub repo automatically** (`scripts/github_backup.py`, wired into the daily
backup loop). As long as the four `GITHUB_BACKUP_*` keys are set in `.env`, even
a total server purge loses nothing — code and player snapshots are both on
GitHub. You can also trigger a mirror manually from the console:

```bash
python scripts/github_backup.py
```

> **Security:** the database contains player data. Create a **private** GitHub
> repo for backups and scope the token to it (Settings → Developer settings →
> Personal access tokens → Fine-grained tokens → "Contents: read and write"
> on that repo only).

### 🔄 Updating the bot
1. `git pull` on your PC (or edit on GitHub).
2. Re-upload the changed files via SFTP.
3. **Restart** the server from the panel.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `DISCORD_TOKEN is not set` | `.env` missing or key empty | Recreate `.env` (step 3), restart |
| `ModuleNotFoundError` | `pip install` never ran | Ensure startup command includes `pip install -r requirements.txt`, restart |
| `Login failure: Improper token` | Token wrong or reset | Copy a fresh token from the Dev Portal into `.env` |
| `PrivilegedIntentsRequired` | MESSAGE CONTENT INTENT off | Enable it in the Dev Portal → **Bot** → *Privileged Gateway Intents*, restart |
| No slash commands | Global sync delay | Set `DEV_GUILD_ID` and restart for instant sync |
| Bot stays offline / panel shows stopped | Crashed on boot | Read the last lines of the **Console**; most boot failures are `.env` or intent issues |
| DB resets after redeploy | Files uploaded to wrong dir | Confirm `run.py` is at `/home/container/run.py` (step 2) |

---

## 8. Later: moving to cloud Postgres (optional)

When the server outgrows SQLite (or you build the web dashboard), switch to
free cloud Postgres — the code is already migration-ready:

1. Create a free Postgres at **Neon** or **Supabase** (no card needed).
2. In `.env` set `DATABASE_TYPE=postgres` and `DATABASE_URL=postgresql://...`.
3. Run the migration once: `python scripts/migrate_sqlite_to_postgres.py`
   (see `MIGRATION.md` for the full procedure).
4. Restart. No code changes required.

---

*Generated for the Heavenly Dao Engine v1.1.0 — the Heaven that makes the Earth.*
