"""
SQLite database setup and initialization.
"""
import sqlite3
import os
import shutil
from datetime import datetime
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 用户数据目录：打包后不要把 finance.db 放在程序临时目录/安装目录里。
# Windows: C:\Users\<你>\AppData\Roaming\FinanceCalendar
# 其他系统: ~/.FinanceCalendar
APP_NAME = "FinanceCalendar"

def get_data_dir():
    base = os.getenv("APPDATA")
    if base:
        data_dir = os.path.join(base, APP_NAME)
    else:
        data_dir = os.path.join(os.path.expanduser("~"), "." + APP_NAME)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "finance.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MAX_BACKUPS = 30


import hashlib


def _file_hash(path):
    """MD5 of entire file. Fast enough for <1MB DB files."""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def backup_db(force=False):
    """Backup the database only if changed since last backup.
    Set force=True to backup regardless."""
    import logging
    log = logging.getLogger("uvicorn.error")
    if not os.path.exists(DB_PATH):
        log.info("backup_db: no DB file, skip")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Check if DB changed since last backup
    if not force:
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
        if backups:
            last_bak = os.path.join(BACKUP_DIR, backups[-1])
            db_hash = _file_hash(DB_PATH)
            bak_hash = _file_hash(last_bak)
            log.info(f"backup_db: db={db_hash[:12]} last_bak={bak_hash[:12]} same={db_hash == bak_hash}")
            if db_hash == bak_hash:
                return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"finance_{ts}.db")
    shutil.copy2(DB_PATH, dest)
    log.info(f"backup_db: created {os.path.basename(dest)}")
    # Cleanup old backups
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
    while len(backups) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))
    return dest


def list_backups():
    """Return list of backup files sorted newest first."""
    if not os.path.exists(BACKUP_DIR):
        return []
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')], reverse=True)
    result = []
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        size = os.path.getsize(path)
        result.append({"filename": f, "size": size})
    return result


def restore_db(filename: str) -> bool:
    """Restore database from a backup file using SQLite native backup API."""
    src = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(src):
        return False
    # Backup current before restore
    backup_db()
    # Use SQLite backup API (safe, no file-lock issues)
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(DB_PATH)
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    return True

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    type        TEXT    NOT NULL DEFAULT 'expense'
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    amount      REAL    NOT NULL,
    type        TEXT    NOT NULL DEFAULT 'expense',
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    project_id  INTEGER REFERENCES projects(id)  ON DELETE SET NULL,
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS reminders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    amount       REAL,
    total_debt   REAL,
    day_of_month INTEGER NOT NULL,
    start_date   TEXT,
    end_date     TEXT,
    note         TEXT,
    color        TEXT    NOT NULL DEFAULT '#ff3b30',
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS reminder_done (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id INTEGER NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
    year_month  TEXT    NOT NULL,
    done_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(reminder_id, year_month)
);

CREATE INDEX IF NOT EXISTS idx_tx_date   ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_type   ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_tx_cat    ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_tx_proj   ON transactions(project_id);
CREATE INDEX IF NOT EXISTS idx_rem_dm    ON reminder_done(reminder_id, year_month);
"""

DEFAULT_CATEGORIES = [
    ("餐饮", "expense"),
    ("交通", "expense"),
    ("购物", "expense"),
    ("娱乐", "expense"),
    ("居住", "expense"),
    ("医疗", "expense"),
    ("教育", "expense"),
    ("通讯", "expense"),
    ("其他支出", "expense"),
    ("信用卡还款", "expense"),
    ("花呗还款", "expense"),
    ("贷款还款", "expense"),
    ("其他还款", "expense"),
    ("工资", "income"),
    ("奖金", "income"),
    ("投资", "income"),
    ("兼职", "income"),
    ("其他收入", "income"),
]

DEFAULT_PROJECTS = [
    ("日常",),
    ("工作",),
    ("旅行",),
]


def init_db():
    """Create tables and seed defaults."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        cur = conn.cursor()
        # Always ensure categories exist
        cur.executemany(
            "INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)",
            DEFAULT_CATEGORIES,
        )
        cur.execute("SELECT COUNT(*) FROM projects")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT OR IGNORE INTO projects (name) VALUES (?)",
                DEFAULT_PROJECTS,
            )
        conn.commit()

    # Normalize reminder dates: 'YYYY-M' → 'YYYY-MM'
    with sqlite3.connect(DB_PATH) as conn:
        for row in conn.execute("SELECT id, start_date, end_date FROM reminders").fetchall():
            sid, s, e = row
            ns = s[:5] + '0' + s[5:] if s and len(s) == 6 and s[4] == '-' else s
            ne = e[:5] + '0' + e[5:] if e and len(e) == 6 and e[4] == '-' else e
            if ns != s or ne != e:
                conn.execute("UPDATE reminders SET start_date=?, end_date=? WHERE id=?", (ns, ne, sid))
        conn.commit()

    # Ensure total_debt column exists
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("SELECT total_debt FROM reminders LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE reminders ADD COLUMN total_debt REAL")
        conn.commit()


_migrated = False

@contextmanager
def get_db():
    """Yield a connection with row_factory set to sqlite3.Row."""
    global _migrated
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # One-time migration
    if not _migrated:
        try:
            conn.execute("SELECT start_date FROM reminders LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE reminders ADD COLUMN start_date TEXT")
                conn.execute("ALTER TABLE reminders ADD COLUMN end_date TEXT")
                conn.commit()
            except Exception:
                pass
        _migrated = True
    try:
        yield conn
    finally:
        conn.close()
