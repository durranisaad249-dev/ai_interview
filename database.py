"""
database.py — SQLite helper for AI Mock Interview Platform
All DB operations: sessions, answers, evaluations, achievements
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "interview_data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        role TEXT,
        difficulty TEXT,
        q_type TEXT,
        resume_text TEXT,
        resume_info TEXT,
        questions TEXT,
        status TEXT DEFAULT 'in_progress',
        total_score REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question_index INTEGER,
        question TEXT,
        answer TEXT,
        answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question_index INTEGER,
        score INTEGER,
        confidence INTEGER,
        technical_score INTEGER,
        communication_score INTEGER,
        tone_score INTEGER,
        summary TEXT,
        strengths TEXT,
        weaknesses TEXT,
        improvement TEXT,
        model_answer_hint TEXT,
        star_used BOOLEAN DEFAULT 0,
        follow_up_question TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        badge_name TEXT,
        badge_emoji TEXT,
        earned_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


# ── Sessions ──────────────────────────────────────────────

def create_session(session_id, role, difficulty, q_type, resume_text, resume_info, questions):
    conn = get_conn()
    conn.execute("""
        INSERT INTO sessions (session_id, role, difficulty, q_type, resume_text, resume_info, questions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, role, difficulty, q_type,
        resume_text,
        json.dumps(resume_info),
        json.dumps(questions)
    ))
    conn.commit()
    conn.close()


def complete_session(session_id, total_score):
    conn = get_conn()
    conn.execute("""
        UPDATE sessions SET status='completed', total_score=?, completed_at=?
        WHERE session_id=?
    """, (total_score, datetime.now(), session_id))
    conn.commit()
    conn.close()


def get_session(session_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['resume_info'] = json.loads(d['resume_info'] or '{}')
        d['questions'] = json.loads(d['questions'] or '[]')
        return d
    return None


def get_all_sessions():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, 
               COUNT(DISTINCT a.id) as answer_count,
               AVG(e.score) as avg_score
        FROM sessions s
        LEFT JOIN answers a ON s.session_id = a.session_id
        LEFT JOIN evaluations e ON s.session_id = e.session_id
        WHERE s.status = 'completed'
        GROUP BY s.session_id
        ORDER BY s.completed_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Answers ───────────────────────────────────────────────

def save_answer(session_id, question_index, question, answer):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO answers (session_id, question_index, question, answer)
        VALUES (?, ?, ?, ?)
    """, (session_id, question_index, question, answer))
    conn.commit()
    conn.close()


def get_answers(session_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM answers WHERE session_id=? ORDER BY question_index
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Evaluations ───────────────────────────────────────────

def save_evaluation(session_id, question_index, eval_data):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO evaluations 
        (session_id, question_index, score, confidence, technical_score,
         communication_score, tone_score, summary, strengths, weaknesses,
         improvement, model_answer_hint, star_used, follow_up_question)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        session_id, question_index,
        eval_data.get('score', 5),
        eval_data.get('confidence', 5),
        eval_data.get('technical_score', 5),
        eval_data.get('communication_score', 5),
        eval_data.get('tone_score', 5),
        eval_data.get('summary', ''),
        eval_data.get('strengths', ''),
        eval_data.get('weaknesses', ''),
        eval_data.get('improvement', ''),
        eval_data.get('model_answer_hint', ''),
        eval_data.get('star_used', False),
        eval_data.get('follow_up_question', '')
    ))
    conn.commit()
    conn.close()


def get_evaluations(session_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM evaluations WHERE session_id=? ORDER BY question_index
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_evaluations_for_dashboard():
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.*, s.role, s.difficulty, s.created_at, s.completed_at
        FROM evaluations e
        JOIN sessions s ON e.session_id = s.session_id
        WHERE s.status = 'completed'
        ORDER BY s.completed_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Achievements ──────────────────────────────────────────

def save_achievement(session_id, badge_name, badge_emoji):
    conn = get_conn()
    conn.execute("""
        INSERT INTO achievements (session_id, badge_name, badge_emoji)
        VALUES (?, ?, ?)
    """, (session_id, badge_name, badge_emoji))
    conn.commit()
    conn.close()


def get_achievements(session_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM achievements WHERE session_id=?
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_achievements():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM achievements ORDER BY earned_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Stats for Dashboard ───────────────────────────────────

def get_dashboard_stats():
    conn = get_conn()
    
    total_sessions = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE status='completed'"
    ).fetchone()[0]
    
    avg_score = conn.execute(
        "SELECT AVG(total_score) FROM sessions WHERE status='completed'"
    ).fetchone()[0] or 0
    
    best_score = conn.execute(
        "SELECT MAX(total_score) FROM sessions WHERE status='completed'"
    ).fetchone()[0] or 0

    role_stats = conn.execute("""
        SELECT role, COUNT(*) as count, AVG(total_score) as avg_score
        FROM sessions WHERE status='completed'
        GROUP BY role
    """).fetchall()

    score_trend = conn.execute("""
        SELECT DATE(completed_at) as date, AVG(total_score) as avg_score
        FROM sessions WHERE status='completed'
        GROUP BY DATE(completed_at)
        ORDER BY date
    """).fetchall()

    conn.close()
    return {
        'total_sessions': total_sessions,
        'avg_score': round(avg_score, 1),
        'best_score': round(best_score, 1),
        'role_stats': [dict(r) for r in role_stats],
        'score_trend': [dict(r) for r in score_trend],
    }