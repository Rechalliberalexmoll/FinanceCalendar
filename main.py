"""
Finance Manager — FastAPI + SQLite local bookkeeping backend.

Run:
    cd "E:\\Softs\\finance manager"
    python -m uvicorn main:app --reload --port 8000

OpenAPI docs: http://localhost:8000/docs
"""
from __future__ import annotations

from datetime import date
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import os
import database as db
import schemas as s


def _norm_date(d):
    """Normalize 'YYYY-M' to 'YYYY-MM' for consistent comparison."""
    if d and isinstance(d, str) and len(d) == 6 and d[4] == '-':
        return d[:5] + '0' + d[5:]
    return d
import parser as nlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="本地记账系统",
    description="FastAPI + SQLite 轻量本地记账后端",
    version="1.0.2",  # bump2
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    import logging
    log = logging.getLogger("uvicorn.error")
    log.info(f"DB path: {db.DB_PATH}")
    exists = os.path.exists(db.DB_PATH)
    log.info(f"DB exists: {exists}")
    if exists:
        log.info(f"DB size: {os.path.getsize(db.DB_PATH)} bytes")
    try:
        bak = db.backup_db()
        log.info(f"Startup backup: {bak or '(skipped, no changes)'}")
    except Exception as e:
        log.warning(f"Startup backup failed: {e}")
    try:
        db.init_db()
        log.info(f"DB after init: {os.path.getsize(db.DB_PATH)} bytes")
    except Exception as e:
        log.error(f"init_db failed: {e}")
    baks = db.list_backups()
    log.info(f"Backups on disk: {len(baks)} files in {db.BACKUP_DIR}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Backup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/backups", response_model=List[dict], tags=["备份"])
def list_backups():
    """List all available backups."""
    return db.list_backups()


@app.post("/backups", tags=["备份"])
def create_backup():
    """Manually create a backup."""
    path = db.backup_db()
    if path:
        return {"ok": True, "file": os.path.basename(path)}
    return {"ok": False, "error": "No database to backup"}


@app.post("/backups/restore", tags=["备份"])
def restore_backup(filename: str = Query(...)):
    """Restore database from a backup."""
    ok = db.restore_db(filename)
    if not ok:
        raise HTTPException(404, "Backup file not found")
    return {"ok": True, "restored": filename}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Categories
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/categories", response_model=List[s.CategoryOut], tags=["分类"])
def list_categories():
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
        return [dict(r) for r in rows]


@app.post("/categories", response_model=s.CategoryOut, status_code=201, tags=["分类"])
def create_category(body: s.CategoryCreate):
    with db.get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                (body.name, body.type),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM categories WHERE id=?", (cur.lastrowid,)).fetchone())
        except Exception:
            raise HTTPException(400, "分类已存在或参数错误")


@app.put("/categories/{cat_id}", response_model=s.CategoryOut, tags=["分类"])
def update_category(cat_id: int, body: s.CategoryUpdate):
    fields, vals = [], []
    if body.name is not None:
        fields.append("name=?"); vals.append(body.name)
    if body.type is not None:
        fields.append("type=?"); vals.append(body.type)
    if not fields:
        raise HTTPException(400, "未提供更新字段")
    vals.append(cat_id)
    with db.get_db() as conn:
        conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not row:
            raise HTTPException(404, "分类不存在")
        return dict(row)


@app.delete("/categories/{cat_id}", status_code=204, tags=["分类"])
def delete_category(cat_id: int):
    with db.get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Projects
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/projects", response_model=List[s.ProjectOut], tags=["项目"])
def list_projects():
    with db.get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()]


@app.post("/projects", response_model=s.ProjectOut, status_code=201, tags=["项目"])
def create_project(body: s.ProjectCreate):
    with db.get_db() as conn:
        try:
            cur = conn.execute("INSERT INTO projects (name) VALUES (?)", (body.name,))
            conn.commit()
            return dict(conn.execute("SELECT * FROM projects WHERE id=?", (cur.lastrowid,)).fetchone())
        except Exception:
            raise HTTPException(400, "项目已存在")


@app.put("/projects/{pid}", response_model=s.ProjectOut, tags=["项目"])
def update_project(pid: int, body: s.ProjectUpdate):
    if not body.name:
        raise HTTPException(400, "未提供名称")
    with db.get_db() as conn:
        conn.execute("UPDATE projects SET name=? WHERE id=?", (body.name, pid))
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, "项目不存在")
        return dict(row)


