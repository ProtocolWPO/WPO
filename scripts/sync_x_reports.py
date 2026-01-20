#!/usr/bin/env python3
import os
import json
import re
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode

API = "https://api.x.com/2"


def api_get(path, token, params=None):
    url = API + path
    if params:
        url += "?" + urlencode(params, doseq=True)

    req = Request(url)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("User-Agent", "WPO-GH-Sync/1.0")

    with urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def iso_date(created_at):
    # X API returns ISO 8601 timestamps like 2023-01-01T12:34:56.000Z
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return ""


def detect_risk(text):
    t = (text or "").lower()
    if "#high" in t or "[high]" in t or "high risk" in t:
        return "high"
    if "#medium" in t or "[medium]" in t or "medium risk" in t:
        return "medium"
    return "info"


def extract_lines(text):
    # Normalize newlines and trim
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n")]
    # Drop empty tails
    while lines and not lines[-1]:
        lines.pop()
    return lines


def parse_post_to_report(username, post):
    post_id = post.get("id")
    # For long posts, X may return extended text inside note_tweet.text
    raw_text = (post.get("note_tweet") or {}).get("text") or post.get("text", "")
    created_at = post.get("created_at", "")
    risk = detect_risk(raw_text)

    # Remove the filter tag from display
    filter_tag = os.getenv("X_FILTER", "#WPO_REPORT")
    display_text = (raw_text or "").replace(filter_tag, "").strip()

    lines = extract_lines(display_text)
    title = lines[0] if lines else "Update"

    # Optional structured fields
    status_en = "Published • Source: X"
    evidence_en = "Evidence: See linked post"

    # Parse lines like "Status: ..." or "Evidence: ..."
    for ln in lines[1:]:
        m = re.match(r"^(status|evidence)\s*:\s*(.+)$", ln, flags=re.IGNORECASE)
        if not m:
            continue
        key = m.group(1).lower()
        val = m.group(2).strip()
        if key == "status" and val:
            status_en = val
        if key == "evidence" and val:
            evidence_en = val

    link = f"https://x.com/{username}/status/{post_id}" if post_id else f"https://x.com/{username}"

    return {
        "id": post_id or "",
        "title_en": title,
        "title_ar": "",
        "status_en": status_en,
        "status_ar": "",
        "evidence_en": evidence_en,
        "evidence_ar": "",
        "risk": risk,
        "date": iso_date(created_at),
        "link": link
    }


def main():
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    username = os.getenv("X_USERNAME", "").strip().lstrip("@")
    if not token or not username:
        print("Missing X_BEARER_TOKEN or X_USERNAME", file=sys.stderr)
        return 2

    filter_tag = os.getenv("X_FILTER", "#WPO_REPORT")
    try:
        max_results = int(os.getenv("X_MAX_RESULTS", "30"))
    except Exception:
        max_results = 30

    max_results = max(5, min(100, max_results))

    # 1) Get user id by username
    user = api_get(f"/users/by/username/{username}", token)
    user_id = (user.get("data") or {}).get("id")
    if not user_id:
        print("Could not resolve user id", file=sys.stderr)
        return 3

    # 2) Get posts for user id
    posts = api_get(
        f"/users/{user_id}/tweets",
        token,
        params={
            "max_results": max_results,
            "exclude": ["replies", "retweets"],
            "tweet.fields": ["created_at", "public_metrics", "note_tweet"],
        },
    )

    data = posts.get("data") or []

    # Filter posts by marker
    def _post_text(pp):
        return ((pp.get("note_tweet") or {}).get("text") or pp.get("text") or "")

    filtered = [p for p in data if filter_tag in _post_text(p)]

    # Convert to reports
    reports = [parse_post_to_report(username, p) for p in filtered]

    out_path = os.getenv("OUTPUT_PATH", "reports.json")
    payload = {
        "source": f"X:@{username}",
        "filter": filter_tag,
        "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "reports": reports,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(reports)} reports to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
