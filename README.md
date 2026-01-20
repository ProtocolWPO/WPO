# Whale Protocol Official — GitHub Pages (Ready Deploy)

## 1) Upload
Upload these files to your GitHub repository (root folder):
- index.html
- app.js
- reports.json
- logo.svg (replace with your logo)
- favicon.svg
- og.png (share preview)

## 2) Enable GitHub Pages
Repository **Settings** → **Pages** →
- Source: **Deploy from a branch**
- Branch: **main**
- Folder: **/** (root)

Your site will be available at:
`https://USERNAME.github.io/REPO/`

## 3) Publish / Update reports
Edit `reports.json` and commit.

## Notes
- The report form uses `mailto:` (opens the visitor's email client).
- Basic anti-abuse: honeypot + 30s cooldown + requires (address OR evidence link).

## Auto-sync Published Reports from X (hashtags)

This site can auto-update **Published Reports** from the official X account.

### What gets pulled?
Only posts that include this hashtag:
- `#WPO_REPORT`

### Setup (GitHub Pages + Actions)
1) In your repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `X_BEARER_TOKEN`
   - Value: your X API v2 Bearer Token

2) The workflow file is already included:
   - `.github/workflows/sync-x-reports.yml`

3) The sync script is included:
   - `scripts/sync_x_reports.py`

4) Make a post on X like this:

```
Alert #004 — Suspicious Wallet Cluster [HIGH]
Status: Under Review
Evidence: https://etherscan.io/tx/... , https://...
#WPO_REPORT
```

Within ~1 hour (or manually via **Actions → Sync X Reports → Run workflow**), the site will update `reports.json` and the cards will appear automatically.

> Note: X API access/limits depend on your plan.
