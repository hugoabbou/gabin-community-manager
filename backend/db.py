import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gabin.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hook TEXT,
            body TEXT,
            cta TEXT,
            hashtags TEXT,
            image_path TEXT,
            platforms TEXT DEFAULT '["instagram","facebook"]',
            themes TEXT DEFAULT '[]',
            sport_event TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            published_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sport TEXT NOT NULL,
            external_id TEXT NOT NULL UNIQUE,
            badge_url TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Default settings
    defaults = {
        "auto_publish": "false",
        "platforms": '["instagram", "facebook"]',
        "active_themes": '["sports_event", "daily_special", "ambiance"]',
        "daily_story_time": "09:00",
    }
    for key, value in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    # Default teams
    default_teams = [
        ("Paris Saint-Germain", "Football", "133604", "https://www.thesportsdb.com/images/media/team/badge/xzqdr11517660252.png"),
        ("Équipe de France", "Football", "133739", "https://www.thesportsdb.com/images/media/team/badge/sqxqrs1419536840.png"),
        ("AS Monaco", "Football", "133600", ""),
        ("Olympique de Marseille", "Football", "133601", ""),
    ]
    for team in default_teams:
        c.execute(
            "INSERT OR IGNORE INTO teams (name, sport, external_id, badge_url) VALUES (?, ?, ?, ?)",
            team,
        )

    conn.commit()
    conn.close()


# --- Posts ---

def create_post(hook, body, cta, hashtags, image_path, platforms, themes, sport_event=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO posts (hook, body, cta, hashtags, image_path, platforms, themes, sport_event)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (hook, body, cta, json.dumps(hashtags), image_path,
         json.dumps(platforms), json.dumps(themes),
         json.dumps(sport_event) if sport_event else None),
    )
    post_id = c.lastrowid
    conn.commit()
    conn.close()
    return post_id


def get_posts(status=None):
    conn = get_conn()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM posts ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [_row_to_post(r) for r in rows]


def get_post(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    conn.close()
    return _row_to_post(row) if row else None


def update_post_status(post_id, status):
    conn = get_conn()
    c = conn.cursor()
    published_at = datetime.now().isoformat() if status == "published" else None
    c.execute(
        "UPDATE posts SET status = ?, published_at = ? WHERE id = ?",
        (status, published_at, post_id),
    )
    conn.commit()
    conn.close()


def update_post_content(post_id, data):
    conn = get_conn()
    c = conn.cursor()
    fields = []
    values = []
    for key in ["hook", "body", "cta"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if "hashtags" in data:
        fields.append("hashtags = ?")
        values.append(json.dumps(data["hashtags"]))
    if fields:
        values.append(post_id)
        c.execute(f"UPDATE posts SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_post(post_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()


def _row_to_post(row):
    if not row:
        return None
    d = dict(row)
    for field in ["hashtags", "platforms", "themes"]:
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    if d.get("sport_event"):
        try:
            d["sport_event"] = json.loads(d["sport_event"])
        except Exception:
            pass
    return d


# --- Teams ---

def get_teams():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM teams WHERE active = 1 ORDER BY sport, name")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_team(name, sport, external_id, badge_url=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO teams (name, sport, external_id, badge_url) VALUES (?, ?, ?, ?)",
        (name, sport, external_id, badge_url),
    )
    team_id = c.lastrowid
    conn.commit()
    conn.close()
    return team_id


def remove_team(team_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE teams SET active = 0 WHERE id = ?", (team_id,))
    conn.commit()
    conn.close()


# --- Settings ---

def get_settings():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    conn.close()
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except Exception:
            result[row["key"]] = row["value"]
    return result


def update_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
