"""Step 5: the human review queue. Export to CSV -> open in Google Sheets -> import back.

Reviewer fills the 'decision' column with approve or reject, and can edit the
'edited_title' / 'edited_caption' columns to fix wording.
"""
import csv
import json

COLUMNS = [
    "variant_id", "episode_id", "clip_id", "lang", "start", "end", "type",
    "title", "caption", "hashtags", "needs_review", "video_path",
    "decision", "edited_title", "edited_caption",
]


def export_csv(conn, path: str) -> int:
    rows = conn.execute(
        """SELECT v.id AS variant_id, c.episode_id, c.id AS clip_id, v.lang, c.start, c.end, c.type,
                  v.title, v.caption, v.hashtags, v.needs_review, v.video_path
           FROM variants v JOIN clips c ON c.id = v.clip_id
           WHERE v.status = 'pending_review'
           ORDER BY v.needs_review DESC, c.episode_id, c.start, v.lang"""
    ).fetchall()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows Telugu/Hindi
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            d = dict(r)
            d["hashtags"] = " ".join("#" + h for h in json.loads(d["hashtags"]))
            d["decision"] = d["edited_title"] = d["edited_caption"] = ""
            w.writerow(d)
    return len(rows)


def import_csv(conn, path: str) -> dict:
    counts = {"approved": 0, "rejected": 0, "skipped": 0}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            decision = (row.get("decision") or "").strip().lower()
            if decision not in ("approve", "reject"):
                counts["skipped"] += 1
                continue
            vid = int(row["variant_id"])
            if row.get("edited_title", "").strip():
                conn.execute("UPDATE variants SET title=? WHERE id=?", (row["edited_title"].strip(), vid))
            if row.get("edited_caption", "").strip():
                conn.execute("UPDATE variants SET caption=? WHERE id=?", (row["edited_caption"].strip(), vid))
            status = "approved" if decision == "approve" else "rejected"
            conn.execute("UPDATE variants SET status=?, needs_review=0 WHERE id=?", (status, vid))
            counts["approved" if status == "approved" else "rejected"] += 1
    conn.commit()
    return counts