@app.delete("/projects/{pid}", status_code=204, tags=["项目"])
def delete_project(pid: int):
    with db.get_db() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Transactions  (CRUD)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _tx_row_to_dict(row) -> dict:
    d = dict(row)
    d["category_name"] = d.pop("category_name", None)
    d["project_name"] = d.pop("project_name", None)
    return d


_TX_JOIN = """
    SELECT t.*,
           c.name AS category_name,
           p.name AS project_name
    FROM transactions t
    LEFT JOIN categories c ON t.category_id = c.id
    LEFT JOIN projects  p ON t.project_id  = p.id
"""


@app.get("/transactions", response_model=List[s.TransactionOut], tags=["交易"])
def list_transactions(
    start_date: Optional[date] = Query(None, description="起始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    tx_type: Optional[str] = Query(None, description="income / expense"),
    category_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    where, params = ["1=1"], []
    if start_date:
        where.append("t.date >= ?"); params.append(str(start_date))
    if end_date:
        where.append("t.date <= ?"); params.append(str(end_date))
    if tx_type:
        where.append("t.type = ?"); params.append(tx_type)
    if category_id is not None:
        where.append("t.category_id = ?"); params.append(category_id)
    if project_id is not None:
        where.append("t.project_id = ?"); params.append(project_id)

    sql = f"{_TX_JOIN} WHERE {' AND '.join(where)} ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with db.get_db() as conn:
        return [_tx_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


@app.post("/transactions", response_model=s.TransactionOut, status_code=201, tags=["交易"])
def create_transaction(body: s.TransactionCreate):
    with db.get_db() as conn:
        cur = conn.execute(
            """INSERT INTO transactions (date, amount, type, category_id, project_id, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(body.date), body.amount, body.type, body.category_id, body.project_id, body.note),
        )
        conn.commit()
        row = conn.execute(_tx_join_single(), (cur.lastrowid,)).fetchone()
        return _tx_row_to_dict(row)


def _tx_join_single() -> str:
    return _TX_JOIN.replace("\n", " ") + " WHERE t.id = ?"


@app.get("/transactions/{tx_id}", response_model=s.TransactionOut, tags=["交易"])
def get_transaction(tx_id: int):
    with db.get_db() as conn:
        row = conn.execute(_tx_join_single(), (tx_id,)).fetchone()
        if not row:
            raise HTTPException(404, "交易记录不存在")
        return _tx_row_to_dict(row)


@app.put("/transactions/{tx_id}", response_model=s.TransactionOut, tags=["交易"])
def update_transaction(tx_id: int, body: s.TransactionUpdate):
    fields, vals = [], []
    for name in ("date", "amount", "type", "category_id", "project_id", "note"):
        v = getattr(body, name)
        if v is not None:
            if name == "date":
                v = str(v)
            fields.append(f"{name}=?")
            vals.append(v)
        elif name in ("note", "project_id"):
            # Allow clearing these fields by sending null
            fields.append(f"{name}=?")
            vals.append(None)
    if not fields:
        raise HTTPException(400, "未提供更新字段")
    fields.append("updated_at=datetime('now','localtime')")
    vals.append(tx_id)
    with db.get_db() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute(_tx_join_single(), (tx_id,)).fetchone()
        if not row:
            raise HTTPException(404, "交易记录不存在")
        return _tx_row_to_dict(row)


@app.delete("/transactions/{tx_id}", status_code=204, tags=["交易"])
def delete_transaction(tx_id: int):
    with db.get_db() as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Statistics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/stats/monthly", response_model=List[s.MonthlyStat], tags=["统计"])
def monthly_stats(
    year: Optional[int] = Query(None, description="年份，不传则返回所有月份"),
):
    where, params = [], []
    if year:
        where.append("strftime('%Y', date) = ?"); params.append(str(year))
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT strftime('%Y', date) AS yr,
               strftime('%m', date) AS mo,
               SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
        FROM transactions {where_clause}
        GROUP BY yr, mo
        ORDER BY yr, mo
    """
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        s.MonthlyStat(
            year=int(r["yr"]),
            month=int(r["mo"]),
            income=round(r["income"], 2),
            expense=round(r["expense"], 2),
            net=round(r["income"] - r["expense"], 2),
        )
        for r in rows
    ]


@app.get("/stats/category", response_model=List[s.CategoryStat], tags=["统计"])
def category_stats(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    tx_type: Optional[str] = Query(None, description="income / expense"),
):
    where, params = ["1=1"], []
    if start_date:
        where.append("t.date >= ?"); params.append(str(start_date))
    if end_date:
        where.append("t.date <= ?"); params.append(str(end_date))
    if tx_type:
        where.append("t.type = ?"); params.append(tx_type)

    sql = f"""
        SELECT c.id   AS category_id,
               COALESCE(c.name, '未分类') AS category_name,
               c.type,
               SUM(t.amount) AS total,
               COUNT(*)      AS count
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE {' AND '.join(where)}
        GROUP BY c.id
        ORDER BY total DESC
    """
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        s.CategoryStat(
            category_id=r["category_id"],
            category_name=r["category_name"],
            type=r["type"],
            total=round(r["total"], 2),
            count=r["count"],
        )
        for r in rows
    ]


@app.get("/stats/project", response_model=List[s.ProjectStat], tags=["统计"])
def project_stats(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    where, params = ["1=1"], []
    if start_date:
        where.append("t.date >= ?"); params.append(str(start_date))
    if end_date:
        where.append("t.date <= ?"); params.append(str(end_date))

    sql = f"""
        SELECT p.id   AS project_id,
               COALESCE(p.name, '未分配') AS project_name,
               SUM(CASE WHEN t.type='income'  THEN t.amount ELSE 0 END) AS income,
               SUM(CASE WHEN t.type='expense' THEN t.amount ELSE 0 END) AS expense,
               COUNT(*) AS count
        FROM transactions t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE {' AND '.join(where)}
        GROUP BY p.id
        ORDER BY income + expense DESC
    """
    with db.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        s.ProjectStat(
            project_id=r["project_id"],
            project_name=r["project_name"],
            income=round(r["income"], 2),
            expense=round(r["expense"], 2),
            net=round(r["income"] - r["expense"], 2),
            count=r["count"],
        )
        for r in rows
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Natural Language Parse
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/parse", response_model=s.ParseResult, tags=["解析"])
def parse_text(body: s.ParseRequest):
    """Parse a natural language description into structured transaction data.

    Calls local Ollama model. Returns preview only — does NOT write to database.
    If needs_confirmation=true, the user should confirm/correct before saving.
    """
    result = nlparse.parse_natural_language(body.text, model=body.model)
    return result


@app.post("/parse/confirm", response_model=s.TransactionOut, status_code=201, tags=["解析"])
def confirm_and_save(body: s.ParseConfirm):
    """Save a parsed result (from /parse) as an actual transaction."""
    with db.get_db() as conn:
        cur = conn.execute(
            """INSERT INTO transactions (date, amount, type, category_id, project_id, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (body.date, body.amount, body.type, body.category_id, body.project_id, body.note),
        )
        conn.commit()
        row = conn.execute(_tx_join_single(), (cur.lastrowid,)).fetchone()
        return _tx_row_to_dict(row)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Reminders (还款日提醒)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/reminders", response_model=List[s.ReminderOut], tags=["提醒"])
def list_reminders():
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM reminders ORDER BY day_of_month").fetchall()
        return [dict(r) for r in rows]


@app.post("/reminders", response_model=s.ReminderOut, status_code=201, tags=["提醒"])
def create_reminder(body: s.ReminderCreate):
    with db.get_db() as conn:
        cur = conn.execute(
            """INSERT INTO reminders (name, amount, total_debt, day_of_month, start_date, end_date, note, color)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.name, body.amount, body.total_debt, body.day_of_month, _norm_date(body.start_date), _norm_date(body.end_date), body.note, body.color),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM reminders WHERE id=?", (cur.lastrowid,)).fetchone())


@app.put("/reminders/{rid}", response_model=s.ReminderOut, tags=["提醒"])
def update_reminder(rid: int, body: s.ReminderUpdate):
    fields, vals = [], []
    for name in ("name", "amount", "total_debt", "day_of_month", "start_date", "end_date", "note", "color", "is_active"):
        v = getattr(body, name)
        if v is not None:
            if name in ("start_date", "end_date"):
                v = _norm_date(v)
            fields.append(f"{name}=?")
            vals.append(v)
        elif name in ("note",):
            fields.append(f"{name}=?")
            vals.append(None)
    if not fields:
        raise HTTPException(400, "未提供更新字段")
    vals.append(rid)
    with db.get_db() as conn:
        conn.execute(f"UPDATE reminders SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            raise HTTPException(404, "提醒不存在")
        return dict(row)


@app.delete("/reminders/{rid}", status_code=204, tags=["提醒"])
def delete_reminder(rid: int):
    with db.get_db() as conn:
        conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
        conn.commit()


@app.post("/reminders/{rid}/done", tags=["提醒"])
def mark_reminder_done(rid: int, body: s.ReminderDone):
    """Mark a reminder as done for a given year-month (idempotent)."""
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if not row:
            raise HTTPException(404, "提醒不存在")
        conn.execute(
            "INSERT OR IGNORE INTO reminder_done (reminder_id, year_month) VALUES (?, ?)",
            (rid, body.year_month),
        )
        conn.commit()
        return {"ok": True}


@app.delete("/reminders/{rid}/done", tags=["提醒"])
def undo_reminder_done(rid: int, year_month: str = Query(...)):
    """Unmark a reminder as done for a given year-month."""
    with db.get_db() as conn:
        conn.execute(
            "DELETE FROM reminder_done WHERE reminder_id=? AND year_month=?",
            (rid, year_month),
        )
        conn.commit()
        return {"ok": True}


@app.get("/reminders/status", response_model=List[dict], tags=["提醒"])
def reminders_status(year_month: str = Query(...)):
    """Return all reminders with done status for a given year-month."""
    with db.get_db() as conn:
        rows = conn.execute("""
            SELECT r.*, d.id AS done_id
            FROM reminders r
            LEFT JOIN reminder_done d ON r.id = d.reminder_id AND d.year_month = ?
            WHERE r.is_active = 1
              AND (r.start_date IS NULL OR REPLACE(r.start_date, '-', '') <= REPLACE(?, '-', ''))
              AND (r.end_date IS NULL OR REPLACE(r.end_date, '-', '') >= REPLACE(?, '-', ''))
            ORDER BY r.day_of_month
        """, (year_month, year_month, year_month)).fetchall()
    return [{**dict(r), "done": r["done_id"] is not None} for r in rows]


@app.get("/reminders/future-total", tags=["提醒"])
def future_total():
    """Calculate total pending amount from current month onward, minus done months."""
    from datetime import date
    today = date.today()
    cur_ym = f"{today.year}-{today.month:02d}"
    with db.get_db() as conn:
        rows = conn.execute("""
            SELECT r.* FROM reminders r
            WHERE r.is_active = 1 AND ((r.amount > 0) OR (r.total_debt > 0))
        """).fetchall()
        total = 0.0
        for r in rows:
            debt = r["total_debt"]
            amt = r["amount"] or 0
            if debt and debt > 0:
                # Has total debt → count it once, ignore minimum payment
                total += debt
            elif amt > 0:
                # No total debt → sum remaining months × minimum payment
                start = r["start_date"] or cur_ym
                end = r["end_date"]
                sy, sm = int(start[:4]), int(start[5:7])
                if end:
                    ey, em = int(end[:4]), int(end[5:7])
                else:
                    ey, em = today.year + 5, today.month
                y, m = sy, sm
                while (y, m) <= (ey, em):
                    ym = f"{y}-{m:02d}"
                    if ym >= cur_ym:
                        done = conn.execute(
                            "SELECT 1 FROM reminder_done WHERE reminder_id=? AND year_month=?",
                            (r["id"], ym)
                        ).fetchone()
                        if not done:
                            total += amt
                    m += 1
                    if m > 12:
                        m = 1; y += 1
    return {"total": round(total, 2)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Health check
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/", tags=["系统"])
def root():
    from fastapi.responses import HTMLResponse
    with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"})


@app.get("/health", tags=["系统"])
def health():
    with db.get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    return {"status": "ok", "transactions": count, "db_path": db.DB_PATH, "data_dir": os.path.dirname(db.DB_PATH)}


@app.get("/open-data-dir", tags=["系统"])
def open_data_dir():
    import subprocess
    data_dir = os.path.dirname(db.DB_PATH)
    subprocess.Popen(["explorer", data_dir])
    return {"ok": True, "path": data_dir}
