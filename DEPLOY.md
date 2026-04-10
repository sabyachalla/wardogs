# War Dogs — Deploy in 15 minutes, for free

## What you need
- GitHub account (free) → github.com
- Google AI Studio account (free) → aistudio.google.com

---

## Step 1 — Get your free Gemini API key (2 min)

1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click **Get API key** → **Create API key**
4. Copy the key (looks like: `AIzaSy...`)

---

## Step 2 — Create GitHub repo and upload files (5 min)

1. Go to https://github.com/new
2. Name it `wardogs` (or anything you like)
3. Make it **Public** (required for free GitHub Pages)
4. Click **Create repository**
5. Upload all the files from this folder:
   - `index.html`
   - `events.json`
   - `ledger.json`
   - `wallet.json`
   - `scripts/refresh.py`
   - `.github/workflows/refresh.yml`

   **Easiest way:** drag and drop all files onto the GitHub repo page, commit directly.

---

## Step 3 — Add your Gemini API key as a secret (2 min)

1. In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GEMINI_API_KEY`
4. Value: paste your key from Step 1
5. Click **Add secret**

---

## Step 4 — Enable GitHub Pages (2 min)

1. In your repo, go to **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main` / Folder: `/ (root)`
4. Click **Save**

After ~60 seconds, GitHub will show your URL:
**`https://YOUR-USERNAME.github.io/wardogs`**

That's it. Send that link to your friends.

---

## How the refresh works

Every hour, GitHub Actions automatically:
1. Fetches headlines from Reuters, Yahoo Finance, and Google News RSS feeds (all free)
2. Sends them to Google Gemini Flash (free: 1,500 requests/day — you'll use ~24/day)
3. Gemini analyzes headlines and returns updated investment signals
4. `events.json` is updated in the repo
5. GitHub Pages serves the new version instantly

**Cost: $0/month.** Free forever unless you exceed 1,500 Gemini requests/day.

---

## To trigger a manual refresh anytime

1. Go to your repo on GitHub
2. Click **Actions** → **Refresh War Dogs Signals**
3. Click **Run workflow** → **Run workflow**

---

## Optional: custom domain (e.g. wardogs.app)

If you want `wardogs.app` instead of `yourname.github.io/wardogs`:
1. Buy a domain (~$10/year on Namecheap or Google Domains)
2. In GitHub Pages settings, add your custom domain
3. Done — GitHub handles SSL automatically

---

## File structure

```
wardogs/
├── index.html              ← The app (single file, no build needed)
├── events.json             ← Live signals (updated hourly by bot)
├── ledger.json             ← Historical closed trades (update manually)
├── wallet.json             ← Wallet positions (update manually)
├── scripts/
│   └── refresh.py          ← The AI refresh script
└── .github/
    └── workflows/
        └── refresh.yml     ← GitHub Actions cron job
```

## Updating the Ledger manually

When you close a signal (event expires), move it from events.json to ledger.json:
1. Edit `ledger.json` on GitHub directly (pencil icon)
2. Add the closed trade with its actual outcome
3. Commit — the site updates in seconds
