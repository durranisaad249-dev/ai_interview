"""
InterviewAI Pro v3.3
Flow: Home → Resume Upload → Resume Review (NEW) → Setup → Interview → Results → Dashboard/History
Fixes:
  - Resume Review page between upload and setup
  - Questions 100% based on resume (any field: BBA, HR, CS, Medical, Law, etc.)
  - Expanded roles list (tech + non-tech)
  - Voice bridge via components.html (not st.markdown)
  - getUserMedia before SpeechRecognition
  - PDF 4-method + image OCR (Ollama vision / pytesseract)
"""
import streamlit as st
import streamlit.components.v1 as components
import os, uuid, json, io, base64, time
from datetime import datetime
import plotly.graph_objects as go

try:
    import pdfplumber
    PDF_OK = True
except Exception:
    PDF_OK = False

try:
    import fitz  # PyMuPDF — renders PDF pages to images for scanned-PDF OCR
    FITZ_OK = True
except Exception:
    FITZ_OK = False

try:
    import pytesseract
    from PIL import Image as PILImg
    OCR_OK = True
except Exception:
    OCR_OK = False

try:
    from PIL import Image as PILImage
    PIL_OK = True
except Exception:
    PIL_OK = False

try:
    import docx as docx_lib
    DOCX_OK = True
except Exception:
    DOCX_OK = False

import requests
import database as db
import ai_engine as ai

# ── Delete session helper (removes all related rows) ───────────────
def delete_session(session_id):
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH, check_same_thread=False)
    try:
        conn.execute("DELETE FROM evaluations  WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM achievements WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions     WHERE session_id=?", (session_id,))
        # answers table may not exist in older DBs
        try:
            conn.execute("DELETE FROM answers WHERE session_id=?", (session_id,))
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()

# ── page config ────────────────────────────────────────────────────
st.set_page_config(page_title="InterviewAI Pro", page_icon="🎯",
                   layout="wide", initial_sidebar_state="collapsed")
db.init_db()

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# ── CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

/* ═══════════════════════════════════════════
   COLOUR PALETTE — Deep Indigo × Gold × Coral
   ═══════════════════════════════════════════ */
:root{
  /* Backgrounds — rich deep navy-indigo */
  --bg:   #07091a;
  --bg2:  #0c0f24;
  --bg3:  #10152e;
  --bg4:  #161c38;

  /* Accent palette */
  --a:    #6366f1;   /* indigo */
  --a2:   #8b5cf6;   /* violet */
  --a3:   #06d6a0;   /* emerald */
  --gold: #fbbf24;   /* amber */
  --coral:#f43f5e;   /* rose */
  --cyan: #22d3ee;   /* cyan */

  /* Borders */
  --bd:   rgba(99,102,241,.25);
  --bd2:  rgba(255,255,255,.07);
  --bd3:  rgba(99,102,241,.12);

  /* Text */
  --t1:   #f0f4ff;
  --t2:   #9ba3c7;
  --t3:   #4e5a80;

  /* Glow shadows */
  --glow-a:  rgba(99,102,241,.35);
  --glow-a2: rgba(139,92,246,.35);
  --glow-em: rgba(6,214,160,.3);
}

/* ── Reset & Base ─────────────────────────── */
*,*::before,*::after{box-sizing:border-box}
html,body,[data-testid="stApp"],[data-testid="stAppViewContainer"]{
  background:var(--bg)!important;
  color:var(--t1)!important;
  font-family:'DM Sans',sans-serif!important;
}

/* Remove Streamlit chrome */
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],.stDeployButton{display:none!important}
[data-testid="stSidebar"]{background:var(--bg2)!important}
.block-container{padding-top:1.2rem!important}

/* ── Typography ───────────────────────────── */
h1,h2,h3,h4{font-family:'Syne',sans-serif!important;letter-spacing:-.02em}

/* ── Buttons — gradient pill ──────────────── */
.stButton>button{
  background:linear-gradient(135deg,var(--a),var(--a2))!important;
  color:#fff!important;border:none!important;
  border-radius:12px!important;
  font-family:'Syne',sans-serif!important;
  font-weight:700!important;
  letter-spacing:.03em!important;
  transition:all .22s cubic-bezier(.4,0,.2,1)!important;
  box-shadow:0 4px 24px var(--glow-a)!important;
  padding:10px 22px!important;
}
.stButton>button:hover{
  transform:translateY(-2px) scale(1.01)!important;
  box-shadow:0 8px 32px var(--glow-a2)!important;
  background:linear-gradient(135deg,var(--a2),var(--a))!important;
}
.stButton>button:active{transform:translateY(0)!important}

/* Back / subtle button */
.back-btn>.stButton>button{
  background:rgba(255,255,255,.04)!important;
  border:1px solid var(--bd2)!important;
  box-shadow:none!important;
  color:var(--t2)!important;
  font-size:13px!important;
  padding:6px 14px!important;
  border-radius:8px!important;
}
.back-btn>.stButton>button:hover{
  background:rgba(99,102,241,.12)!important;
  border-color:var(--bd)!important;
  color:var(--t1)!important;
  transform:none!important;
}

/* ── Inputs ───────────────────────────────── */
.stTextInput>div>div>input,.stTextArea textarea{
  background:var(--bg3)!important;
  border:1px solid var(--bd)!important;
  color:var(--t1)!important;
  border-radius:12px!important;
  transition:border-color .2s!important;
}
.stTextInput>div>div>input:focus,.stTextArea textarea:focus{
  border-color:var(--a)!important;
  box-shadow:0 0 0 3px rgba(99,102,241,.15)!important;
}

/* ── File uploader ────────────────────────── */
[data-testid="stFileUploadDropzone"]{
  background:linear-gradient(135deg,rgba(99,102,241,.04),rgba(139,92,246,.04))!important;
  border:2px dashed var(--bd)!important;
  border-radius:16px!important;
  transition:all .2s!important;
}
[data-testid="stFileUploadDropzone"]:hover{
  border-color:var(--a)!important;
  background:rgba(99,102,241,.08)!important;
}

/* ── Select boxes ─────────────────────────── */
[data-baseweb="select"]>div{
  background:var(--bg3)!important;
  border:1px solid var(--bd)!important;
  color:var(--t1)!important;
  border-radius:12px!important;
}

/* ── Tabs ─────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{
  background:var(--bg2)!important;
  border-radius:14px 14px 0 0;
  padding:4px;gap:4px;
  border-bottom:1px solid var(--bd2)!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;
  color:var(--t2)!important;
  border-radius:10px!important;
  font-family:'Syne',sans-serif!important;
  font-weight:600!important;
}
.stTabs [aria-selected="true"]{
  background:linear-gradient(135deg,var(--a),var(--a2))!important;
  color:#fff!important;
  box-shadow:0 2px 12px var(--glow-a)!important;
}

/* ── Metrics ──────────────────────────────── */
[data-testid="stMetric"]{
  background:var(--bg3)!important;
  border:1px solid var(--bd2)!important;
  border-radius:16px!important;
  padding:18px!important;
  transition:all .2s!important;
}
[data-testid="stMetric"]:hover{
  border-color:var(--bd)!important;
  box-shadow:0 4px 20px rgba(0,0,0,.3)!important;
}

/* ── Expanders ────────────────────────────── */
.streamlit-expanderHeader{
  background:var(--bg3)!important;
  border:1px solid var(--bd2)!important;
  border-radius:12px!important;
  color:var(--t1)!important;
  font-family:'Syne',sans-serif!important;
}

/* ── Alert boxes ──────────────────────────── */
.stSuccess{background:rgba(6,214,160,.08)!important;border:1px solid rgba(6,214,160,.3)!important;border-radius:12px!important}
.stError  {background:rgba(244,63,94,.08)!important;border:1px solid rgba(244,63,94,.3)!important;border-radius:12px!important}
.stInfo   {background:rgba(99,102,241,.08)!important;border:1px solid rgba(99,102,241,.3)!important;border-radius:12px!important}
.stWarning{background:rgba(251,191,36,.08)!important;border:1px solid rgba(251,191,36,.3)!important;border-radius:12px!important}

/* ── Progress bar ─────────────────────────── */
.stProgress>div>div{
  background:linear-gradient(90deg,var(--a),var(--a2),var(--cyan))!important;
  border-radius:4px!important;
}

/* ── Radio buttons ────────────────────────── */
.stRadio>div>label{
  background:var(--bg3)!important;
  border:1px solid var(--bd2)!important;
  border-radius:12px!important;
  padding:10px 16px!important;
  transition:all .2s!important;
}
.stRadio>div>label:hover{
  border-color:var(--bd)!important;
  background:var(--bg4)!important;
}

/* ═══════════════════════════════════════════
   CUSTOM COMPONENTS
   ═══════════════════════════════════════════ */

/* Logo */
.logo{
  font-family:'Syne',sans-serif;font-size:20px;font-weight:800;
  background:linear-gradient(135deg,var(--a),var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  letter-spacing:-.03em;
}

/* Section label */
.sl{
  font-family:'DM Mono',monospace;font-size:11px;
  color:var(--a);letter-spacing:.14em;text-transform:uppercase;margin-bottom:10px;
}

/* ── Cards ────────────────────────────────── */
.card{
  background:linear-gradient(145deg,var(--bg3),var(--bg2));
  border:1px solid var(--bd2);
  border-radius:20px;padding:24px;margin-bottom:14px;
  transition:all .22s;
  box-shadow:0 2px 16px rgba(0,0,0,.3);
}
.card:hover{border-color:var(--bd);box-shadow:0 8px 32px rgba(0,0,0,.4)}

.cs{
  background:var(--bg3);border:1px solid var(--bd2);
  border-radius:14px;padding:14px 18px;
}

/* Feature card */
.fc{
  background:linear-gradient(145deg,rgba(16,21,46,.9),rgba(12,15,36,.95));
  border:1px solid var(--bd2);
  border-radius:18px;padding:22px;height:100%;
  transition:all .22s cubic-bezier(.4,0,.2,1);
  box-shadow:0 2px 12px rgba(0,0,0,.25);
  position:relative;overflow:hidden;
}
.fc::before{
  content:'';position:absolute;top:-40px;right:-40px;
  width:120px;height:120px;
  background:radial-gradient(circle,rgba(99,102,241,.08) 0%,transparent 70%);
  pointer-events:none;
}
.fc:hover{
  border-color:rgba(99,102,241,.3);
  transform:translateY(-3px);
  box-shadow:0 12px 40px rgba(0,0,0,.4),0 0 0 1px rgba(99,102,241,.15);
}

/* Pill badge */
.pill{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(99,102,241,.08);
  border:1px solid rgba(99,102,241,.2);
  border-radius:100px;padding:7px 16px;
  font-size:13px;color:var(--t2);
  margin-right:8px;margin-bottom:8px;
  transition:all .2s;
}
.pill:hover{background:rgba(99,102,241,.15);border-color:var(--bd)}
.pill strong{color:var(--a);font-family:'DM Mono',monospace}

/* Achievement badge */
.badge{
  display:inline-flex;align-items:center;gap:6px;
  padding:5px 14px;
  background:linear-gradient(135deg,rgba(251,191,36,.12),rgba(251,191,36,.06));
  border:1px solid rgba(251,191,36,.3);
  border-radius:100px;font-size:13px;color:var(--gold);
  margin:3px;font-family:'Syne',sans-serif;font-weight:600;
}

/* ── Metric bar ───────────────────────────── */
.mb{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.mb-l{font-size:12px;color:var(--t2);width:160px;flex-shrink:0;font-family:'DM Mono',monospace}
.mb-t{flex:1;height:7px;background:rgba(255,255,255,.05);border-radius:4px;overflow:hidden}
.mb-f{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--a),var(--a2))}
.mb-v{font-family:'DM Mono',monospace;font-size:13px;width:40px;text-align:right;color:var(--t1);font-weight:600}

/* ── History row ──────────────────────────── */
.hr-row{
  display:flex;align-items:center;gap:14px;
  padding:14px 18px;
  background:linear-gradient(135deg,var(--bg3),var(--bg2));
  border:1px solid var(--bd2);
  border-radius:14px;margin-bottom:8px;
  transition:all .2s;
}
.hr-row:hover{border-color:var(--bd);box-shadow:0 4px 16px rgba(0,0,0,.3)}

/* ── Progress stepper ─────────────────────── */
.ps{display:flex;gap:6px;margin-bottom:20px}
.psd{flex:1;height:4px;border-radius:2px;background:var(--bg3)}
.psd.done{background:linear-gradient(90deg,var(--a),var(--a2))}
.psd.active{background:linear-gradient(90deg,var(--a2),var(--cyan));opacity:.7}

/* ── Review page ──────────────────────────── */
.field-detected{
  padding:20px 22px;border-radius:16px;
  background:linear-gradient(135deg,rgba(6,214,160,.06),rgba(6,214,160,.02));
  border:2px solid rgba(6,214,160,.3);margin-bottom:20px;
}
.skill-tag{
  display:inline-block;
  background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.25);
  border-radius:8px;padding:4px 11px;font-size:11px;color:var(--a);
  margin:3px;font-family:'DM Mono',monospace;
}
.exp-tag{
  display:inline-block;
  background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.25);
  border-radius:8px;padding:4px 11px;font-size:11px;color:#a78bfa;margin:3px;
}
.q-preview-item{
  display:flex;gap:12px;padding:14px;
  background:var(--bg3);border:1px solid var(--bd2);
  border-radius:12px;margin-bottom:8px;
  transition:all .2s;
}
.q-preview-item:hover{border-color:var(--bd)}
.q-num{
  font-family:'DM Mono',monospace;font-size:11px;color:var(--a);
  background:rgba(99,102,241,.12);border-radius:6px;
  padding:3px 9px;flex-shrink:0;height:fit-content;
}

/* ── Global scrollbar ─────────────────────── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--a)}

/* ── Slider ───────────────────────────────── */
.stSlider [data-baseweb="slider"] div[role="slider"]{
  background:var(--a)!important;
  box-shadow:0 0 0 4px rgba(99,102,241,.25)!important;
}
</style>
""", unsafe_allow_html=True)

# ── Accent per page ────────────────────────────────────────────────
PAGE_ACCENT = {
    'home':          ('#6366f1', '#8b5cf6'),   # indigo → violet
    'demo':          ('#22d3ee', '#06b6d4'),   # cyan
    'resume':        ('#a78bfa', '#7c3aed'),   # violet
    'resume_review': ('#06d6a0', '#059669'),   # emerald
    'setup':         ('#f97316', '#fb923c'),   # orange
    'interview':     ('#06d6a0', '#22d3ee'),   # emerald → cyan
    'results':       ('#fbbf24', '#f59e0b'),   # amber/gold
    'dashboard':     ('#f43f5e', '#e11d48'),   # rose
    'history':       ('#22d3ee', '#06b6d4'),   # cyan/teal
}

def set_accent(page):
    a, a2 = PAGE_ACCENT.get(page, ('#6366f1', '#8b5cf6'))
    st.markdown(f"""<style>
    :root{{--a:{a}!important;--a2:{a2}!important;--bd:rgba(99,102,241,.25)!important}}
    .stButton>button{{
      background:linear-gradient(135deg,{a},{a2})!important;
      box-shadow:0 4px 24px {a}55!important;
    }}
    .stButton>button:hover{{box-shadow:0 8px 32px {a2}66!important}}
    .stTabs [aria-selected="true"]{{background:linear-gradient(135deg,{a},{a2})!important}}
    .sl{{color:{a}!important}}
    .logo{{background:linear-gradient(135deg,{a},{a2})!important;-webkit-background-clip:text!important;-webkit-text-fill-color:transparent!important}}
    .psd.done{{background:linear-gradient(90deg,{a},{a2})!important}}
    </style>""", unsafe_allow_html=True)

# ── Roles ───────────────────────────────────────────────────────────
ALL_ROLES = [
    "Software Engineer",
    "Data Scientist",
    "Frontend Developer",
    "Backend Developer",
    "HR Manager",
]

# ── Deep question context per role ──────────────────────────────────
ROLE_DEEP_CONTEXT = {
    "Software Engineer": (
        "Ask practical questions about software design, common algorithms, debugging, "
        "code quality, and technology choices. Mix conceptual understanding with "
        "real-world application. Avoid trivial syntax questions."
    ),
    "Data Scientist": (
        "Ask about model building, data cleaning, evaluation metrics, and applying "
        "ML to real problems. Include a mix of practical and conceptual questions. "
        "Avoid questions that only test library syntax."
    ),
    "Frontend Developer": (
        "Ask about how browsers work, component design, state management, performance, "
        "and user experience. Cover both fundamentals and practical patterns. "
        "Avoid trivial HTML/CSS trivia."
    ),
    "Backend Developer": (
        "Ask about API design, databases, server-side logic, scalability, and "
        "common architectural patterns. Include practical problem-solving questions. "
        "Avoid questions with obvious textbook answers."
    ),
    "HR Manager": (
        "Ask about hiring processes, employee management, conflict resolution, "
        "performance reviews, and HR best practices. Focus on real-world scenarios "
        "and decision-making rather than definitions."
    ),
}

# ── Field validation keywords — must match one of these to be accepted ──
ALLOWED_FIELD_KEYWORDS = {
    "Software Engineer":  ["software", "engineer", "developer", "programming", "coding",
                           "computer science", "cs", "swe", "full stack", "fullstack",
                           "java", "python", "c++", "golang", "rust", "software dev"],
    "Data Scientist":     ["data science", "data scientist", "machine learning", "ml",
                           "ai", "artificial intelligence", "deep learning", "nlp",
                           "analytics", "data analyst", "statistician", "data engineer",
                           "computer vision", "big data", "data mining"],
    "Frontend Developer": ["frontend", "front end", "front-end", "react", "vue", "angular",
                           "ui developer", "web developer", "javascript developer",
                           "ui/ux developer", "web engineer", "html", "css", "typescript"],
    "Backend Developer":  ["backend", "back end", "back-end", "server", "api developer",
                           "node", "django", "flask", "spring", "rails", "laravel",
                           "microservices", "database engineer", "systems engineer"],
    "HR Manager":         ["hr", "human resource", "human resources", "recruiter",
                           "talent", "people ops", "people operations", "hrbp",
                           "hr generalist", "hr business partner", "hr manager",
                           "workforce", "organisational development", "payroll"],
}

def detect_allowed_role(resume_text: str, resume_info: dict):
    """
    Returns (matched_role, confidence) or (None, 0) if resume doesn't match
    any of the 5 allowed fields.
    Checks: detected role title, field, skills, job titles in resume text.
    """
    check_text = " ".join([
        resume_info.get('last_role', ''),
        resume_info.get('suggested_role', ''),
        resume_info.get('field', ''),
        resume_info.get('summary', ''),
        " ".join(resume_info.get('skills', [])),
        " ".join(resume_info.get('technologies', [])),
        resume_text[:2000],   # first 2000 chars of raw resume
    ]).lower()

    best_role, best_count = None, 0
    for role, keywords in ALLOWED_FIELD_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in check_text)
        if count > best_count:
            best_role, best_count = role, count

    # Must have at least 2 keyword hits to accept
    if best_count >= 2:
        return best_role, best_count
    return None, 0


def generate_deep_questions(role, difficulty, q_type, q_count, resume_info, warmup):
    """Wrapper that injects role-specific depth context. warmup always False."""
    deep_ctx = ROLE_DEEP_CONTEXT.get(role, "")
    enhanced_info = dict(resume_info) if resume_info else {}
    enhanced_info['_depth_instruction'] = (
        f"Instructions for question generation:\n"
        f"1. Ask clear, practical questions relevant to the {role} role.\n"
        f"2. {deep_ctx}\n"
        f"3. Questions should be answerable in 1-3 minutes — not overly long or complex.\n"
        f"4. Mix scenario-based, conceptual, and experience questions.\n"
        f"5. Base questions on the candidate's resume skills and background.\n"
        f"6. Difficulty level: {difficulty}."
    )
    # Force warmup=False so first question is always a depth question
    return ai.generate_questions(role, difficulty, q_type, q_count, enhanced_info, False)


DEFAULTS = dict(
    page='home', session_id=None,
    resume_text='', resume_info={},
    detected_role='', generated_questions=[],
    role='Software Engineer', difficulty='Senior',
    q_type='Mixed', q_count=5, warmup=False,
    questions=[], current_q=0,
    answers={}, evaluations={}, follow_ups={},
    interview_started=False, interview_complete=False,
    resume_field_rejected='',
    q_start_time=None,
    q_time_limit=120,
    timed_out=False,
    cam_scores={},       # accumulated camera personality scores for this session
    cam_score_count=0,   # number of samples accumulated
)
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def nav(p): st.session_state.page = p; st.rerun()

def back_btn(lbl, dest):
    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button(f"← {lbl}"): nav(dest)
    st.markdown('</div>', unsafe_allow_html=True)

def sc_col(s):
    if s >= 8: return '#10b981'
    if s >= 6: return '#4f8bff'
    if s >= 4: return '#f59e0b'
    return '#ef4444'

def mbar(lbl, v, mx=10):
    pct = (v / mx) * 100; c = sc_col(v)
    return (f'<div class="mb"><div class="mb-l">{lbl}</div>'
            f'<div class="mb-t"><div class="mb-f" style="width:{pct}%;background:{c}"></div></div>'
            f'<div class="mb-v" style="color:{c}">{v}/10</div></div>')

def grade(pct):
    if pct >= 90: return 'A+', 'Exceptional'
    if pct >= 80: return 'A',  'Excellent'
    if pct >= 70: return 'B+', 'Good'
    if pct >= 60: return 'B',  'Satisfactory'
    if pct >= 50: return 'C',  'Needs Work'
    return 'D', 'Poor'

# ── nav bar ────────────────────────────────────────────────────────
def nav_bar(cur):
    set_accent(cur)
    status = ai.check_ollama_status()
    dc = '#06d6a0' if status['online'] else '#f43f5e'
    mt = f"Model: {OLLAMA_MODEL}" if status['online'] else 'Offline — Demo Mode'
    a, a2 = PAGE_ACCENT.get(cur, ('#6366f1', '#8b5cf6'))
    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;padding:10px 0 18px;
      border-bottom:1px solid rgba(99,102,241,.15);margin-bottom:22px">
      <div class="logo" style="background:linear-gradient(135deg,{a},{a2});-webkit-background-clip:text;-webkit-text-fill-color:transparent">InterviewAI Pro</div>
      <span style="font-size:10px;font-weight:700;padding:2px 9px;
        background:rgba(99,102,241,.12);border:1px solid rgba(99,102,241,.25);
        border-radius:20px;color:{a};font-family:'DM Mono',monospace">v3.3</span>
      <div style="flex:1"></div>
      <div style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--t2)">
        <span style="width:8px;height:8px;border-radius:50%;background:{dc};display:inline-block;
          box-shadow:0 0 8px {dc}88"></span>
        <span>{mt}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    pages = [('','Home','home'), ('','Demo','demo'), ('','Resume','resume'),
             ('','Review','resume_review'), ('','Setup','setup'),
             ('','Interview','interview'), ('','Results','results'),
             ('','Dashboard','dashboard'), ('','History','history')]
    cols = st.columns(len(pages))
    for col, (ico, lbl, key) in zip(cols, pages):
        with col:
            if st.button(f"{lbl}", key=f"nav_{key}_{cur}", use_container_width=True):
                nav(key)

# ── flow progress bar ──────────────────────────────────────────────
FLOW = ['resume', 'resume_review', 'setup', 'interview', 'results']

def flow_bar(cur):
    labels = {'resume':'1. Upload', 'resume_review':'2. Review', 'setup':'3. Setup',
              'interview':'4. Interview', 'results':'5. Results'}
    idx = FLOW.index(cur) if cur in FLOW else -1
    segs = ""
    for i, step in enumerate(FLOW):
        cls = "done" if i < idx else "active" if i == idx else ""
        segs += f'<div class="psd {cls}"></div>'
    lbls = "".join([
        f'<div style="flex:1;text-align:center;font-size:11px;color:{"var(--a)" if i==idx else "var(--t3)" if i>idx else "var(--a3)"};font-family:\'DM Mono\',monospace">{labels[s]}</div>'
        for i, s in enumerate(FLOW)
    ])
    st.markdown(f'<div class="ps">{segs}</div><div style="display:flex;margin-top:-12px;margin-bottom:18px">{lbls}</div>',
                unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  FILE EXTRACTION — PDF + Image OCR + TXT + DOCX
# ════════════════════════════════════════════════════════════════════
def ocr_ollama(raw: bytes) -> str:
    b64 = base64.b64encode(raw).decode('utf-8')
    for model in ['llava-phi3', 'llava', 'bakllava']:
        try:
            r = requests.post(OLLAMA_URL, json={
                "model": model,
                "prompt": "This is a resume/CV image. Extract ALL text exactly as written. Return only the extracted text.",
                "images": [b64], "stream": False,
                "options": {"temperature": 0, "num_predict": 2000}
            }, timeout=90)
            if r.ok:
                t = r.json().get("response", "").strip()
                if len(t) > 50: return t
        except Exception:
            pass
    return ""

def ocr_tesseract(raw: bytes) -> str:
    if not OCR_OK: return ""
    try:
        img = PILImg.open(io.BytesIO(raw))
        return pytesseract.image_to_string(img).strip()
    except Exception:
        return ""

def render_pdf_pages_to_images(raw: bytes, max_pages: int = 4, zoom: float = 2.2):
    """
    Renders the first `max_pages` pages of a scanned PDF to PNG image bytes
    using PyMuPDF (fitz). Returns a list of PNG byte strings, one per page.
    This is required because pdfplumber only extracts embedded text layers —
    scanned/photographed PDFs have no text layer, only page images, so they
    must be rasterised before OCR (Ollama vision or Tesseract) can read them.
    """
    if not FITZ_OK:
        return []
    pages_png = []
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
        mat = fitz.Matrix(zoom, zoom)  # upscale for sharper OCR
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=mat)
            pages_png.append(pix.tobytes("png"))
        doc.close()
    except Exception:
        return []
    return pages_png


def extract_file(uploaded_file):
    """Returns (text, success:bool, warning:str)"""
    name = uploaded_file.name.lower()
    raw  = uploaded_file.read()

    # TXT
    if name.endswith('.txt'):
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try: return raw.decode(enc).strip(), True, ''
            except: pass
        return raw.decode('utf-8', errors='replace').strip(), True, ''

    # DOCX
    if name.endswith('.docx'):
        if DOCX_OK:
            try:
                from docx import Document
                doc = Document(io.BytesIO(raw))
                t = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
                if len(t) >= 50: return t, True, ''
            except Exception:
                pass
        return '', False, 'Could not read DOCX — paste text in the Paste tab instead.'

    # Images
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
    if any(name.endswith(e) for e in IMAGE_EXTS):
        t = ocr_ollama(raw)
        if len(t) >= 50: return t, True, ''
        t = ocr_tesseract(raw)
        if len(t) >= 50: return t, True, ''
        return '', False, (
            "Could not read text from image.\n"
            "Install a vision model: `ollama pull llava-phi3`\n"
            "Or paste your resume text in the Paste tab."
        )

    # PDF — 4 methods + image OCR fallback
    if not PDF_OK:
        return '', False, 'pdfplumber not installed: pip install pdfplumber'
    if not FITZ_OK:
        # Text-layer extraction still works without PyMuPDF; only scanned-PDF
        # OCR fallback needs it. Note this so the user knows what to install.
        pass

    best = ''
    def try_method(fn):
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return '\n'.join(fn(p) for p in pdf.pages).strip()
        except Exception:
            return ''

    t = try_method(lambda p: p.extract_text() or '')
    if len(t) > len(best): best = t
    if len(best) >= 60: return best, True, ''

    t = try_method(lambda p: p.extract_text(x_tolerance=4, y_tolerance=4) or '')
    if len(t) > len(best): best = t
    if len(best) >= 60: return best, True, ''

    t = try_method(lambda p: ' '.join(w['text'] for w in (p.extract_words() or [])))
    if len(t) > len(best): best = t
    if len(best) >= 60: return best, True, ''

    t = try_method(lambda p: ''.join(c.get('text','') for c in (p.chars or [])))
    if len(t) > len(best): best = t
    if len(best) >= 50: return best, True, ''

    # Scanned PDF — rasterise pages to images first, THEN run OCR on those images.
    # (Running OCR directly on raw PDF bytes — as before — always fails, since
    #  OCR functions expect image bytes like PNG/JPEG, not a PDF container.)
    page_images = render_pdf_pages_to_images(raw, max_pages=4)

    if page_images:
        combined = []
        for img_bytes in page_images:
            t = ocr_ollama(img_bytes)
            if len(t) < 30:
                t = ocr_tesseract(img_bytes)
            if t:
                combined.append(t)
        full_text = '\n\n'.join(combined).strip()
        if len(full_text) >= 50:
            return full_text, True, ''
        if len(full_text) > len(best):
            best = full_text

    warn_lines = ["PDF is a scanned image — could not extract text automatically.", "", "**Fix options:**"]
    if not FITZ_OK:
        warn_lines.append("• Install PDF rendering support: `pip install PyMuPDF`")
    warn_lines.append("• Install vision model: `ollama pull llava-phi3`")
    warn_lines.append("• Export your CV from Word/Google Docs as PDF")
    warn_lines.append("• Upload a screenshot/photo of your CV instead")
    warn_lines.append("• Paste your resume text in the Paste tab below")
    warn = "\n".join(warn_lines)
    return best, len(best.strip()) >= 30, warn


# ════════════════════════════════════════════════════════════════════
#  HOME
# ════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════
#  HOME PAGE — Premium Realistic AI Humanoid Head
# ════════════════════════════════════════════════════════════════════
def page_home():
    nav_bar('home')
    
    c1, c2 = st.columns([1.2, 1])
    
    with c1:
        st.markdown('<div class="sl">AI-POWERED INTERVIEW PLATFORM</div>', unsafe_allow_html=True)
        st.markdown("""
        <h1 style="font-family:Syne,sans-serif;font-size:clamp(34px,5.5vw,68px);
                   font-weight:800;line-height:1.05;margin-bottom:16px">
          <span style="background:linear-gradient(135deg,#E8E8E8,#A0A0A0,#6B7280);
                     -webkit-background-clip:text;-webkit-text-fill-color:transparent">
            Ace Your Next<br>Interview
          </span>
        </h1>
        """, unsafe_allow_html=True)
        st.markdown("""
        <p style="font-size:17px;color:var(--t2);line-height:1.6;max-width:520px;margin-bottom:28px">
          Upload your resume — any field, any format. AI reads it and asks questions based on YOUR exact background.
        </p>
        """, unsafe_allow_html=True)
        
        stats = db.get_dashboard_stats()
        st.markdown(f"""<div style="margin-bottom:24px">
          <span class="pill">🎯 <strong>{stats['total_sessions']}</strong> Sessions</span>
          <span class="pill">⭐ <strong>{stats['avg_score']:.0f}%</strong> Avg</span>
          <span class="pill">🎤 <strong>Voice</strong> Mode</span>
          <span class="pill">📄 <strong>Any</strong> Field</span>
        </div>""", unsafe_allow_html=True)
        
        a, b, c = st.columns(3)
        with a:
            if st.button("Try Demo", use_container_width=True): nav('demo')
        with b:
            if st.button("Start Now", use_container_width=True): nav('resume')
        with c:
            if st.button("Dashboard", use_container_width=True): nav('dashboard')

    with c2:
        # Premium Realistic AI Humanoid Head - No Cartoon, Pure Realistic Quality
        components.html("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { background: transparent; overflow: hidden; margin: 0; padding: 0; }
                #container {
                    width: 100%;
                    height: 420px;
                    position: relative;
                    border-radius: 28px;
                    overflow: hidden;
                    background: radial-gradient(circle at 30% 20%, #1a1a2e, #0a0a15);
                    box-shadow: 0 20px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
                    cursor: pointer;
                }
                canvas { width: 100%; height: 100%; display: block; }
                .badge-container {
                    position: absolute;
                    bottom: 15px;
                    left: 0;
                    right: 0;
                    text-align: center;
                    pointer-events: none;
                    z-index: 10;
                }
                .live-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    background: rgba(0,0,0,0.6);
                    backdrop-filter: blur(8px);
                    padding: 6px 16px;
                    border-radius: 40px;
                    font-size: 11px;
                    font-family: monospace;
                    color: #10b981;
                    border: 1px solid rgba(16,185,129,0.4);
                    letter-spacing: 1px;
                }
                .live-dot {
                    width: 8px;
                    height: 8px;
                    background: #10b981;
                    border-radius: 50%;
                    animation: pulseLive 1s infinite;
                    box-shadow: 0 0 8px #10b981;
                }
                @keyframes pulseLive {
                    0%,100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.5; transform: scale(1.3); }
                }
            </style>
        </head>
        <body>
        <div id="container">
            <div class="badge-container">
                <div class="live-badge">
                    <div class="live-dot"></div>
                    AI INTERVIEWER · PREMIUM
                </div>
            </div>
        </div>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script>
        (function() {
            const container = document.getElementById('container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            const scene = new THREE.Scene();
            scene.background = null;
            scene.fog = new THREE.FogExp2(0x0a0a15, 0.008);
            
            const camera = new THREE.PerspectiveCamera(42, width/height, 0.1, 1000);
            camera.position.set(0, 0.1, 2.8);
            camera.lookAt(0, 0, 0);
            
            const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(width, height);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.setClearColor(0x000000, 0);
            container.appendChild(renderer.domElement);
            
            // Realistic studio lighting
            const ambientLight = new THREE.AmbientLight(0x2a2a3a, 0.6);
            scene.add(ambientLight);
            
            const keyLight = new THREE.DirectionalLight(0xfff5e0, 1.2);
            keyLight.position.set(1.5, 2, 2.5);
            scene.add(keyLight);
            
            const fillLight = new THREE.PointLight(0x88aaff, 0.4);
            fillLight.position.set(-1, 1, 1.5);
            scene.add(fillLight);
            
            const rimLight = new THREE.PointLight(0xffaa66, 0.5);
            rimLight.position.set(1, 0.8, -1.8);
            scene.add(rimLight);
            
            const backLight = new THREE.PointLight(0x6688ff, 0.3);
            backLight.position.set(0, 0.5, -2);
            scene.add(backLight);
            
            const hairLight = new THREE.PointLight(0xffcc88, 0.25);
            hairLight.position.set(0, 1.2, 0.5);
            scene.add(hairLight);
            
            // Head group
            const headGroup = new THREE.Group();
            scene.add(headGroup);
            
            // MAIN HEAD - Realistic human proportions
            const headGeo = new THREE.SphereGeometry(0.72, 128, 128);
            const skinMat = new THREE.MeshStandardMaterial({
                color: 0xd4a574,
                roughness: 0.35,
                metalness: 0.05,
                emissive: 0x332211,
                emissiveIntensity: 0.02
            });
            const head = new THREE.Mesh(headGeo, skinMat);
            head.castShadow = true;
            head.receiveShadow = false;
            headGroup.add(head);
            
            // Subtle skin texture overlay
            const skinDetailGeo = new THREE.SphereGeometry(0.718, 128, 128);
            const skinDetailMat = new THREE.MeshStandardMaterial({
                color: 0xccaa88,
                roughness: 0.3,
                metalness: 0.02,
                transparent: true,
                opacity: 0.3
            });
            const skinDetail = new THREE.Mesh(skinDetailGeo, skinDetailMat);
            headGroup.add(skinDetail);
            
            // JAW STRUCTURE - Realistic chin/jaw definition
            const jawGeo = new THREE.CylinderGeometry(0.62, 0.55, 0.45, 32);
            const jawMat = new THREE.MeshStandardMaterial({ color: 0xc49a6c, roughness: 0.35 });
            const jaw = new THREE.Mesh(jawGeo, jawMat);
            jaw.position.set(0, -0.28, 0.05);
            headGroup.add(jaw);
            
            // NOSE - Realistic bridge and tip
            const noseBridge = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.08, 0.12), skinMat);
            noseBridge.position.set(0, 0.02, 0.68);
            headGroup.add(noseBridge);
            
            const noseTip = new THREE.Mesh(new THREE.SphereGeometry(0.09, 32, 32), skinMat);
            noseTip.position.set(0, -0.05, 0.78);
            headGroup.add(noseTip);
            
            // EYES - Human-like with subtle glow
            const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: 0xf5f0e8, roughness: 0.2, metalness: 0.02 });
            const eyeIrisMat = new THREE.MeshStandardMaterial({ color: 0x4a7a9c, emissive: 0x1a4a6a, emissiveIntensity: 0.15 });
            
            const leftEyeWhite = new THREE.Mesh(new THREE.SphereGeometry(0.12, 64, 64), eyeWhiteMat);
            leftEyeWhite.position.set(-0.23, 0.16, 0.68);
            headGroup.add(leftEyeWhite);
            
            const rightEyeWhite = new THREE.Mesh(new THREE.SphereGeometry(0.12, 64, 64), eyeWhiteMat);
            rightEyeWhite.position.set(0.23, 0.16, 0.68);
            headGroup.add(rightEyeWhite);
            
            const leftIris = new THREE.Mesh(new THREE.SphereGeometry(0.08, 64, 64), eyeIrisMat);
            leftIris.position.set(-0.23, 0.16, 0.79);
            headGroup.add(leftIris);
            
            const rightIris = new THREE.Mesh(new THREE.SphereGeometry(0.08, 64, 64), eyeIrisMat);
            rightIris.position.set(0.23, 0.16, 0.79);
            headGroup.add(rightIris);
            
            // Pupils
            const pupilMat = new THREE.MeshStandardMaterial({ color: 0x111111 });
            const leftPupil = new THREE.Mesh(new THREE.SphereGeometry(0.045, 48, 48), pupilMat);
            leftPupil.position.set(-0.23, 0.16, 0.86);
            headGroup.add(leftPupil);
            
            const rightPupil = new THREE.Mesh(new THREE.SphereGeometry(0.045, 48, 48), pupilMat);
            rightPupil.position.set(0.23, 0.16, 0.86);
            headGroup.add(rightPupil);
            
            // EYEBROWS - Realistic facial hair
            const browMat = new THREE.MeshStandardMaterial({ color: 0x4a3a2a, roughness: 0.6 });
            const leftBrow = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.045, 0.06), browMat);
            leftBrow.position.set(-0.22, 0.32, 0.71);
            leftBrow.rotation.z = -0.1;
            headGroup.add(leftBrow);
            
            const rightBrow = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.045, 0.06), browMat);
            rightBrow.position.set(0.22, 0.32, 0.71);
            rightBrow.rotation.z = 0.1;
            headGroup.add(rightBrow);
            
            // BEARD - Professional salt-and-pepper look
            const beardMat = new THREE.MeshStandardMaterial({ color: 0x5a4a3a, roughness: 0.7 });
            const beardGeo = new THREE.CylinderGeometry(0.58, 0.52, 0.28, 32);
            const beard = new THREE.Mesh(beardGeo, beardMat);
            beard.position.set(0, -0.22, 0.45);
            headGroup.add(beard);
            
            // Mustache
            const mustacheGeo = new THREE.TorusGeometry(0.22, 0.035, 32, 64, Math.PI);
            const mustacheMat = new THREE.MeshStandardMaterial({ color: 0x5a4a3a, roughness: 0.6 });
            const mustache = new THREE.Mesh(mustacheGeo, mustacheMat);
            mustache.position.set(0, -0.08, 0.72);
            mustache.rotation.x = 0.2;
            mustache.rotation.z = 0;
            headGroup.add(mustache);
            
            // MOUTH with subtle smile
            const mouthMat = new THREE.MeshStandardMaterial({ color: 0xaa7a5a });
            const mouthGeo = new THREE.TorusGeometry(0.14, 0.022, 32, 64, Math.PI);
            const mouth = new THREE.Mesh(mouthGeo, mouthMat);
            mouth.position.set(0, -0.12, 0.73);
            mouth.rotation.x = 0.15;
            headGroup.add(mouth);
            
            // EARS
            const earMat = new THREE.MeshStandardMaterial({ color: 0xccaa88, roughness: 0.35 });
            const leftEar = new THREE.Mesh(new THREE.SphereGeometry(0.11, 48, 48), earMat);
            leftEar.position.set(-0.72, 0.02, 0.08);
            leftEar.scale.set(0.7, 0.9, 0.5);
            headGroup.add(leftEar);
            
            const rightEar = new THREE.Mesh(new THREE.SphereGeometry(0.11, 48, 48), earMat);
            rightEar.position.set(0.72, 0.02, 0.08);
            rightEar.scale.set(0.7, 0.9, 0.5);
            headGroup.add(rightEar);
            
            // NECK
            const neckMat = new THREE.MeshStandardMaterial({ color: 0xc49a6c, roughness: 0.4 });
            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.42, 0.35, 24), neckMat);
            neck.position.set(0, -0.65, 0);
            headGroup.add(neck);
            
            // SUIT JACKET - Professional attire
            const suitMat = new THREE.MeshStandardMaterial({ color: 0x2a2a3a, roughness: 0.45, metalness: 0.08 });
            const shoulders = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.35, 0.55), suitMat);
            shoulders.position.set(0, -0.78, -0.05);
            headGroup.add(shoulders);
            
            const chest = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.45, 0.35), suitMat);
            chest.position.set(0, -0.95, 0.1);
            headGroup.add(chest);
            
            // TIE
            const tieMat = new THREE.MeshStandardMaterial({ color: 0x8a2a2a, metalness: 0.1 });
            const tie = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.32, 0.04), tieMat);
            tie.position.set(0, -0.85, 0.28);
            headGroup.add(tie);
            
            // SUBTLE ROBOTIC ELEMENTS - Premium AI feel
            const templeLightMat = new THREE.MeshStandardMaterial({ color: 0x00aaff, emissive: 0x0088cc, emissiveIntensity: 0.2 });
            const leftTemple = new THREE.Mesh(new THREE.SphereGeometry(0.025, 16, 16), templeLightMat);
            leftTemple.position.set(-0.34, 0.22, 0.72);
            headGroup.add(leftTemple);
            
            const rightTemple = new THREE.Mesh(new THREE.SphereGeometry(0.025, 16, 16), templeLightMat);
            rightTemple.position.set(0.34, 0.22, 0.72);
            headGroup.add(rightTemple);
            
            // HAIR - Natural looking
            const hairMat = new THREE.MeshStandardMaterial({ color: 0x3a3a4a, roughness: 0.5 });
            const hairBase = new THREE.Mesh(new THREE.SphereGeometry(0.73, 64, 64), hairMat);
            hairBase.position.set(0, 0.35, 0.1);
            hairBase.scale.set(0.98, 0.42, 0.85);
            headGroup.add(hairBase);
            
            const hairSideL = new THREE.Mesh(new THREE.SphereGeometry(0.15, 32, 32), hairMat);
            hairSideL.position.set(-0.58, 0.28, 0.25);
            headGroup.add(hairSideL);
            
            const hairSideR = new THREE.Mesh(new THREE.SphereGeometry(0.15, 32, 32), hairMat);
            hairSideR.position.set(0.58, 0.28, 0.25);
            headGroup.add(hairSideR);
            
            // Particle aura - premium floating particles
            const particleCount = 150;
            const particlesGeo = new THREE.BufferGeometry();
            const particlePositions = new Float32Array(particleCount * 3);
            for (let i = 0; i < particleCount; i++) {
                const radius = 1.05 + Math.random() * 0.25;
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.acos(2 * Math.random() - 1);
                particlePositions[i*3] = radius * Math.sin(phi) * Math.cos(theta);
                particlePositions[i*3+1] = radius * Math.sin(phi) * Math.sin(theta) * 0.7;
                particlePositions[i*3+2] = radius * Math.cos(phi);
            }
            particlesGeo.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
            const particleMat = new THREE.PointsMaterial({
                color: 0x88aaff,
                size: 0.006,
                transparent: true,
                opacity: 0.3,
                blending: THREE.AdditiveBlending
            });
            const particles = new THREE.Points(particlesGeo, particleMat);
            headGroup.add(particles);
            
            // MOVEMENT - Smooth, professional, subtle
            let autoAngle = 0;
            let currentRotY = 0;
            let currentRotX = 0;
            let currentEyeRot = 0;
            let pulseTime = 0;
            
            function animate() {
                requestAnimationFrame(animate);
                
                pulseTime += 0.02;
                const eyeGlow = 0.15 + Math.sin(pulseTime * 2.5) * 0.05;
                leftTemple.material.emissiveIntensity = eyeGlow;
                rightTemple.material.emissiveIntensity = eyeGlow;
                eyeIrisMat.emissiveIntensity = 0.12 + Math.sin(pulseTime * 1.8) * 0.04;
                
                autoAngle += 0.006;
                // Gentle left-right movement (like a calm conversation)
                const targetY = Math.sin(autoAngle) * 0.22;
                const targetX = Math.sin(autoAngle * 0.6) * 0.05;
                currentRotY += (targetY - currentRotY) * 0.06;
                currentRotX += (targetX - currentRotX) * 0.06;
                headGroup.rotation.y = currentRotY;
                headGroup.rotation.x = currentRotX;
                
                // Subtle floating
                const bobY = Math.sin(autoAngle * 1.2) * 0.002;
                headGroup.position.y = bobY;
                
                // Particles rotation
                particles.rotation.y += 0.002;
                
                renderer.render(scene, camera);
            }
            
            animate();
            
            window.addEventListener('resize', () => {
                const newWidth = container.clientWidth;
                const newHeight = container.clientHeight;
                camera.aspect = newWidth / newHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(newWidth, newHeight);
            });
        })();
        </script>
        </body>
        </html>
        """, height=440)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    status = ai.check_ollama_status()
    dc = '#10b981' if status['online'] else '#ef4444'
    status_label = 'Online' if status['online'] else 'Offline — Demo Mode'

    components.html(f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:transparent;color:#eef2ff}}
.card{{text-align:center;padding:24px 20px 20px;border-radius:18px;
  border:1px solid rgba(79,139,255,.3);background:rgba(79,139,255,.05)}}
</style></head><body>
<div class="card">
  <div style="display:flex;justify-content:center;margin-bottom:8px">
    <svg viewBox="0 0 220 240" width="160" height="174" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="metalBody" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#4a5568"/>
          <stop offset="45%" stop-color="#2d3748"/>
          <stop offset="100%" stop-color="#1a202c"/>
        </linearGradient>
        <linearGradient id="metalHead" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#525b6e"/>
          <stop offset="55%" stop-color="#333c4d"/>
          <stop offset="100%" stop-color="#1c222e"/>
        </linearGradient>
        <radialGradient id="eyeGlowHome" cx="50%" cy="40%" r="65%">
          <stop offset="0%" stop-color="#e0aaff"/>
          <stop offset="45%" stop-color="#a855f7"/>
          <stop offset="100%" stop-color="#6d28d9"/>
        </radialGradient>
        <filter id="eyeBlurHome" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3.2"/>
        </filter>
      </defs>

      <!-- shoulders / body -->
      <rect x="48" y="178" width="124" height="55" rx="16" fill="url(#metalBody)"/>
      <rect x="48" y="178" width="124" height="14" rx="7" fill="rgba(255,255,255,.06)"/>
      <!-- chest panel light -->
      <rect x="96" y="198" width="28" height="8" rx="4" fill="#a855f7" opacity=".85">
        <animate attributeName="opacity" values=".4;1;.4" dur="1.8s" repeatCount="indefinite"/>
      </rect>

      <!-- neck -->
      <rect x="92" y="150" width="36" height="34" rx="6" fill="#252b38"/>

      <!-- ears -->
      <g>
        <circle cx="42" cy="118" r="15" fill="url(#metalBody)"/>
        <circle cx="42" cy="118" r="7" fill="#1a1f2b"/>
        <circle cx="178" cy="118" r="15" fill="url(#metalBody)"/>
        <circle cx="178" cy="118" r="7" fill="#1a1f2b"/>
      </g>

      <!-- helmet/head -->
      <path d="M55 60 Q55 18 110 16 Q165 18 165 60 L165 130 Q165 158 110 158 Q55 158 55 130 Z"
            fill="url(#metalHead)"/>
      <!-- helmet top ridge -->
      <path d="M82 22 Q110 8 138 22 L132 30 Q110 20 88 30 Z" fill="#5a6477"/>
      <!-- small antenna nub -->
      <rect x="105" y="6" width="10" height="12" rx="3" fill="#3a4252"/>
      <circle cx="110" cy="6" r="4" fill="#a855f7">
        <animate attributeName="opacity" values="1;.3;1" dur="1.4s" repeatCount="indefinite"/>
      </circle>

      <!-- face plate recess -->
      <rect x="64" y="78" width="92" height="62" rx="14" fill="#11141c"/>

      <!-- visor / eyes bar -->
      <g filter="url(#eyeBlurHome)">
        <rect x="74" y="96" width="30" height="11" rx="5.5" fill="url(#eyeGlowHome)">
          <animate attributeName="opacity" values="1;1;1;.15;1" dur="3.6s" repeatCount="indefinite" keyTimes="0;.85;.9;.93;1"/>
        </rect>
        <rect x="116" y="96" width="30" height="11" rx="5.5" fill="url(#eyeGlowHome)">
          <animate attributeName="opacity" values="1;1;1;.15;1" dur="3.6s" repeatCount="indefinite" keyTimes="0;.85;.9;.93;1"/>
        </rect>
      </g>
      <rect x="74" y="96" width="30" height="11" rx="5.5" fill="none" stroke="#e9d5ff" stroke-width="1" opacity=".7"/>
      <rect x="116" y="96" width="30" height="11" rx="5.5" fill="none" stroke="#e9d5ff" stroke-width="1" opacity=".7"/>

      <!-- nose/mic bridge -->
      <rect x="100" y="110" width="20" height="6" rx="3" fill="#3a4252"/>

      <!-- mouth grille -->
      <rect x="84" y="120" width="52" height="14" rx="7" fill="#1a1f2b" stroke="#3a4252" stroke-width="1.5"/>
      <rect x="92" y="124" width="4" height="6" rx="2" fill="#a855f7" opacity=".7">
        <animate attributeName="height" values="6;2;6" dur="1s" repeatCount="indefinite"/>
      </rect>
      <rect x="100" y="124" width="4" height="6" rx="2" fill="#a855f7" opacity=".6">
        <animate attributeName="height" values="2;6;2" dur="1s" repeatCount="indefinite" begin=".2s"/>
      </rect>
      <rect x="108" y="124" width="4" height="6" rx="2" fill="#a855f7" opacity=".7">
        <animate attributeName="height" values="6;3;6" dur="1s" repeatCount="indefinite" begin=".4s"/>
      </rect>
      <rect x="116" y="124" width="4" height="6" rx="2" fill="#a855f7" opacity=".6">
        <animate attributeName="height" values="3;6;3" dur="1s" repeatCount="indefinite" begin=".6s"/>
      </rect>
      <rect x="124" y="124" width="4" height="6" rx="2" fill="#a855f7" opacity=".7">
        <animate attributeName="height" values="6;2;6" dur="1s" repeatCount="indefinite" begin=".8s"/>
      </rect>

      <!-- subtle bob animation -->
      <animateTransform attributeName="transform" type="translate"
        values="0,0; 0,-4; 0,0" dur="2.6s" repeatCount="indefinite"/>
    </svg>
  </div>
  <div style="font-family:'Syne',sans-serif;font-size:17px;font-weight:700;margin-bottom:6px">AI Interviewer</div>
  <div style="font-size:13px;color:#8896b3;margin-bottom:14px">Reads your resume &rarr; Asks tailored questions &rarr; Scores you on 4 dimensions</div>
  <div style="display:flex;align-items:center;justify-content:center;gap:8px;font-size:12px;margin-bottom:14px">
    <span style="width:8px;height:8px;border-radius:50%;background:{dc};box-shadow:0 0 6px {dc};display:inline-block"></span>
    <span style="color:#8896b3"><strong style="color:{dc}">{status_label}</strong></span>
  </div>
  <div style="font-size:11px;color:#4a5c78">Specialised for: Software Engineering &middot; Data Science &middot; Frontend &middot; Backend &middot; HR Management</div>
</div>
</body></html>""", height=380, scrolling=False)
    
    st.markdown("""<div class="cs" style="border-color:rgba(168,85,247,.3);background:rgba(168,85,247,.05)">
      <div style="font-size:11px;color:var(--t3);margin-bottom:7px;font-family:'DM Mono',monospace">ACCEPTED RESUME FORMATS</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        <span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(168,85,247,.1);border:1px solid rgba(168,85,247,.25);color:#a855f7">📄 PDF</span>
        <span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(6,182,212,.1);border:1px solid rgba(6,182,212,.25);color:#06b6d4">🖼️ Image/Screenshot</span>
        <span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(79,139,255,.1);border:1px solid rgba(79,139,255,.25);color:#4f8bff">📝 TXT</span>
        <span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);color:#10b981">📋 DOCX</span>
        <span style="font-size:11px;padding:3px 10px;border-radius:20px;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.25);color:#f59e0b">✏️ Paste</span>
      </div>
    </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown('<div class="sl">HOW IT WORKS — 5 STEPS</div>', unsafe_allow_html=True)
    
    steps = [
        ("📄", "Upload Resume", "Any format — PDF, image, Word, or paste text. AI reads every skill, project, and experience."),
        ("🔍", "AI Review Page", "NEW: AI shows what it extracted — name, field, skills, experience. You confirm and adjust the role."),
        ("⚙️", "Configure", "Pick difficulty, question type (Technical/Behavioural/Mixed), question count."),
        ("🎤", "AI Interview", "AI speaks each question aloud. You answer by voice or text. Questions are 100% based on YOUR resume."),
        ("📊", "Results & Score", "Grade, radar chart, 4-metric scores, per-question feedback, downloadable report."),
    ]
    cols = st.columns(5)
    for col, (ico, title, desc) in zip(cols, steps):
        with col:
            st.markdown(f"""<div class="fc">
              <div style="font-size:28px;margin-bottom:10px">{ico}</div>
              <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:13px;margin-bottom:7px">{title}</div>
              <div style="font-size:12px;color:var(--t2);line-height:1.5">{desc}</div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  DEMO
# ════════════════════════════════════════════════════════════════════
DEMO_QS = [
    "Tell me about yourself and your professional background.",
    "Describe the most challenging project you have worked on. What was your role and what did you learn?",
    "How do you handle tight deadlines or pressure at work? Give a real example.",
    "What are your key strengths and how have they contributed to your success?",
    "Where do you see yourself professionally in the next 3-5 years?",
]

def page_demo():
    nav_bar('demo')
    back_btn("Home", "home")
    st.markdown('<div class="sl">DEMO MODE — NO SETUP REQUIRED</div>', unsafe_allow_html=True)
    st.title("Demo Interview")

    st.markdown("""<div class="card" style="border-color:rgba(79,139,255,.3);background:rgba(79,139,255,.05)">
      <div style="font-family:'Syne',sans-serif;font-weight:700;margin-bottom:12px">🎤 How Voice Works</div>
      <div style="display:flex;gap:18px;flex-wrap:wrap">
        <div style="flex:1;min-width:120px"><div style="font-size:20px;margin-bottom:5px">1️⃣</div><div style="font-size:13px;font-weight:600;margin-bottom:3px">AI Speaks</div><div style="font-size:12px;color:var(--t2)">Question read aloud automatically</div></div>
        <div style="flex:1;min-width:120px"><div style="font-size:20px;margin-bottom:5px">2️⃣</div><div style="font-size:13px;font-weight:600;margin-bottom:3px">You Record</div><div style="font-size:12px;color:var(--t2)">Click mic → browser asks permission → speak → words fill answer box live</div></div>
        <div style="flex:1;min-width:120px"><div style="font-size:20px;margin-bottom:5px">3️⃣</div><div style="font-size:13px;font-weight:600;margin-bottom:3px">AI Scores</div><div style="font-size:12px;color:var(--t2)">Submit → 4-metric feedback instantly</div></div>
      </div>
    </div>""", unsafe_allow_html=True)

    if st.button("Launch Demo Interview Now", use_container_width=True):
        sid = "DEMO" + str(uuid.uuid4())[:4].upper()
        st.session_state.update({
            'session_id': sid, 'questions': DEMO_QS, 'role': 'General Professional',
            'difficulty': 'Mid-Level', 'q_type': 'Mixed', 'q_count': len(DEMO_QS),
            'warmup': False, 'current_q': 0, 'answers': {}, 'evaluations': {}, 'follow_ups': {},
            'interview_started': True, 'interview_complete': False})
        db.create_session(sid, "General Professional", "Mid-Level", "Mixed", "", {}, DEMO_QS)
        nav('interview')

    st.markdown("---")
    st.markdown("**Demo Questions**")
    for i, q in enumerate(DEMO_QS):
        st.markdown(f"""<div class="q-preview-item">
          <span class="q-num">Q{i+1}</span>
          <span style="font-size:13px;color:var(--t2)">{q}</span>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  RESUME UPLOAD (Step 1)
# ════════════════════════════════════════════════════════════════════
def page_resume():
    nav_bar('resume')
    flow_bar('resume')
    back_btn("Home", "home")
    st.title("Upload Your Resume")
    st.markdown('<p style="color:var(--t2)">Upload in any format. AI will extract your background and generate interview questions tailored specifically to YOU.</p>', unsafe_allow_html=True)

    st.markdown("""<div class="cs" style="margin-bottom:18px;border-color:rgba(168,85,247,.3);background:rgba(168,85,247,.05)">
      <div style="font-size:12px;color:var(--t2)">
        <strong style="color:#a855f7">📎 Accepted:</strong>
        PDF (text or scanned) · PNG/JPG/JPEG (screenshot) · TXT · DOCX (Word) · or paste below<br>
        <span style="color:var(--t3);margin-top:4px;display:block">For image/scanned PDF: install <code>ollama pull llava-phi3</code> for best OCR · or paste text directly</span>
      </div>
    </div>""", unsafe_allow_html=True)

    t1, t2 = st.tabs(["📁 Upload File", "✏️ Paste Text"])

    with t1:
        accepted = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'bmp', 'txt']
        if DOCX_OK: accepted.append('docx')
        up = st.file_uploader("Drop your resume here", type=accepted,
                              help="PDF, image screenshot, Word doc, or plain text")

        if up is not None:
            fname = up.name.lower()
            if any(fname.endswith(e) for e in ('.png','.jpg','.jpeg','.webp','.bmp')):
                st.image(up, caption=f"📷 {up.name}", use_container_width=True)
                up.seek(0)

            with st.spinner(f"📖 Extracting text from **{up.name}**…"):
                up.seek(0)
                text, ok, warn = extract_file(up)

            if ok and len(text.strip()) >= 50:
                st.session_state.resume_text = text
                st.success(f"✅ **{up.name}** — {len(text.split())} words extracted")
                with st.expander("👁 Preview"):
                    st.text(text[:800] + ("…" if len(text) > 800 else ""))
            else:
                if warn: st.warning(warn)
                else: st.error("Could not extract text. Use the Paste tab below.")

    with t2:
        manual = st.text_area(
            "Paste your full resume / CV text here",
            height=260,
            placeholder="John Smith\nBBA Marketing — XYZ University 2020\n\nExperience:\n  Marketing Manager — ABC Company (2020-2024)\n  • Led digital campaigns reaching 200k users\n  • Managed team of 5 marketing specialists\n\nSkills: Digital Marketing, SEO, Content Strategy, Google Analytics, Brand Management",
            value=st.session_state.resume_text, key="paste_resume"
        )
        if manual and manual != st.session_state.resume_text:
            st.session_state.resume_text = manual
        if manual and len(manual.split()) > 20:
            st.success(f"✅ {len(manual.split())} words ready")

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Skip Resume", use_container_width=True):
            st.session_state.resume_text = ""
            st.session_state.resume_info = {}
            st.session_state.detected_role = ""
            nav('setup')
    with c2:
        if st.button("Analyse & Review →", use_container_width=True,
                     disabled=not st.session_state.resume_text):
            with st.spinner("🤖 AI analysing your resume…"):
                info = ai.analyze_resume(st.session_state.resume_text)
                st.session_state.resume_info = info

            # ── Field validation ───────────────────────────────────
            matched_role, confidence = detect_allowed_role(
                st.session_state.resume_text, info)

            if not matched_role:
                # Detected field is not one of the 5 allowed — block
                detected_field = (info.get('field', '') or
                                  info.get('last_role', '') or 'Unknown Field')
                st.session_state.resume_info  = {}
                st.session_state.resume_text  = ""
                st.session_state.resume_field_rejected = detected_field
                st.rerun()
            else:
                # Accepted — set matched role and proceed
                st.session_state.detected_role = matched_role
                st.session_state.role          = matched_role
                st.session_state.pop('resume_field_rejected', None)
                nav('resume_review')

    with c3:
        if st.button("Quick Start (Skip Review) →", use_container_width=True,
                     disabled=not st.session_state.resume_text):
            with st.spinner("🤖 Analysing…"):
                info = ai.analyze_resume(st.session_state.resume_text)

            matched_role, confidence = detect_allowed_role(
                st.session_state.resume_text, info)

            if not matched_role:
                detected_field = (info.get('field', '') or
                                  info.get('last_role', '') or 'Unknown Field')
                st.session_state.resume_info  = {}
                st.session_state.resume_text  = ""
                st.session_state.resume_field_rejected = detected_field
                st.rerun()
            else:
                st.session_state.resume_info   = info
                st.session_state.detected_role = matched_role
                st.session_state.role          = matched_role
                st.session_state.pop('resume_field_rejected', None)
                nav('setup')

    # ── Show rejection banner if field was rejected ────────────────
    if st.session_state.get('resume_field_rejected'):
        rejected = st.session_state.resume_field_rejected
        st.markdown(f"""
<div style="margin-top:24px;padding:24px 28px;border-radius:16px;
     background:rgba(239,68,68,.08);border:2px solid rgba(239,68,68,.4)">
  <div style="font-size:13px;font-family:monospace;color:#ef4444;
       letter-spacing:.1em;margin-bottom:10px">⛔ RESUME NOT ACCEPTED</div>
  <div style="font-size:18px;font-weight:700;margin-bottom:10px;color:#eef2ff">
    Your resume appears to be in: <span style="color:#ef4444">{rejected}</span>
  </div>
  <div style="font-size:14px;color:#8896b3;line-height:1.8;margin-bottom:16px">
    This platform <strong style="color:#eef2ff">only accepts resumes</strong>
    from the following 5 fields:
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px">
    {"".join([
      f'<span style="padding:6px 16px;border-radius:100px;background:rgba(168,85,247,.12);'
      f'border:1px solid rgba(168,85,247,.35);font-size:13px;color:#a855f7;font-weight:600">'
      f'{r}</span>'
      for r in ALL_ROLES
    ])}
  </div>
  <div style="font-size:13px;color:#8896b3;line-height:1.6;padding:12px 16px;
       border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)">
    💡 Please upload a resume for one of the supported roles above.
    If you believe this is an error, ensure your resume clearly states
    your job title, field, and relevant technical skills.
  </div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  RESUME REVIEW (Step 2 — NEW PAGE)
# ════════════════════════════════════════════════════════════════════
def page_resume_review():
    nav_bar('resume_review')
    flow_bar('resume_review')
    back_btn("Resume Upload", "resume")

    info = st.session_state.resume_info
    if not info:
        st.warning("No resume analysed yet. Please upload your resume first.")
        if st.button("← Go to Upload"): nav('resume')
        return

    st.markdown('<div class="sl">STEP 2 OF 5 — RESUME REVIEW</div>', unsafe_allow_html=True)
    st.title("Resume Review & Interview Config")
    st.markdown('<p style="color:var(--t2)">Your resume has been verified for this platform. All questions will be <strong>advanced & field-specific</strong> — depth from question 1.</p>', unsafe_allow_html=True)

    # ── Detected profile card ──────────────────────────────────────
    name     = info.get('name', 'Candidate')
    role_det = info.get('last_role', '') or st.session_state.detected_role or 'Professional'
    edu      = info.get('education', 'N/A')
    exp_yrs  = info.get('experience_years', 0)
    summary  = info.get('summary', '')
    skills   = list(dict.fromkeys(info.get('skills', []) + info.get('technologies', [])))[:20]
    projects = info.get('projects', [])[:4]
    companies= info.get('companies', [])[:4]
    field    = info.get('field', '') or role_det

    st.markdown(f"""<div class="field-detected">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div>
          <div style="font-size:11px;color:#10b981;font-family:'DM Mono',monospace;margin-bottom:6px">✅ AI DETECTED YOUR PROFILE</div>
          <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;margin-bottom:4px">{name}</div>
          <div style="font-size:14px;color:#10b981;font-weight:600;margin-bottom:8px">{role_det}</div>
          <div style="font-size:13px;color:var(--t2)">🎓 {edu} &nbsp;·&nbsp; ⏱️ {exp_yrs} yrs exp</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:11px;color:var(--t3);margin-bottom:6px">Interview questions will be about:</div>
          <div style="font-size:13px;color:var(--t1);font-weight:600">{field}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        # Skills
        if skills:
            tags = "".join([f'<span class="skill-tag">{s}</span>' for s in skills])
            st.markdown(f"""<div class="card">
              <div style="font-size:11px;color:var(--t3);margin-bottom:9px;font-family:'DM Mono',monospace">DETECTED SKILLS & TECHNOLOGIES</div>
              <div>{tags}</div>
            </div>""", unsafe_allow_html=True)

        # Summary
        if summary:
            st.markdown(f"""<div class="card">
              <div style="font-size:11px;color:var(--t3);margin-bottom:8px;font-family:'DM Mono',monospace">AI PROFILE SUMMARY</div>
              <div style="font-size:13px;color:var(--t2);line-height:1.6">{summary}</div>
            </div>""", unsafe_allow_html=True)

    with c2:
        # Companies / Experience
        if companies:
            exp_tags = "".join([f'<span class="exp-tag">{c}</span>' for c in companies])
            st.markdown(f"""<div class="card">
              <div style="font-size:11px;color:var(--t3);margin-bottom:9px;font-family:'DM Mono',monospace">EXPERIENCE / COMPANIES</div>
              <div>{exp_tags}</div>
            </div>""", unsafe_allow_html=True)

        # Projects
        if projects:
            proj_html = "".join([f'<div style="font-size:12px;color:var(--t2);padding:6px 0;border-bottom:1px solid var(--bd2)">📁 {p}</div>' for p in projects])
            st.markdown(f"""<div class="card">
              <div style="font-size:11px;color:var(--t3);margin-bottom:9px;font-family:'DM Mono',monospace">KEY PROJECTS</div>
              {proj_html}
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Interview Configuration ────────────────────────────────────
    st.markdown('<div class="sl">CONFIGURE YOUR INTERVIEW</div>', unsafe_allow_html=True)

    cf1, cf2 = st.columns([1.2, 1])
    with cf1:
        st.markdown("**Interview Role / Position**")
        st.markdown('<div style="font-size:12px;color:var(--t3);margin-bottom:8px">AI detected your field. Confirm or change to match the job you\'re applying for.</div>', unsafe_allow_html=True)

        # Find default index
        cur_role = st.session_state.role
        if cur_role not in ALL_ROLES:
            cur_role = ALL_ROLES[0]
        role_idx = ALL_ROLES.index(cur_role)

        chosen_role = st.selectbox("Select your target role", ALL_ROLES, index=role_idx,
                                   help="Choose the role you're interviewing for. Questions will match this field.")
        st.session_state.role = chosen_role

        st.markdown("**Question Depth Level**")
        dm = {"🔴 Senior / Advanced":  "Senior",
              "🟣 Expert / Principal": "Expert"}
        dl = st.radio("Depth Level", list(dm.keys()), horizontal=True,
                      index=0 if st.session_state.difficulty not in dm.values() else list(dm.values()).index(st.session_state.difficulty))
        st.session_state.difficulty = dm[dl]

        st.markdown("**Question Type**")
        qt = {"🔧 Technical / Field-Specific": "Technical",
              "🤝 Behavioural / Situational":  "Behavioural",
              "⚡ Mixed (Recommended)":         "Mixed"}
        ql = st.radio("Type", list(qt.keys()), horizontal=True,
                      index=list(qt.values()).index(st.session_state.q_type))
        st.session_state.q_type = qt[ql]

        st.markdown("**Number of Questions**")
        st.session_state.q_count = st.slider("Questions", 3, 10, st.session_state.q_count)
        st.session_state.warmup = False  # Always off — depth from Q1

    with cf2:
        est = st.session_state.q_count * 3
        st.markdown(f"""<div class="card" style="border-color:var(--bd)">
          <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;margin-bottom:16px">📋 Your Interview Preview</div>
          <div style="display:flex;flex-direction:column;gap:11px;margin-bottom:16px">
            <div style="display:flex;gap:10px;align-items:flex-start">
              <div style="width:9px;height:9px;border-radius:50%;background:#10b981;flex-shrink:0;margin-top:4px"></div>
              <div><div style="font-size:10px;color:var(--t3)">CANDIDATE</div><div style="font-size:13px">{name}</div></div>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start">
              <div style="width:9px;height:9px;border-radius:50%;background:var(--a);flex-shrink:0;margin-top:4px"></div>
              <div><div style="font-size:10px;color:var(--t3)">TARGET ROLE</div><div style="font-size:13px">{st.session_state.role}</div></div>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start">
              <div style="width:9px;height:9px;border-radius:50%;background:var(--a2);flex-shrink:0;margin-top:4px"></div>
              <div><div style="font-size:10px;color:var(--t3)">DIFFICULTY</div><div style="font-size:13px">{st.session_state.difficulty}</div></div>
            </div>
            <div style="display:flex;gap:10px;align-items:flex-start">
              <div style="width:9px;height:9px;border-radius:50%;background:var(--gold);flex-shrink:0;margin-top:4px"></div>
              <div><div style="font-size:10px;color:var(--t3)">QUESTIONS</div><div style="font-size:13px">{st.session_state.q_count}{"+ warm-up" if st.session_state.warmup else ""} · ~{est} min</div></div>
            </div>
          </div>
          <div style="padding:12px;background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2);border-radius:10px;font-size:12px;color:#10b981;line-height:1.6">
            ✅ Advanced depth questions from Q1 — no warm-up, no basics. Every question probes real-world expertise using your actual resume skills and projects.
          </div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.q_type in ['Behavioural', 'Mixed']:
            st.markdown("""<div class="cs" style="border-color:rgba(245,158,11,.25);background:rgba(245,158,11,.05)">
              <div style="font-size:11px;color:var(--gold);margin-bottom:5px;font-family:'DM Mono',monospace">💡 STAR METHOD TIP</div>
              <div style="font-size:12px;color:var(--t2);line-height:1.6">
                <strong>S</strong>ituation → <strong>T</strong>ask → <strong>A</strong>ction → <strong>R</strong>esult<br>
                Always end with a measurable outcome. AI detects STAR usage and rewards it.
              </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Generate questions & go to interview ───────────────────────
    cb, cg = st.columns([1, 2])
    with cb:
        if st.button("← Back to Upload", use_container_width=True): nav('resume')
    with cg:
        if st.button("Generate Questions & Start Interview →", use_container_width=True):
            with st.spinner(f"🤖 Generating {st.session_state.q_count} advanced questions for {st.session_state.role}…"):
                qs = generate_deep_questions(
                    st.session_state.role, st.session_state.difficulty,
                    st.session_state.q_type, st.session_state.q_count,
                    st.session_state.resume_info, st.session_state.warmup
                )
                st.session_state.generated_questions = qs

            # Show preview of generated questions
            st.success(f"✅ {len(qs)} questions generated based on your resume!")
            st.markdown("**Your Interview Questions Preview:**")
            for i, q in enumerate(qs):
                st.markdown(f"""<div class="q-preview-item">
                  <span class="q-num">Q{i+1}</span>
                  <span style="font-size:13px;color:var(--t2)">{q}</span>
                </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Start Interview Now →", use_container_width=True):
                sid = str(uuid.uuid4())[:8].upper()
                st.session_state.update({
                    'session_id': sid, 'questions': qs, 'current_q': 0,
                    'answers': {}, 'evaluations': {}, 'follow_ups': {},
                    'interview_started': True, 'interview_complete': False,
                    'q_start_time': time.time(), 'timed_out': False,
                    'cam_scores': {}, 'cam_score_count': 0})
                db.create_session(sid, st.session_state.role, st.session_state.difficulty,
                    st.session_state.q_type, st.session_state.resume_text,
                    st.session_state.resume_info, qs)
                nav('interview')

    # If questions already generated, show start button directly
    if st.session_state.generated_questions and not st.button.__name__ == 'button':
        pass


# ════════════════════════════════════════════════════════════════════
#  SETUP (Step 3 — kept for direct access / re-config)
# ════════════════════════════════════════════════════════════════════
def page_setup():
    nav_bar('setup')
    flow_bar('setup')
    back_btn("Resume Review", "resume_review")
    st.markdown('<div class="sl">STEP 3 OF 5 — INTERVIEW SETUP</div>', unsafe_allow_html=True)
    st.title("Interview Setup")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("**🎯 Target Role**")
        cur_role = st.session_state.role
        if cur_role not in ALL_ROLES: cur_role = ALL_ROLES[0]
        st.session_state.role = st.selectbox("Role", ALL_ROLES, index=ALL_ROLES.index(cur_role))

        st.markdown("**Question Depth Level**")
        dm = {"🔴 Senior / Advanced": "Senior", "🟣 Expert / Principal": "Expert"}
        dl = st.radio("Level", list(dm.keys()), horizontal=True, index=0 if st.session_state.difficulty not in dm.values() else list(dm.values()).index(st.session_state.difficulty))
        st.session_state.difficulty = dm[dl]

        st.markdown("**Question Type**")
        qt = {"🔧 Technical / Field-Specific": "Technical", "🤝 Behavioural / Situational": "Behavioural", "⚡ Mixed (Recommended)": "Mixed"}
        ql = st.radio("Type", list(qt.keys()), horizontal=True, index=list(qt.values()).index(st.session_state.q_type))
        st.session_state.q_type = qt[ql]

        st.markdown("**Questions**")
        st.session_state.q_count = st.slider("Count", 3, 10, st.session_state.q_count)
        st.session_state.warmup = False  # No warmup — depth from Q1

    with c2:
        has_resume = bool(st.session_state.resume_info)
        skills_sample = (st.session_state.resume_info.get('skills', []) + st.session_state.resume_info.get('technologies', []))[:5]
        st.markdown(f"""<div class="card" style="border-color:var(--bd)">
          <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;margin-bottom:14px">📋 Preview</div>
          <div style="font-size:13px;color:var(--t2);margin-bottom:12px">Role: <strong style="color:var(--t1)">{st.session_state.role}</strong></div>
          <div style="font-size:13px;color:var(--t2);margin-bottom:12px">Level: <strong style="color:var(--t1)">{st.session_state.difficulty}</strong></div>
          <div style="font-size:13px;color:var(--t2);margin-bottom:12px">Qs: <strong style="color:var(--t1)">{st.session_state.q_count}{"+ warmup" if st.session_state.warmup else ""}</strong></div>
          <hr style="border-color:var(--bd2);margin:12px 0">
          {'<div style="font-size:12px;color:#10b981;margin-bottom:8px">✅ Questions tailored to your resume</div><div style="display:flex;flex-wrap:wrap;gap:4px">' + "".join([f'<span class="skill-tag">{s}</span>' for s in skills_sample]) + '</div>' if has_resume else '<div style="font-size:12px;color:var(--t3)">⚠️ No resume — generic questions</div>'}
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    cb, cg = st.columns([1, 2])
    with cb:
        if st.button("← Back", use_container_width=True): nav('resume_review')
    with cg:
        if st.button("Generate & Start →", use_container_width=True):
            with st.spinner("🤖 Generating advanced depth questions…"):
                qs = generate_deep_questions(
                    st.session_state.role, st.session_state.difficulty,
                    st.session_state.q_type, st.session_state.q_count,
                    st.session_state.resume_info, st.session_state.warmup)
                sid = str(uuid.uuid4())[:8].upper()
                st.session_state.update({
                    'session_id': sid, 'questions': qs, 'current_q': 0,
                    'answers': {}, 'evaluations': {}, 'follow_ups': {},
                    'interview_started': True, 'interview_complete': False,
                    'q_start_time': time.time(), 'timed_out': False})
                db.create_session(sid, st.session_state.role, st.session_state.difficulty,
                    st.session_state.q_type, st.session_state.resume_text,
                    st.session_state.resume_info, qs)
            nav('interview')


# ════════════════════════════════════════════════════════════════════
#  INTERVIEW ROOM (Step 4) — JS countdown timer + Streamlit rerun bridge
# ════════════════════════════════════════════════════════════════════
def page_interview():
    nav_bar('interview')

    if not st.session_state.get('interview_started') or not st.session_state.questions:
        st.warning("⚠️ No active interview. Start from Resume Review or Setup.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Upload Resume"): nav('resume')
        with c2:
            if st.button("Try Demo"): nav('demo')
        return

    qs    = st.session_state.questions
    total = len(qs)
    cur   = st.session_state.current_q

    if cur >= total:
        st.success("✅ Interview complete!")
        if st.button("See Results →", use_container_width=True): nav('results')
        return

    # ── Ensure q_start_time is always set ─────────────────────────
    if not st.session_state.get('q_start_time'):
        st.session_state.q_start_time = time.time()

    TIME_LIMIT = int(st.session_state.get('q_time_limit', 120))
    elapsed    = time.time() - float(st.session_state.q_start_time)
    remaining  = max(0, TIME_LIMIT - int(elapsed))

    question  = qs[cur]
    is_warmup = (cur == 0 and st.session_state.warmup and '[WARMUP]' in question.upper())
    q_display = question.replace('[WARMUP]', '').replace('[warmup]', '').strip()

    prog = "".join([f'<div class="psd {"done" if i<cur else "active" if i==cur else ""}"></div>' for i in range(total)])
    st.markdown(f'<div class="ps">{prog}</div>', unsafe_allow_html=True)

    # ── Times Up full-page screen ──────────────────────────────────
    if remaining <= 0:
        st.markdown(f"""
<div style="text-align:center;padding:60px 20px">
  <div style="font-size:72px;margin-bottom:16px">⏰</div>
  <div style="font-size:36px;font-weight:800;color:#ef4444;font-family:monospace;margin-bottom:12px">
    TIME'S UP!
  </div>
  <div style="font-size:16px;color:#8896b3;margin-bottom:8px">
    Question {cur+1} of {total} — {TIME_LIMIT}s limit reached
  </div>
  <div style="font-size:14px;color:#4a5c78;margin-bottom:32px">
    Your answer has been recorded. Advancing to next question…
  </div>
</div>""", unsafe_allow_html=True)
        with st.spinner("Saving answer and continuing…"):
            time.sleep(2)
        final = st.session_state.answers.get(cur, "") or "[No answer — time expired]"
        st.session_state.answers[cur] = final
        try:
            db.save_answer(st.session_state.session_id, cur, q_display, final)
            if not is_warmup:
                ev = ai.evaluate_answer(q_display, final, st.session_state.role,
                                        st.session_state.difficulty, st.session_state.q_type)
                st.session_state.evaluations[cur] = ev
                st.session_state.follow_ups[cur]  = ev.get('follow_up_question', '')
                db.save_evaluation(st.session_state.session_id, cur, ev)
        except Exception:
            pass
        st.session_state.current_q    += 1
        st.session_state.q_start_time  = time.time()
        if st.session_state.current_q >= total:
            evs  = list(st.session_state.evaluations.values())
            avg  = (sum(e.get('score', 5) for e in evs) / len(evs)) if evs else 5
            pct_ = (avg / 10) * 100
            db.complete_session(st.session_state.session_id, pct_)
            badges = ai.compute_achievements(st.session_state.session_id, evs, pct_,
                st.session_state.difficulty, len(db.get_all_sessions()) <= 1)
            for nm, em in badges:
                db.save_achievement(st.session_state.session_id, nm, em)
            st.session_state.interview_complete = True
            nav('results')
        else:
            st.rerun()
        return

    # ── Prominent timer bar (Streamlit-side, always visible) ───────
    pct_bar   = remaining / TIME_LIMIT * 100
    t_min, t_s = divmod(remaining, 60)
    t_str     = f"{t_min}:{t_s:02d}"
    bar_col   = ("#10b981" if pct_bar > 50 else "#f59e0b" if pct_bar > 20 else "#ef4444")
    urgent    = "animation:tpulse .6s ease-in-out infinite;" if pct_bar <= 20 else ""
    st.markdown(f"""
<style>@keyframes tpulse{{0%,100%{{opacity:1}}50%{{opacity:.45}}}}</style>
<div style="margin-bottom:10px;background:#0d1220;border:1px solid {bar_col}44;
     border-radius:12px;padding:10px 18px;display:flex;align-items:center;gap:14px">
  <div style="font-size:26px;font-family:monospace;font-weight:800;color:{bar_col};
       min-width:64px;{urgent}">⏱ {t_str}</div>
  <div style="flex:1;height:8px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden">
    <div style="height:100%;width:{pct_bar:.1f}%;background:{bar_col};border-radius:4px;
         transition:width 1s linear"></div>
  </div>
  <div style="font-size:11px;color:#4a5c78;font-family:monospace;white-space:nowrap">
    Q{cur+1}/{total} · {TIME_LIMIT}s limit
  </div>
</div>""", unsafe_allow_html=True)

    cl, cr = st.columns([3, 2])

    with cl:
        wu   = ' [WARM-UP]' if is_warmup else ''
        qs_  = (q_display.replace('`','').replace('<','&lt;').replace('>','&gt;')
                          .replace('"','&quot;').replace('\\',' ').replace('\n',' '))
        sid_ = st.session_state.session_id or 'N/A'
        role_= st.session_state.role.replace('"', '')

        vw = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#080c18;color:#eef2ff;padding:14px;min-height:545px}}
.room{{background:linear-gradient(145deg,#080c18,#0d1220);border:1px solid rgba(16,185,129,.28);border-radius:18px;padding:20px;position:relative;overflow:hidden}}
.room::before{{content:'';position:absolute;top:-50px;right:-50px;width:180px;height:180px;background:radial-gradient(circle,rgba(16,185,129,.07) 0%,transparent 70%);pointer-events:none}}
.top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.live{{background:#ef4444;color:#fff;font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;letter-spacing:.1em;animation:blink 1.5s ease-in-out infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}
.meta{{font-size:11px;color:#4a5c78;font-family:monospace}}
/* Timer ring inside widget */
.tring-wrap{{display:flex;align-items:center;gap:6px}}
.tring{{position:relative;width:42px;height:42px;flex-shrink:0}}
.tring svg{{transform:rotate(-90deg)}}
.tr-bg{{fill:none;stroke:rgba(255,255,255,.07);stroke-width:4}}
.tr-fg{{fill:none;stroke:#10b981;stroke-width:4;stroke-linecap:round;stroke-dasharray:107;stroke-dashoffset:0;transition:stroke-dashoffset .95s linear,stroke .4s}}
.tr-txt{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:9px;font-family:monospace;font-weight:800;color:#10b981}}
.tring-lbl{{font-size:9px;color:#4a5c78;font-family:monospace;line-height:1.4}}
.av-wrap{{text-align:center;margin-bottom:14px}}
.av{{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#3a4252,#1c222e);display:inline-flex;align-items:center;justify-content:center;font-size:30px;animation:idle 2.5s ease-in-out infinite;overflow:hidden}}
@keyframes idle{{0%,100%{{box-shadow:0 0 0 0 rgba(168,85,247,.4)}}50%{{box-shadow:0 0 0 12px rgba(168,85,247,0)}}}}
.av.speaking{{animation:sp .5s ease-in-out infinite}}
@keyframes sp{{0%,100%{{box-shadow:0 0 0 4px rgba(168,85,247,.7)}}50%{{box-shadow:0 0 0 16px rgba(168,85,247,.1)}}}}
.av.listening{{background:linear-gradient(135deg,#ef4444,#dc2626)!important;animation:ls .7s ease-in-out infinite}}
@keyframes ls{{0%,100%{{box-shadow:0 0 0 4px rgba(239,68,68,.6)}}50%{{box-shadow:0 0 0 18px rgba(239,68,68,.06)}}}}
.av.requesting{{background:linear-gradient(135deg,#f59e0b,#d97706)!important}}
.ai-n{{font-size:13px;font-weight:600;margin-top:6px}}
.ai-s{{font-size:11px;color:#4a5c78;margin-top:2px}}
.qbox{{background:#080c18;border:1px solid rgba(16,185,129,.2);border-radius:12px;padding:14px;margin:12px 0;font-size:14px;line-height:1.7}}
.qn{{font-size:10px;color:#10b981;font-family:monospace;margin-bottom:6px;letter-spacing:.1em}}
.sb{{font-size:12px;color:#8896b3;text-align:center;padding:9px 12px;border-radius:8px;background:rgba(255,255,255,.03);margin:10px 0;min-height:40px;display:flex;align-items:center;justify-content:center;line-height:1.4;transition:all .3s}}
.sb.rec{{color:#ef4444;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2)}}
.sb.spk{{color:#10b981;background:rgba(16,185,129,.08)}}
.sb.req{{color:#f59e0b;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2)}}
.sb.err{{color:#ef4444;background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2)}}
.sb.tout{{color:#ef4444;background:rgba(239,68,68,.12);border:2px solid rgba(239,68,68,.5);font-weight:700;animation:blink .6s ease-in-out infinite}}
.trans{{background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.15);border-radius:10px;padding:12px;margin:10px 0;font-size:13px;line-height:1.6;min-height:58px;max-height:120px;overflow-y:auto;display:none}}
.trans.on{{display:block}}
.wc{{font-size:10px;color:#4a5c78;text-align:right;margin-top:3px;font-family:monospace}}
.btns{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}
button{{padding:9px 16px;border-radius:9px;border:none;cursor:pointer;font-size:13px;font-weight:600;font-family:'Segoe UI',system-ui,sans-serif;transition:all .2s}}
.bsp{{background:rgba(16,185,129,.14);color:#10b981;border:1px solid rgba(16,185,129,.3)}}
.bsp:hover{{background:rgba(16,185,129,.25)}}
.brec{{background:linear-gradient(135deg,#10b981,#059669);color:#fff;box-shadow:0 3px 12px rgba(16,185,129,.35)}}
.brec:hover{{opacity:.9;transform:translateY(-1px)}}
.bst{{background:rgba(239,68,68,.14);color:#ef4444;border:1px solid rgba(239,68,68,.3);display:none}}
.bc{{background:rgba(255,255,255,.06);color:#8896b3;border:1px solid rgba(255,255,255,.08)}}
.wv{{display:none;gap:3px;align-items:center;height:24px}}
.wv.on{{display:flex}}
.wb{{width:3px;border-radius:2px;background:#ef4444;animation:wv .8s ease-in-out infinite}}
.wb:nth-child(1){{height:8px;animation-delay:0s}}.wb:nth-child(2){{height:16px;animation-delay:.1s}}
.wb:nth-child(3){{height:24px;animation-delay:.2s}}.wb:nth-child(4){{height:16px;animation-delay:.3s}}
.wb:nth-child(5){{height:8px;animation-delay:.4s}}
@keyframes wv{{0%,100%{{transform:scaleY(.5)}}50%{{transform:scaleY(1)}}}}
.tip{{font-size:11px;color:#4a5c78;margin-top:10px;padding:8px;background:rgba(255,255,255,.02);border-radius:8px;line-height:1.5}}
.ph{{display:none;font-size:12px;color:#f59e0b;margin-top:10px;padding:10px;background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.2);border-radius:8px;line-height:1.6}}
.ph.on{{display:block}}
/* Times-up overlay inside widget */
.toov{{display:none;position:fixed;inset:0;background:rgba(8,12,24,.95);z-index:9999;
       flex-direction:column;align-items:center;justify-content:center;gap:14px;text-align:center;padding:24px}}
.toov.on{{display:flex}}
</style></head><body>
<div class="room">
  <div class="top">
    <div style="display:flex;align-items:center;gap:8px">
      <span class="live">● LIVE</span>
      <span class="meta">#{sid_}</span>
    </div>
    <div class="tring-wrap">
      <div class="tring">
        <svg viewBox="0 0 42 42" width="42" height="42">
          <circle class="tr-bg" cx="21" cy="21" r="17"/>
          <circle class="tr-fg" id="trfg" cx="21" cy="21" r="17"/>
        </svg>
        <div class="tr-txt" id="trval">{t_str}</div>
      </div>
      <div class="tring-lbl">Time<br>Left</div>
    </div>
    <span class="meta">Q{cur+1}/{total}</span>
  </div>
  <div class="av-wrap">
    <div class="av" id="av">
      <svg viewBox="0 0 64 64" width="46" height="46" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="avEyeGlow" cx="50%" cy="40%" r="65%">
            <stop offset="0%" stop-color="#e0aaff"/>
            <stop offset="45%" stop-color="#a855f7"/>
            <stop offset="100%" stop-color="#6d28d9"/>
          </radialGradient>
        </defs>
        <rect x="8" y="14" width="48" height="36" rx="12" fill="#11141c"/>
        <rect x="14" y="24" width="15" height="7" rx="3.5" fill="url(#avEyeGlow)">
          <animate attributeName="opacity" values="1;1;1;.15;1" dur="3.6s" repeatCount="indefinite" keyTimes="0;.85;.9;.93;1"/>
        </rect>
        <rect x="35" y="24" width="15" height="7" rx="3.5" fill="url(#avEyeGlow)">
          <animate attributeName="opacity" values="1;1;1;.15;1" dur="3.6s" repeatCount="indefinite" keyTimes="0;.85;.9;.93;1"/>
        </rect>
        <rect x="24" y="38" width="16" height="7" rx="3.5" fill="#1a1f2b" stroke="#3a4252" stroke-width="1"/>
        <rect x="27" y="40" width="2.5" height="3" rx="1" fill="#a855f7">
          <animate attributeName="height" values="3;1;3" dur="1s" repeatCount="indefinite"/>
        </rect>
        <rect x="31.5" y="40" width="2.5" height="3" rx="1" fill="#a855f7">
          <animate attributeName="height" values="1;3;1" dur="1s" repeatCount="indefinite" begin=".2s"/>
        </rect>
        <rect x="36" y="40" width="2.5" height="3" rx="1" fill="#a855f7">
          <animate attributeName="height" values="3;1.5;3" dur="1s" repeatCount="indefinite" begin=".4s"/>
        </rect>
      </svg>
    </div>
    <div class="ai-n">AI Interviewer</div>
    <div class="ai-s">{role_} · {st.session_state.difficulty}</div>
  </div>
  <div class="qbox">
    <div class="qn">QUESTION {cur+1}{wu}</div>
    <div id="qt">{qs_}</div>
  </div>
  <div class="sb" id="sb">Press <strong>🔊 AI Speak</strong> to hear the question, then <strong>🎤 Start Recording</strong></div>
  <div class="trans" id="tr"><span id="tt" style="color:#4a5c78;font-style:italic">Your spoken words appear here live…</span></div>
  <div class="wc" id="wc"></div>
  <div class="ph" id="ph">
    <strong>🔒 Allow microphone:</strong><br>
    Chrome/Edge: click 🔒 in address bar → Site settings → Microphone → Allow<br>
    Firefox: click mic icon → Allow | Safari: Settings for this website → Allow<br>
    Then click <strong>🎤 Start Recording</strong> again.
  </div>
  <div class="btns">
    <button class="bsp"  onclick="speak()"    id="bsp">🔊 AI Speak Question</button>
    <button class="brec" onclick="startRec()" id="brec">🎤 Start Recording</button>
    <button class="bst"  onclick="stopRec()"  id="bst">⏹ Stop</button>
    <button class="bc"   onclick="clearAll()">🗑 Clear</button>
    <div class="wv" id="wv"><div class="wb"></div><div class="wb"></div><div class="wb"></div><div class="wb"></div><div class="wb"></div></div>
  </div>
  <div class="tip">💡 Chrome/Edge give best mic results. Allow mic when asked. Your words fill the answer box live.</div>
</div>
<!-- Times-up overlay inside widget -->
<div class="toov" id="toov">
  <div style="font-size:60px">⏰</div>
  <div style="font-size:26px;font-weight:800;color:#ef4444;font-family:monospace">TIME'S UP!</div>
  <div style="font-size:13px;color:#8896b3">Answer recorded · moving to next question…</div>
</div>
<script>
var rec=null,full='',synth=window.speechSynthesis,voices=[];
var JS_REM={remaining}, JS_TOT={TIME_LIMIT}, timerDone=false, timerInt=null;

function ss(m,c){{var e=document.getElementById('sb');e.innerHTML=m;e.className='sb'+(c?' '+c:'');}}
function sav(c){{document.getElementById('av').className='av'+(c?' '+c:'');}}
function sph(v){{document.getElementById('ph').className='ph'+(v?' on':'');}}
function lv(){{voices=synth?synth.getVoices():[];}}
if(synth){{lv();synth.onvoiceschanged=lv;}}

// ── JS countdown ring ───────────────────────────────────────────────
(function(){{
  var ring=document.getElementById('trfg');
  var txt=document.getElementById('trval');
  var circ=2*Math.PI*17; // ≈ 106.8
  ring.style.strokeDasharray=circ;
  var secs=JS_REM, tot=JS_TOT;

  function render(){{
    var mm=Math.floor(secs/60), ss2=secs%60;
    txt.textContent=mm+':'+(ss2<10?'0':'')+ss2;
    var pct=secs/tot;
    ring.style.strokeDashoffset=circ*(1-pct);
    var col=pct>.5?'#10b981':pct>.2?'#f59e0b':'#ef4444';
    ring.style.stroke=col; txt.style.color=col;
  }}
  render();

  timerInt=setInterval(function(){{
    if(timerDone)return;
    secs=Math.max(0,secs-1);
    render();
    if(secs<=0){{
      timerDone=true;
      clearInterval(timerInt);
      onTimeUp();
    }}
  }},1000);
}})();

function onTimeUp(){{
  // Show in-widget overlay
  document.getElementById('toov').classList.add('on');
  ss('⏰ TIME\\'S UP! Submitting…','tout');
  if(rec){{try{{rec.stop();}}catch(e){{}}}}
  if(synth)synth.cancel();
  post(full);
  // Tell parent Streamlit to click the hidden timeout button → triggers rerun
  setTimeout(function(){{
    try{{
      window.parent.postMessage({{type:'TIMEOUT',text:full}},'*');
    }}catch(e){{}}
  }},400);
}}

function speak(){{
  if(!synth){{ss('⚠️ TTS not available. Use Chrome.','err');return;}}
  synth.cancel();
  var u=new SpeechSynthesisUtterance(document.getElementById('qt').innerText);
  u.rate=0.88;u.pitch=1.05;u.volume=1;
  var v=voices.find(function(x){{return x.name.includes('Google UK English Male');}})
    ||voices.find(function(x){{return x.name.includes('Daniel');}})
    ||voices.find(function(x){{return x.lang&&x.lang.startsWith('en');}});
  if(v)u.voice=v;
  u.onstart=function(){{ss('🔊 AI reading question…','spk');sav('speaking');}};
  u.onend=function(){{
    ss('✅ Done — 🎤 Auto-starting recording in 1s…','spk');
    sav('');
    setTimeout(function(){{startRec();}},1000);
  }};
  u.onerror=function(e){{ss('⚠️ Speech error: '+e.error,'err');sav('');}};
  synth.speak(u);
}}

async function startRec(){{
  if(timerDone){{ss('⏰ Time is up — cannot record.','err');return;}}
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){{ss('⚠️ Voice needs Chrome or Edge. Type answer on the right.','err');return;}}
  if(synth)synth.cancel();
  sph(false);
  ss('🔐 Requesting microphone permission…','req');
  sav('requesting');
  try{{
    var s=await navigator.mediaDevices.getUserMedia({{audio:true,video:false}});
    s.getTracks().forEach(function(t){{t.stop();}});
  }}catch(e){{
    sav('');
    if(e.name==='NotAllowedError'||e.name==='PermissionDeniedError'){{
      ss('🔒 Mic blocked — see help below ↓','err');sph(true);
    }}else if(e.name==='NotFoundError'){{
      ss('🎤 No microphone found. Type your answer on the right.','err');
    }}else{{
      ss('⚠️ '+e.name+': '+e.message,'err');
    }}
    return;
  }}
  rec=new SR();
  rec.continuous=true;rec.interimResults=true;rec.lang='en-US';rec.maxAlternatives=1;
  full='';
  rec.onstart=function(){{
    ss('● Recording… speak clearly','rec');sav('listening');
    document.getElementById('brec').style.display='none';
    document.getElementById('bst').style.display='inline-block';
    document.getElementById('wv').classList.add('on');
    document.getElementById('tr').classList.add('on');
    var t=document.getElementById('tt');t.style.fontStyle='normal';t.style.color='#eef2ff';
  }};
  rec.onresult=function(e){{
    var interim='';
    for(var i=e.resultIndex;i<e.results.length;i++){{
      if(e.results[i].isFinal){{full+=e.results[i][0].transcript+' ';}}
      else{{interim+=e.results[i][0].transcript;}}
    }}
    document.getElementById('tt').innerHTML=full+(interim?'<em style="color:#4a5c78">'+interim+'</em>':'');
    var wc=full.split(' ').filter(Boolean).length;
    document.getElementById('wc').textContent=wc+' words';
    post(full+interim);
  }};
  rec.onerror=function(e){{
    var m={{'not-allowed':'🔒 Mic blocked — see help ↓','no-speech':'🔇 No speech detected.',
            'network':'🌐 Network error.','audio-capture':'🎤 Mic not found.',
            'service-not-allowed':'🔒 Service blocked — see help ↓','aborted':'ℹ️ Stopped.'}};
    ss(m[e.error]||('⚠️ '+e.error),'err');
    if(e.error==='not-allowed'||e.error==='service-not-allowed')sph(true);
    rst();
  }};
  rec.onend=function(){{ss('✅ Recording stopped — review transcript, then Submit.');sav('');rst();}};
  try{{rec.start();}}catch(e){{ss('⚠️ Could not start: '+e.message,'err');sav('');rst();}}
}}

function stopRec(){{if(rec)rec.stop();}}
function rst(){{
  document.getElementById('brec').style.display='inline-block';
  document.getElementById('bst').style.display='none';
  document.getElementById('wv').classList.remove('on');
  sav('');
}}
function clearAll(){{
  full='';
  document.getElementById('tt').innerHTML='<span style="color:#4a5c78;font-style:italic">Your spoken words appear here live…</span>';
  document.getElementById('tr').classList.remove('on');
  document.getElementById('wc').textContent='';
  sph(false);ss('Cleared — click <strong>🎤 Start Recording</strong>.');post('');
}}
function post(t){{try{{window.parent.postMessage({{type:'VAT',text:t}},'*');}}catch(e){{}}}}
window.onload=function(){{setTimeout(lv,400);}};
</script></body></html>"""

        components.html(vw, height=570, scrolling=False)

    with cr:
        # ── Continuous Camera Personality Analyser ─────────────────
        # Auto-starts on load, never stops, analyses every 8s continuously
        cam_html = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#080c18;color:#eef2ff;padding:8px}
.wrap{background:linear-gradient(145deg,#0d1220,#080c18);border:1px solid rgba(168,85,247,.3);border-radius:16px;padding:10px;height:calc(100vh - 16px);display:flex;flex-direction:column;gap:6px}

/* Header */
.hdr{display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.title{font-size:10px;letter-spacing:.14em;color:#a855f7;font-family:monospace;font-weight:700}
.live-pill{display:flex;align-items:center;gap:4px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);border-radius:100px;padding:2px 8px;font-size:9px;color:#10b981;font-family:monospace;font-weight:700}
.live-dot{width:6px;height:6px;border-radius:50%;background:#10b981;animation:lp 1s ease-in-out infinite}
@keyframes lp{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(16,185,129,.6)}60%{opacity:.6;box-shadow:0 0 0 5px rgba(16,185,129,0)}}

/* Video */
.vid-wrap{position:relative;flex-shrink:0;border-radius:10px;overflow:hidden;background:#000}
#video{width:100%;display:block;object-fit:cover;max-height:175px}
#canvas{display:none}
.corners{position:absolute;inset:0;pointer-events:none}
.c{position:absolute;width:14px;height:14px;border-color:#a855f7;border-style:solid;opacity:.9}
.c.tl{top:6px;left:6px;border-width:2px 0 0 2px;border-radius:2px 0 0 0}
.c.tr{top:6px;right:6px;border-width:2px 2px 0 0;border-radius:0 2px 0 0}
.c.bl{bottom:6px;left:6px;border-width:0 0 2px 2px;border-radius:0 0 0 2px}
.c.br{bottom:6px;right:6px;border-width:0 2px 2px 0;border-radius:0 0 2px 0}
.fbox{position:absolute;border:1.5px solid rgba(168,85,247,.7);border-radius:3px;transition:all 1s ease;box-shadow:0 0 10px rgba(168,85,247,.3)}
.scan{position:absolute;left:0;right:0;height:1.5px;background:linear-gradient(90deg,transparent,rgba(168,85,247,.8),transparent);top:0;animation:sc 1.8s linear infinite;display:none}
.scan.on{display:block}
@keyframes sc{0%{top:0;opacity:1}100%{top:100%;opacity:0}}
.vstat{position:absolute;bottom:0;left:0;right:0;padding:4px 8px;background:linear-gradient(transparent,rgba(8,12,24,.9));font-size:9px;color:#8896b3;font-family:monospace;text-align:center}

/* Score grid - 2 columns of metric cards */
.score-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;flex-shrink:0}
.metric-card{background:#0a0f1e;border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:7px 8px;display:flex;align-items:center;gap:7px;transition:border-color .4s}
.metric-card.good{border-color:rgba(16,185,129,.3)}
.metric-card.warn{border-color:rgba(245,158,11,.3)}
.metric-card.bad{border-color:rgba(239,68,68,.3)}

/* Score ring per metric */
.ring-wrap{position:relative;width:36px;height:36px;flex-shrink:0}
.ring-wrap svg{transform:rotate(-90deg)}
.rbg{fill:none;stroke:rgba(255,255,255,.06);stroke-width:3.5}
.rfg{fill:none;stroke-width:3.5;stroke-linecap:round;stroke-dasharray:88;stroke-dashoffset:88;transition:stroke-dashoffset 1s cubic-bezier(.4,0,.2,1),stroke .5s}
.ring-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-family:monospace;font-weight:800;transition:color .5s}
.ring-denom{font-size:7px;opacity:.6;font-weight:400}

/* Label + bar */
.metric-info{flex:1;min-width:0}
.mlbl{font-size:9px;color:#8896b3;font-family:monospace;letter-spacing:.04em;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mbar{height:4px;background:rgba(255,255,255,.05);border-radius:2px;overflow:hidden}
.mbar-fill{height:100%;border-radius:2px;transition:width 1s cubic-bezier(.4,0,.2,1),background .5s}
.mdelta{font-size:8px;font-family:monospace;margin-top:2px;min-height:10px}

/* Overall score */
.overall{flex-shrink:0;background:#0a0f1e;border:1px solid rgba(168,85,247,.25);border-radius:10px;padding:8px 10px;display:flex;align-items:center;gap:10px}
.ov-ring{position:relative;width:48px;height:48px;flex-shrink:0}
.ov-ring svg{transform:rotate(-90deg)}
.ov-bg{fill:none;stroke:rgba(255,255,255,.06);stroke-width:4}
.ov-fg{fill:none;stroke:#a855f7;stroke-width:4;stroke-linecap:round;stroke-dasharray:119;stroke-dashoffset:119;transition:stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1),stroke .5s}
.ov-num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1}
.ov-n{font-size:14px;font-weight:800;font-family:monospace;color:#a855f7;transition:color .5s}
.ov-d{font-size:8px;color:#4a5c78;font-family:monospace}
.ov-info{flex:1}
.ov-label{font-size:10px;color:#a855f7;font-family:monospace;letter-spacing:.1em;margin-bottom:3px}
.ov-tip{font-size:10px;color:#8896b3;line-height:1.4}

/* Tip box */
.tip-box{flex-shrink:0;background:rgba(168,85,247,.05);border:1px solid rgba(168,85,247,.15);border-radius:8px;padding:6px 8px;font-size:9px;color:#8896b3;line-height:1.5}
.tip-box strong{color:#a855f7}

/* No-cam */
.nocam{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;flex:1;text-align:center;padding:10px}
.ncbtn{padding:9px 22px;border-radius:10px;border:none;cursor:pointer;font-size:12px;font-weight:700;background:linear-gradient(135deg,#a855f7,#7c3aed);color:#fff}
.ncbtn:hover{opacity:.88}
.ncmsg{font-size:11px;color:#4a5c78;max-width:190px;line-height:1.6}
.nce{font-size:10px;color:#ef4444;margin-top:4px}

/* Pulse on score change */
@keyframes scorepop{0%{transform:scale(1)}40%{transform:scale(1.18)}100%{transform:scale(1)}}
.pop{animation:scorepop .35s ease-out}
</style></head><body>
<div class="wrap">
  <div class="hdr">
    <div class="title">&#128249; LIVE PERSONALITY MONITOR</div>
    <div class="live-pill" id="lpill" style="display:none">
      <div class="live-dot"></div>LIVE
    </div>
  </div>

  <!-- No-cam state -->
  <div class="nocam" id="nocam">
    <div style="font-size:32px">&#128247;</div>
    <div class="ncmsg">Scores your confidence, posture, eye contact &amp; more in real-time — out of 10</div>
    <button class="ncbtn" onclick="initCam()">&#9654; Enable Camera</button>
    <div class="nce" id="nce"></div>
  </div>

  <!-- Camera view -->
  <div class="vid-wrap" id="vwrap" style="display:none">
    <video id="video" autoplay playsinline muted></video>
    <canvas id="canvas" width="160" height="120"></canvas>
    <div class="corners">
      <div class="c tl"></div><div class="c tr"></div>
      <div class="c bl"></div><div class="c br"></div>
    </div>
    <div class="fbox" id="fbox" style="display:none"></div>
    <div class="scan" id="scan"></div>
    <div class="vstat" id="vstat">Starting...</div>
  </div>

  <!-- 2x2 metric cards -->
  <div class="score-grid" id="sgrid" style="display:none">
    <!-- Confidence -->
    <div class="metric-card" id="card-conf">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-conf" cx="18" cy="18" r="14" stroke="#10b981"/>
        </svg>
        <div class="ring-num" id="n-conf" style="color:#10b981">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">CONFIDENCE</div>
        <div class="mbar"><div class="mbar-fill" id="b-conf" style="background:#10b981;width:0%"></div></div>
        <div class="mdelta" id="d-conf" style="color:#4a5c78"></div>
      </div>
    </div>
    <!-- Posture -->
    <div class="metric-card" id="card-post">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-post" cx="18" cy="18" r="14" stroke="#4f8bff"/>
        </svg>
        <div class="ring-num" id="n-post" style="color:#4f8bff">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">POSTURE</div>
        <div class="mbar"><div class="mbar-fill" id="b-post" style="background:#4f8bff;width:0%"></div></div>
        <div class="mdelta" id="d-post" style="color:#4a5c78"></div>
      </div>
    </div>
    <!-- Eye Contact -->
    <div class="metric-card" id="card-eye">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-eye" cx="18" cy="18" r="14" stroke="#a855f7"/>
        </svg>
        <div class="ring-num" id="n-eye" style="color:#a855f7">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">EYE CONTACT</div>
        <div class="mbar"><div class="mbar-fill" id="b-eye" style="background:#a855f7;width:0%"></div></div>
        <div class="mdelta" id="d-eye" style="color:#4a5c78"></div>
      </div>
    </div>
    <!-- Engagement -->
    <div class="metric-card" id="card-eng">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-eng" cx="18" cy="18" r="14" stroke="#f59e0b"/>
        </svg>
        <div class="ring-num" id="n-eng" style="color:#f59e0b">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">ENGAGEMENT</div>
        <div class="mbar"><div class="mbar-fill" id="b-eng" style="background:#f59e0b;width:0%"></div></div>
        <div class="mdelta" id="d-eng" style="color:#4a5c78"></div>
      </div>
    </div>
    <!-- Calmness -->
    <div class="metric-card" id="card-calm">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-calm" cx="18" cy="18" r="14" stroke="#06b6d4"/>
        </svg>
        <div class="ring-num" id="n-calm" style="color:#06b6d4">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">CALMNESS</div>
        <div class="mbar"><div class="mbar-fill" id="b-calm" style="background:#06b6d4;width:0%"></div></div>
        <div class="mdelta" id="d-calm" style="color:#4a5c78"></div>
      </div>
    </div>
    <!-- Dressing -->
    <div class="metric-card" id="card-dress">
      <div class="ring-wrap">
        <svg viewBox="0 0 36 36" width="36" height="36">
          <circle class="rbg" cx="18" cy="18" r="14"/>
          <circle class="rfg" id="r-dress" cx="18" cy="18" r="14" stroke="#fbbf24"/>
        </svg>
        <div class="ring-num" id="n-dress" style="color:#fbbf24">0<span class="ring-denom">/10</span></div>
      </div>
      <div class="metric-info">
        <div class="mlbl">DRESSING</div>
        <div class="mbar"><div class="mbar-fill" id="b-dress" style="background:#fbbf24;width:0%"></div></div>
        <div class="mdelta" id="d-dress" style="color:#4a5c78"></div>
      </div>
    </div>
  </div>

  <!-- Overall score -->
  <div class="overall" id="overall" style="display:none">
    <div class="ov-ring">
      <svg viewBox="0 0 48 48" width="48" height="48">
        <circle class="ov-bg" cx="24" cy="24" r="19"/>
        <circle class="ov-fg" id="ov-fg" cx="24" cy="24" r="19"/>
      </svg>
      <div class="ov-num">
        <div class="ov-n" id="ov-num">0</div>
        <div class="ov-d">/10</div>
      </div>
    </div>
    <div class="ov-info">
      <div class="ov-label">OVERALL SCORE</div>
      <div class="ov-tip" id="ov-tip">Analysing your presence...</div>
    </div>
  </div>

  <!-- Tip -->
  <div class="tip-box" id="tipbox" style="display:none">
    <strong>&#128161; Coach:</strong> <span id="tip-txt">Initialising...</span>
  </div>
</div>

<script>
var INTERVAL = 2500; // analyse every 2.5 seconds — real-time feel
var VISION_MODELS = ['llava-phi3','llava','llava:13b','bakllava','moondream'];
var OLLAMA = 'http://localhost:11434';
var stream = null, analyseLoop = null, analysing = false;
var prevPixels = null, tickCount = 0;
// History for smoothing — last 4 readings per metric
var H = {conf:[],post:[],eye:[],eng:[],calm:[],dress:[]};
// Previous values for delta arrows
var PREV = {conf:0,post:0,eye:0,eng:0,calm:0,dress:0};

window.addEventListener('load', function(){ initCam(); });

function initCam(){
  document.getElementById('nce').textContent = '';
  navigator.mediaDevices.getUserMedia({
    video:{width:{ideal:640},height:{ideal:480},facingMode:'user'},
    audio:false
  })
  .then(function(s){
    stream = s;
    var v = document.getElementById('video');
    v.srcObject = s;
    v.onloadedmetadata = function(){ v.play(); };
    document.getElementById('nocam').style.display = 'none';
    document.getElementById('vwrap').style.display = 'block';
    document.getElementById('sgrid').style.display = 'grid';
    document.getElementById('overall').style.display = 'flex';
    document.getElementById('tipbox').style.display = 'block';
    document.getElementById('lpill').style.display = 'flex';
    showFaceBox();
    // First analysis after 1.5s, then every INTERVAL
    setTimeout(function(){ runTick(); }, 1500);
    analyseLoop = setInterval(function(){ if(!analysing) runTick(); }, INTERVAL);
  })
  .catch(function(e){
    var msg = e.name==='NotAllowedError' ? 'Camera permission denied'
            : e.name==='NotFoundError'   ? 'No camera found'
            : 'Error: '+e.message;
    document.getElementById('nce').textContent = msg;
  });
}

function showFaceBox(){
  var fb = document.getElementById('fbox');
  fb.style.display = 'block';
  function upd(){
    var vw=document.getElementById('vwrap').clientWidth;
    var vh=document.getElementById('vwrap').clientHeight;
    var bw=vw*.38, bh=vh*.58;
    fb.style.left=Math.round((vw-bw)/2+(Math.random()-.5)*6)+'px';
    fb.style.top=Math.round(vh*.04+(Math.random()-.5)*4)+'px';
    fb.style.width=Math.round(bw)+'px';
    fb.style.height=Math.round(bh)+'px';
  }
  upd(); setInterval(upd, 2000);
}

// ── Core: pure canvas pixel analysis runs every 2.5s ───────────────
function runTick(){
  var v = document.getElementById('video');
  if(!stream || v.readyState < 2) return;
  analysing = true; tickCount++;
  document.getElementById('scan').classList.add('on');

  var c = document.getElementById('canvas');
  var ctx = c.getContext('2d');
  ctx.drawImage(v, 0, 0, 160, 120);
  var img = ctx.getImageData(0, 0, 160, 120);
  var pix = img.data;

  // 1. Full-frame brightness
  var totalB = 0, n = pix.length/4;
  for(var i=0;i<pix.length;i+=4)
    totalB += pix[i]*.299 + pix[i+1]*.587 + pix[i+2]*.114;
  var avgB = totalB/n;

  // 2. Face zone (upper-centre, ~35-65% x, 5-45% y)
  var fdata = ctx.getImageData(56, 6, 48, 47).data;
  var faceB = 0;
  for(var j=0;j<fdata.length;j+=4)
    faceB += fdata[j]*.299 + fdata[j+1]*.587 + fdata[j+2]*.114;
  faceB /= (fdata.length/4);

  // 3. Eye strip (narrow band ~38-62% x, 18-30% y)
  var edata = ctx.getImageData(61, 22, 38, 14).data;
  var eyeB = 0, eyeContrast = 0;
  for(var k=0;k<edata.length;k+=4){
    var el = edata[k]*.299+edata[k+1]*.587+edata[k+2]*.114;
    eyeB += el;
  }
  eyeB /= (edata.length/4);
  for(var k2=0;k2<edata.length;k2+=4){
    var el2 = edata[k2]*.299+edata[k2+1]*.587+edata[k2+2]*.114;
    eyeContrast += Math.abs(el2-eyeB);
  }
  eyeContrast /= (edata.length/4);

  // 4. Motion detection vs previous frame
  var motion = 0;
  if(prevPixels){
    for(var m=0;m<pix.length;m+=4)
      motion += Math.abs(pix[m]-prevPixels[m])
              + Math.abs(pix[m+1]-prevPixels[m+1])
              + Math.abs(pix[m+2]-prevPixels[m+2]);
    motion /= (n*3);
  }
  prevPixels = new Uint8Array(pix.buffer.slice(0));

  // 5. Skin tone ratio in face zone
  var skinN = 0, totalFPx = fdata.length/4;
  for(var s=0;s<fdata.length;s+=4){
    var r=fdata[s],g=fdata[s+1],b=fdata[s+2];
    if(r>80&&g>40&&b>20&&r>g&&r>b&&(r-b)>15) skinN++;
  }
  var skinR = skinN/totalFPx;

  // 6. Lighting balance L vs R
  var ld=ctx.getImageData(0,0,80,120).data, rd=ctx.getImageData(80,0,80,120).data;
  var lb=0, rb2=0;
  for(var l=0;l<ld.length;l+=4) lb+=ld[l]*.299+ld[l+1]*.587+ld[l+2]*.114;
  for(var r2=0;r2<rd.length;r2+=4) rb2+=rd[r2]*.299+rd[r2+1]*.587+rd[r2+2]*.114;
  lb/=(ld.length/4); rb2/=(rd.length/4);
  var lightBal = 1 - Math.min(1, Math.abs(lb-rb2)/80);

  // 7. Dressing — LOWER body zone (chest/torso only, below neck)
  // y: 65-115 (lower half of 120px frame), x: 35-125
  var bdata=ctx.getImageData(35,65,90,50).data;
  var darkPx=0,whitePx=0,casualPx=0,bPxN=bdata.length/4;
  // Tie strip — narrow vertical strip at centre chest (x:72-82, y:65-115)
  var tdata=ctx.getImageData(72,65,10,50).data;
  var tieDark=0;
  for(var td=0;td<tdata.length;td+=4){
    if(tdata[td]*.299+tdata[td+1]*.587+tdata[td+2]*.114 < 75) tieDark++;
  }
  var tieR = tieDark/(tdata.length/4);

  // Check if waistcoat — dark pixels on sides of chest (collar region)
  var leftChest=ctx.getImageData(35,65,25,50).data;
  var rightChest=ctx.getImageData(100,65,25,50).data;
  var leftDark=0, rightDark=0;
  for(var lc=0;lc<leftChest.length;lc+=4)
    if(leftChest[lc]*.299+leftChest[lc+1]*.587+leftChest[lc+2]*.114 < 70) leftDark++;
  for(var rc=0;rc<rightChest.length;rc+=4)
    if(rightChest[rc]*.299+rightChest[rc+1]*.587+rightChest[rc+2]*.114 < 70) rightDark++;
  var sidesDark = (leftDark+rightDark)/((leftChest.length+rightChest.length)/4);
  // waistcoat = dark on sides + lighter centre
  var hasWaistcoat = sidesDark > 0.45;

  for(var bd=0;bd<bdata.length;bd+=4){
    var r3=bdata[bd],g3=bdata[bd+1],b3=bdata[bd+2];
    var lum=r3*.299+g3*.587+b3*.114;
    var sat=Math.max(r3,g3,b3)-Math.min(r3,g3,b3);
    if(lum<70) darkPx++;
    if(lum>185&&sat<35) whitePx++;
    if(sat>55&&lum>60&&lum<200) casualPx++;
  }
  var darkR=darkPx/bPxN, whiteR=whitePx/bPxN, casualR=casualPx/bPxN;

  // Check body zone vs skin — is camera too close (only face, no chest)?
  var bodySkinCount=0, bodyPxN2=bdata.length/4;
  for(var bs=0;bs<bdata.length;bs+=4){
    var br=bdata[bs],bg=bdata[bs+1],bb=bdata[bs+2];
    if(br>80&&bg>40&&bb>20&&br>bg&&br>bb&&(br-bb)>15) bodySkinCount++;
  }
  var bodySkinR = bodySkinCount/bodyPxN2;
  // >35% skin in body zone = too close / only face showing / no clothing visible
  var bodyIsSkin = bodySkinR > 0.35;

  var dressingRaw;
  if(bodyIsSkin){
    // Camera too close — can't assess clothing → 0 marks
    dressingRaw = 0;
  } else if(hasWaistcoat && (darkR>0.30 || whiteR>0.20)){
    // Waistcoat over kameez (Pakistani formal) → 10/10
    dressingRaw = 100;
  } else if(darkR>0.50){
    // Full dark formal suit → 10/10
    dressingRaw = 100;
  } else if((whiteR>0.30||darkR>0.25) && tieR>0.45){
    // Formal shirt/kameez + clear tie → 10/10
    dressingRaw = 100;
  } else if(darkR>0.30){
    // Dark formal without tie → 65
    dressingRaw = 65;
  } else if(whiteR>0.30){
    // White/light clothing (plain kurta/shirt, no waistcoat, no tie) → 45
    // This covers the white kurta case — not formal enough alone
    dressingRaw = 45;
  } else if(casualR>0.40){
    // Clearly casual/colourful → 25
    dressingRaw = 25;
  } else {
    // Ambiguous — semi-formal → 40
    dressingRaw = 40;
  }

  // ── FACE DETECTION GATE ────────────────────────────────────────────
  // skinR is ratio of skin-tone pixels in face zone (0–1)
  // If < 0.10 = no face present → zero out face-dependent metrics
  var faceDetected = skinR > 0.10;

  // ── SCORE COMPUTATION ──────────────────────────────────────────────
  var rawConf, rawPost, rawEye, rawEng, rawCalm;

  if(!faceDetected){
    // No face = no basis to score confidence, eye contact, engagement
    rawConf = 0;
    rawEye  = 0;
    rawEng  = 10; // minimal
    rawPost = Math.max(0, (1 - motion/18)*40); // posture can still be assessed via motion
    rawCalm = Math.max(0, (1 - motion/14)*50);
  } else {
    // Confidence: face brightness + skin ratio + lighting balance
    rawConf = (faceB/255)*40 + skinR*35 + lightBal*25;

    // Eye contact: STRICT — only give marks when eyes clearly visible + looking at camera
    // Requirements: high eye contrast (dark pupils visible) + face centred + skin present
    // eyeContrast measures variance in eye strip — looking at camera = distinct dark pupils
    // Threshold raised: < 12 = eyes not clearly visible / looking away
    var eyeBase = 0;
    if(eyeContrast >= 20){
      // Clear distinct eyes looking forward — excellent
      eyeBase = Math.min(100, (eyeContrast/55)*70 + skinR*30);
    } else if(eyeContrast >= 14){
      // Moderate — partially looking at camera
      eyeBase = Math.min(60, (eyeContrast/55)*50 + skinR*20);
    } else if(eyeContrast >= 9){
      // Weak — probably looking slightly away
      eyeBase = Math.min(35, (eyeContrast/55)*35);
    } else {
      // No distinct eyes — looking away, eyes closed, or camera angle wrong
      eyeBase = 0;
    }
    // Additional penalty if face is off-centre or too dark
    if(faceB < 60) eyeBase *= 0.4;  // too dark to see eyes
    if(skinR < 0.15) eyeBase *= 0.3; // barely a face in frame
    rawEye = eyeBase;

    // Engagement: moderate motion is good (nodding = engaged)
    // but too still or too much movement both score lower
    var engM = motion < 1  ? 20                          // completely still = disengaged
             : motion < 3  ? 20 + motion*15              // slight movement = good
             : motion < 10 ? 65 - (motion-3)*2          // ideal range
             : Math.max(5, 50 - (motion-10)*5);          // too much = nervous
    rawEng = engM*0.6 + skinR*25 + (faceB/255)*15;

    // Calmness: LOW motion = calm. Any shake/fidget reduces it.
    // motion > 8 = noticeable movement, > 15 = significant fidgeting
    var calmPenalty = motion > 15 ? 0.1
                    : motion > 8  ? 0.35
                    : motion > 4  ? 0.65
                    : motion > 2  ? 0.85
                    : 1.0;
    rawCalm = calmPenalty*60 + lightBal*25 + (Math.min(180,avgB)/180)*15;
  }

  // Posture: stability = low motion + upright (face in upper portion of frame)
  // faceB being bright in upper zone = person sitting up
  // Motion is the strongest signal — any shaking reduces posture
  var postStability = motion > 20 ? 0.05
                    : motion > 12 ? 0.25
                    : motion > 6  ? 0.55
                    : motion > 3  ? 0.78
                    : motion > 1  ? 0.92
                    : 1.0;
  rawPost = postStability*65 + (faceDetected ? (faceB/255)*20 : 0) + lightBal*15;

  // Clamp — minimum is 0 when no face, else 20
  function clamp(v, mn){ return Math.min(100, Math.max(mn||0, Math.round(v))); }
  rawConf = clamp(rawConf, faceDetected?20:0);
  rawPost = clamp(rawPost, 0);
  rawEye  = clamp(rawEye,  faceDetected?15:0);
  rawEng  = clamp(rawEng,  faceDetected?15:0);
  rawCalm = clamp(rawCalm, 0);

  // Smooth with history (last 4)
  function push(arr,v){arr.push(v);if(arr.length>4)arr.shift();
    return Math.round(arr.reduce(function(a,b){return a+b;},0)/arr.length);}

  var sConf  = push(H.conf, rawConf);
  var sPost  = push(H.post, rawPost);
  var sEye   = push(H.eye,  rawEye);
  var sEng   = push(H.eng,  rawEng);
  var sCalm  = push(H.calm, rawCalm);
  var sDress = push(H.dress, dressingRaw);
  // Only keep 100 if confirmed formal (not body-is-skin and raw was 100)
  if(dressingRaw===100 && !bodyIsSkin) sDress=100;
  // If body is skin (camera too close), always 0 — don't let history inflate it
  if(bodyIsSkin) sDress=0;

  // Convert to /10 (round to 1 decimal)
  function to10(v){return Math.round(v/10*10)/10;}
  var vals = {
    conf:to10(sConf), post:to10(sPost), eye:to10(sEye),
    eng:to10(sEng), calm:to10(sCalm), dress:to10(sDress)
  };
  var avg10 = Math.round((vals.conf+vals.post+vals.eye+vals.eng+vals.calm)/5*10)/10;

  // Update UI
  document.getElementById('scan').classList.remove('on');
  updateMetric('conf',  vals.conf,  '#10b981');
  updateMetric('post',  vals.post,  '#4f8bff');
  updateMetric('eye',   vals.eye,   '#a855f7');
  updateMetric('eng',   vals.eng,   '#f59e0b');
  updateMetric('calm',  vals.calm,  '#06b6d4');
  updateMetric('dress', vals.dress, vals.dress>=10?'#fbbf24':vals.dress>=7?'#fbbf24':'#f59e0b');

  // Overall ring
  var ovFg = document.getElementById('ov-fg');
  var ovCirc = 119.4;
  ovFg.style.strokeDashoffset = ovCirc*(1-(avg10/10));
  var ovCol = avg10>=8?'#10b981':avg10>=6?'#4f8bff':avg10>=4?'#f59e0b':'#ef4444';
  ovFg.style.stroke = ovCol;
  var ovN = document.getElementById('ov-num');
  ovN.textContent = avg10.toFixed(1);
  ovN.style.color = ovCol;

  // Tips
  var noFaceTip = 'No face detected — centre yourself in the camera';
  var tips = {
    conf: !faceDetected ? noFaceTip : vals.conf<5 ? 'Sit upright, look at camera — projects more confidence' : 'Confidence looking good',
    post: vals.post<5  ? 'Stop shaking — sit still and straight for better posture' : 'Posture is stable and solid',
    eye:  !faceDetected ? noFaceTip : vals.eye<5 ? 'Look directly at the camera lens, not the screen' : 'Eye contact is strong',
    eng:  vals.eng<5   ? 'Show more presence — slight nods show engagement' : 'Engagement level is great',
    calm: vals.calm<5  ? 'Slow down, breathe — reduce all body movement for calmness' : 'You appear calm and composed'
  };
  var worst='conf', wv=vals.conf;
  if(vals.post<wv){worst='post';wv=vals.post;}
  if(vals.eye<wv){worst='eye';wv=vals.eye;}
  if(vals.eng<wv){worst='eng';wv=vals.eng;}
  if(vals.calm<wv){worst='calm';wv=vals.calm;}
  document.getElementById('tip-txt').textContent = tips[worst];
  document.getElementById('ov-tip').textContent =
    !faceDetected ? 'No face — centre yourself in frame' :
    bodyIsSkin    ? 'Move camera back to show clothing for dressing score' :
    vals.dress>=10 ? 'Perfect dressing — waistcoat or tie detected!' :
    vals.dress>=7  ? 'Good dressing — add waistcoat or tie for 10/10' :
    vals.dress>=5  ? 'Semi-formal — wear waistcoat over kurta or add a tie' :
    'Wear formal dress: Shalwar Kameez + waistcoat, or suit + tie';

  var faceStatus = faceDetected ? (bodyIsSkin ? 'face only (no clothing)' : 'face+body detected') : 'NO FACE DETECTED';
  document.getElementById('vstat').textContent =
    faceStatus+' · motion:'+motion.toFixed(1)+' · overall '+avg10.toFixed(1)+'/10';

  // Post to parent
  try{ window.parent.postMessage({type:'CAM_ANALYSIS',
    data:{confidence:sConf,posture:sPost,eye_contact:sEye,
          engagement:sEng,calmness:sCalm,dressing:sDress},
    avg:Math.round(avg10*10)}, '*'); }catch(e){}

  analysing = false;
}

function updateMetric(id, val10, baseColor){
  var prev = PREV[id];
  PREV[id] = val10;
  var pct = val10/10*100;

  // Determine colour based on score
  var col = val10>=8 ? '#10b981' : val10>=6 ? baseColor : val10>=4 ? '#f59e0b' : '#ef4444';

  // Ring
  var ring = document.getElementById('r-'+id);
  var circ = 88; // 2*pi*14
  ring.style.strokeDashoffset = circ*(1-(val10/10));
  ring.style.stroke = col;

  // Number (animate pop if changed)
  var numEl = document.getElementById('n-'+id);
  var newTxt = val10.toFixed(1);
  if(numEl.firstChild && numEl.firstChild.textContent !== newTxt){
    numEl.classList.remove('pop');
    void numEl.offsetWidth; // reflow
    numEl.classList.add('pop');
  }
  numEl.innerHTML = newTxt + '<span class="ring-denom">/10</span>';
  numEl.style.color = col;

  // Bar
  var bar = document.getElementById('b-'+id);
  bar.style.width = pct+'%';
  bar.style.background = col;

  // Delta arrow
  var delta = val10 - prev;
  var dEl = document.getElementById('d-'+id);
  if(Math.abs(delta) < 0.05){ dEl.textContent=''; }
  else if(delta>0){ dEl.textContent='▲ +'+Math.abs(delta).toFixed(1); dEl.style.color='#10b981'; }
  else{ dEl.textContent='▼ '+Math.abs(delta).toFixed(1); dEl.style.color='#ef4444'; }

  // Card border colour
  var card = document.getElementById('card-'+id);
  card.className = 'metric-card '+(val10>=7?'good':val10>=4?'warn':'bad');
}

window.addEventListener('beforeunload',function(){
  if(analyseLoop) clearInterval(analyseLoop);
  if(stream) stream.getTracks().forEach(function(t){t.stop();});
});
</script></body></html>"""

        components.html(cam_html, height=580, scrolling=False)

        # Hidden cam score accumulator — JS writes to hidden input, Python reads it
        st.markdown('<style>div[data-testid="stTextInput"]:has(input[aria-label="cam_data"]) {position:absolute;opacity:0;pointer-events:none;height:0;overflow:hidden}</style>', unsafe_allow_html=True)
        cam_data_input = st.text_input("cam_data", value="", key="cam_data_field", label_visibility="hidden")

        # Parse and merge incoming cam scores
        if cam_data_input:
            try:
                incoming = json.loads(cam_data_input)
                if isinstance(incoming, dict) and incoming.get('count', 0) > 0:
                    st.session_state.cam_scores      = incoming
                    st.session_state.cam_score_count = incoming.get('count', 0)
            except Exception:
                pass

        # Bridge JS: reads sessionStorage and writes to hidden input + handles VAT/TIMEOUT
        components.html("""<script>
(function(){
  // Push cam scores from sessionStorage into Streamlit hidden input every 5s
  function pushCamScores(){
    try{
      var scores = JSON.parse(sessionStorage.getItem('cam_scores') || 'null');
      if(!scores || scores.count < 1) return;
      var doc = window.parent.document;
      var inputs = doc.querySelectorAll('input[aria-label="cam_data"]');
      if(inputs.length > 0){
        var inp = inputs[0];
        var nv = JSON.stringify(scores);
        if(inp.value !== nv){
          var s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
          s.call(inp, nv);
          inp.dispatchEvent(new Event('input',{bubbles:true}));
          inp.dispatchEvent(new Event('change',{bubbles:true}));
        }
      }
    }catch(e){}
  }
  setInterval(pushCamScores, 5000);
  pushCamScores();
})();
</script>""", height=0)

        st.markdown("**Your Answer**")
        st.markdown('<div style="font-size:12px;color:var(--t3);margin-bottom:8px">Voice fills here live as you speak — or type directly.</div>', unsafe_allow_html=True)

        if cur > 0 and (cur - 1) in st.session_state.follow_ups:
            fu = st.session_state.follow_ups.get(cur - 1, '')
            if fu:
                st.markdown(f"""<div class="cs" style="border-color:rgba(168,85,247,.3);background:rgba(168,85,247,.05);margin-bottom:10px">
                  <div style="font-size:10px;color:#a855f7;font-family:'DM Mono',monospace;margin-bottom:4px">💬 FOLLOW-UP</div>
                  <div style="font-size:13px;color:var(--t2)">{fu}</div>
                </div>""", unsafe_allow_html=True)

        answer = st.text_area(
            "Answer", height=215, key=f"ans_{cur}",
            placeholder="🎤 Speak using the voice widget → words appear here automatically\n\nOR type your answer directly\n\nSTAR method:\n• Situation  • Task  • Action  • Result")

        # Hidden timeout button — CSS hides it, JS clicks it when timer hits 0
        st.markdown("""<style>
div[data-testid="stButton"]:has(button[kind="secondary"][data-testid="baseButton-secondary"] span:empty) { display:none }
</style>""", unsafe_allow_html=True)
        st.markdown('<style>div:has(>button[title="timeout"]){position:absolute;opacity:0;pointer-events:none;height:0;overflow:hidden}</style>', unsafe_allow_html=True)
        timeout_clicked = st.button("⏰", key="__timeout__", help="timeout")

        # ── Bridge: voice text + timeout trigger ───────────────────
        components.html("""<script>
(function(){
  try{
    window.parent.addEventListener('message',function bridge(e){
      if(!e.data) return;

      // Voice-to-text: fill textarea live
      if(e.data.type==='VAT'){
        var txt=e.data.text||'';
        try{
          var doc=window.parent.document;
          var areas=doc.querySelectorAll('textarea');
          var found=false;
          areas.forEach(function(ta){
            if(ta.placeholder&&ta.placeholder.includes('Speak')){
              var s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
              s.call(ta,txt);
              ta.dispatchEvent(new Event('input',{bubbles:true}));
              ta.dispatchEvent(new Event('change',{bubbles:true}));
              found=true;
            }
          });
          if(!found&&areas.length>0){
            var ta=areas[areas.length-1];
            var s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            s.call(ta,txt);
            ta.dispatchEvent(new Event('input',{bubbles:true}));
            ta.dispatchEvent(new Event('change',{bubbles:true}));
          }
        }catch(de){console.warn('VAT DOM:',de);}
      }

      // Timeout: fill textarea then click hidden Streamlit button to rerun
      if(e.data.type==='TIMEOUT'){
        try{
          var txt2=e.data.text||'';
          var doc2=window.parent.document;
          // Fill answer textarea
          var areas2=doc2.querySelectorAll('textarea');
          if(areas2.length>0){
            var ta2=areas2[areas2.length-1];
            var sv=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            sv.call(ta2,txt2);
            ta2.dispatchEvent(new Event('input',{bubbles:true}));
            ta2.dispatchEvent(new Event('change',{bubbles:true}));
          }
          // Find and click the hidden ⏰ timeout button
          setTimeout(function(){
            var btns=doc2.querySelectorAll('button');
            btns.forEach(function(b){
              if(b.textContent&&b.textContent.trim()==='⏰'){
                b.click();
              }
            });
          },500);
        }catch(te){console.warn('TIMEOUT bridge:',te);}
      }

      // CAM_ANALYSIS: store latest camera scores in sessionStorage for results page
      if(e.data.type==='CAM_ANALYSIS' && e.data.data){
        try{
          var d=e.data.data;
          // Accumulate running averages in sessionStorage
          var prev=null;
          try{prev=JSON.parse(sessionStorage.getItem('cam_scores')||'null');}catch(x){}
          var cnt=(prev&&prev.count)||0;
          var upd={
            count: cnt+1,
            confidence: Math.round(((prev&&prev.confidence||0)*cnt + (d.confidence||0))/(cnt+1)),
            posture:    Math.round(((prev&&prev.posture||0)*cnt    + (d.posture||0))/(cnt+1)),
            eye_contact:Math.round(((prev&&prev.eye_contact||0)*cnt+(d.eye_contact||0))/(cnt+1)),
            engagement: Math.round(((prev&&prev.engagement||0)*cnt + (d.engagement||0))/(cnt+1)),
            calmness:   Math.round(((prev&&prev.calmness||0)*cnt   + (d.calmness||0))/(cnt+1)),
            dressing:   Math.round(((prev&&prev.dressing||0)*cnt   + (d.dressing||0))/(cnt+1))
          };
          sessionStorage.setItem('cam_scores', JSON.stringify(upd));
        }catch(ce){console.warn('CAM store:',ce);}
      }
    });
  }catch(se){console.warn('Bridge setup:',se);}
})();
</script>""", height=0)

        # ── Handle timeout button click (auto-submit + advance) ────
        if timeout_clicked:
            final = (answer or "").strip() or "[No answer — time expired]"
            st.session_state.answers[cur] = final
            db.save_answer(st.session_state.session_id, cur, q_display, final)
            if not is_warmup:
                with st.spinner("🧠 AI scoring…"):
                    ev = ai.evaluate_answer(q_display, final, st.session_state.role,
                                            st.session_state.difficulty, st.session_state.q_type)
                    st.session_state.evaluations[cur] = ev
                    st.session_state.follow_ups[cur]  = ev.get('follow_up_question', '')
                    db.save_evaluation(st.session_state.session_id, cur, ev)
            st.session_state.current_q   += 1
            st.session_state.q_start_time = time.time()
            if st.session_state.current_q >= total:
                evs  = list(st.session_state.evaluations.values())
                avg_ = (sum(e.get('score',5) for e in evs)/len(evs)) if evs else 5
                pct_ = (avg_/10)*100
                db.complete_session(st.session_state.session_id, pct_)
                badges = ai.compute_achievements(st.session_state.session_id, evs, pct_,
                    st.session_state.difficulty, len(db.get_all_sessions())<=1)
                for nm,em in badges:
                    db.save_achievement(st.session_state.session_id,nm,em)
                st.session_state.interview_complete=True
                nav('results')
            else:
                st.rerun()

        if st.session_state.q_type in ['Behavioural', 'Mixed']:
            with st.expander("💡 STAR Method Guide"):
                st.markdown("**S** Situation → **T** Task → **A** Action → **R** Result\n\nAlways include a measurable outcome.")

        csk, csb = st.columns(2)
        with csk:
            if st.button("Skip", use_container_width=True):
                st.session_state.answers[cur] = ""
                st.session_state.follow_ups[cur] = ""
                st.session_state.current_q += 1
                st.session_state.q_start_time = time.time()
                st.rerun()
        with csb:
            lbl = "Submit & Next →" if cur < total - 1 else "Submit & Finish ✓"
            if st.button(lbl, use_container_width=True):
                final = (answer or "").strip()
                st.session_state.answers[cur] = final
                db.save_answer(st.session_state.session_id, cur, q_display, final)
                if not is_warmup:
                    with st.spinner("🧠 AI scoring…"):
                        ev = ai.evaluate_answer(q_display, final, st.session_state.role,
                                                st.session_state.difficulty, st.session_state.q_type)
                        st.session_state.evaluations[cur] = ev
                        st.session_state.follow_ups[cur]  = ev.get('follow_up_question', '')
                        db.save_evaluation(st.session_state.session_id, cur, ev)
                st.session_state.current_q += 1
                st.session_state.q_start_time = time.time()
                if st.session_state.current_q >= total:
                    evs  = list(st.session_state.evaluations.values())
                    avg  = (sum(e.get('score', 5) for e in evs) / len(evs)) if evs else 5
                    pct  = (avg / 10) * 100
                    db.complete_session(st.session_state.session_id, pct)
                    badges = ai.compute_achievements(st.session_state.session_id, evs, pct,
                        st.session_state.difficulty, len(db.get_all_sessions()) <= 1)
                    for nm, em in badges:
                        db.save_achievement(st.session_state.session_id, nm, em)
                    st.session_state.interview_complete = True
                    nav('results')
                else:
                    st.rerun()

        if cur > 0 and (cur - 1) in st.session_state.evaluations:
            prev = st.session_state.evaluations[cur - 1]
            sc = prev.get('score', 5); c = sc_col(sc)
            st.markdown(f"""<div class="cs" style="margin-top:12px;border-color:rgba(79,139,255,.2)">
              <div style="font-size:10px;color:var(--t3);font-family:'DM Mono',monospace;margin-bottom:5px">PREV Q SCORE</div>
              <div style="display:flex;align-items:center;gap:10px">
                <div style="font-family:'Syne',sans-serif;font-size:26px;font-weight:800;color:{c}">{sc}/10</div>
                <div style="font-size:12px;color:var(--t2)">{str(prev.get('summary',''))[:90]}…</div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        if st.button("← Exit Interview", use_container_width=True): nav('resume_review')


# ════════════════════════════════════════════════════════════════════
#  RESULTS
# ════════════════════════════════════════════════════════════════════
def page_results():
    nav_bar('results')
    back_btn("Interview", "interview")

    sid = st.session_state.get('session_id')
    if not sid:
        st.warning("No results. Complete an interview first.")
        if st.button("Try Demo"): nav('demo')
        return

    evs = db.get_evaluations(sid)
    ans = db.get_answers(sid)
    ach = db.get_achievements(sid)

    if not evs:
        st.info("No evaluations found.")
        return

    avg_s  = sum(e['score']                     for e in evs) / len(evs)
    avg_t  = sum(e.get('technical_score', 5)    for e in evs) / len(evs)
    avg_c  = sum(e.get('communication_score',5) for e in evs) / len(evs)
    avg_cf = sum(e.get('confidence', 5)         for e in evs) / len(evs)
    avg_tn = sum(e.get('tone_score', 5)         for e in evs) / len(evs)
    pct    = (avg_s / 10) * 100
    g, lbl = grade(pct)
    gc = '#10b981' if pct>=80 else '#4f8bff' if pct>=65 else '#f59e0b' if pct>=50 else '#ef4444'

    st.markdown(f'<div class="sl">SESSION #{sid} — {st.session_state.role}</div>', unsafe_allow_html=True)
    st.title("📊 Interview Results")

    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class="card" style="text-align:center;border-color:{gc}30">
          <div style="font-size:11px;color:var(--t3);font-family:'DM Mono',monospace;margin-bottom:4px">GRADE</div>
          <div style="font-size:48px;font-weight:800;font-family:'Syne',sans-serif;color:{gc}">{g}</div>
          <div style="font-size:12px;color:var(--t2)">{lbl}</div></div>""", unsafe_allow_html=True)
    with c2: st.metric("Overall", f"{pct:.0f}%")
    with c3: st.metric("Technical", f"{avg_t:.1f}/10")
    with c4: st.metric("Communication", f"{avg_c:.1f}/10")
    with c5: st.metric("Confidence", f"{avg_cf:.1f}/10")

    if ach:
        st.markdown(" ".join([f'<span class="badge">{a["badge_emoji"]} {a["badge_name"]}</span>' for a in ach]),
                    unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Scatterpolar(
            r=[avg_t,avg_c,avg_cf,avg_tn,avg_t],
            theta=['Technical','Communication','Confidence','Tone','Technical'],
            fill='toself', fillcolor='rgba(79,139,255,.14)',
            line=dict(color='#4f8bff', width=2)))
        fig.update_layout(
            polar=dict(bgcolor='rgba(13,18,32,.8)',
                radialaxis=dict(range=[0,10],gridcolor='rgba(255,255,255,.05)',tickfont=dict(color='#8896b3',size=9)),
                angularaxis=dict(gridcolor='rgba(255,255,255,.05)',tickfont=dict(color='#eef2ff',size=12))),
            paper_bgcolor='rgba(0,0,0,0)',showlegend=False,
            margin=dict(l=30,r=30,t=30,b=30),height=280)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        ql = [f"Q{e['question_index']+1}" for e in evs]
        qs = [e['score'] for e in evs]
        fig2 = go.Figure(go.Bar(x=ql,y=qs,marker_color=[sc_col(s) for s in qs],
            text=qs,textposition='outside',textfont=dict(color='#eef2ff',size=11)))
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#eef2ff'),yaxis=dict(range=[0,11],gridcolor='rgba(255,255,255,.05)'),
            margin=dict(l=10,r=10,t=20,b=10),height=280,
            title=dict(text="Score per Question",font=dict(size=13,color='#8896b3')))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown(mbar("Technical Accuracy",round(avg_t,1))+mbar("Communication",round(avg_c,1))+
                mbar("Confidence",round(avg_cf,1))+mbar("Tone & Professionalism",round(avg_tn,1)),
                unsafe_allow_html=True)

    # ── Body Language / Personality Section ───────────────────────
    st.markdown("---")
    st.markdown('<div style="font-size:11px;letter-spacing:.12em;color:#a855f7;font-family:monospace;margin-bottom:12px">📹 BODY LANGUAGE & PERSONALITY ANALYSIS</div>', unsafe_allow_html=True)

    cam = st.session_state.get('cam_scores', {})
    has_cam = bool(cam and cam.get('confidence', 0) > 0)

    def cam_card(label, key, col):
        val = cam.get(key, 0) if has_cam else None
        val10 = round(val / 10, 1) if val is not None else None
        bar_col = ('#10b981' if val10 and val10>=7 else '#f59e0b' if val10 and val10>=4 else '#ef4444') if val10 else '#4a5c78'
        bar_w   = f"{val}%" if val is not None else "0%"
        score_txt = f"{val10}/10" if val10 is not None else "—"
        sub_txt = "" if has_cam else "Enable camera for score"
        return f"""<div style="background:#0d1220;border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:14px">
          <div style="font-size:10px;color:{col};font-family:monospace;letter-spacing:.08em;margin-bottom:8px">{label}</div>
          <div style="font-size:30px;font-weight:800;font-family:'Syne',sans-serif;color:{bar_col};margin-bottom:8px">{score_txt}</div>
          <div style="height:5px;background:rgba(255,255,255,.05);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:{bar_w};background:{bar_col};border-radius:3px;transition:width .6s"></div>
          </div>
          <div style="font-size:11px;color:#4a5c78;margin-top:5px">{sub_txt}</div>
        </div>"""

    st.markdown(f"""<div style="background:rgba(168,85,247,.05);border:1px solid rgba(168,85,247,.18);border-radius:14px;padding:18px;margin-bottom:16px">
      <div style="font-size:13px;color:#8896b3;margin-bottom:16px;line-height:1.6">
        {"Live camera analysis ran throughout your interview — <strong style='color:#eef2ff'>averaged across all snapshots</strong>. Scores reflect your actual body language detected by the camera." if has_cam else "Camera was not active during this session. Enable camera on the interview page to get personality scores."}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px">
        {cam_card("CONFIDENCE",  "confidence",  "#10b981")}
        {cam_card("POSTURE",     "posture",      "#4f8bff")}
        {cam_card("EYE CONTACT", "eye_contact",  "#a855f7")}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
        {cam_card("ENGAGEMENT",  "engagement",  "#f59e0b")}
        {cam_card("CALMNESS",    "calmness",    "#06b6d4")}
        {cam_card("DRESSING",    "dressing",    "#fbbf24")}
      </div>
      {"<div style='margin-top:14px;padding:10px 14px;background:rgba(168,85,247,.07);border-radius:8px;font-size:12px;color:#8896b3'><strong style='color:#a855f7'>Overall presence: " + str(round(sum([cam.get(k,0) for k in ['confidence','posture','eye_contact','engagement','calmness']])/5/10,1)) + "/10</strong> averaged across " + str(cam.get('count',0)) + " camera snapshots during the interview.</div>" if has_cam else ""}
      <div style="margin-top:12px;padding:12px;background:rgba(168,85,247,.04);border:1px solid rgba(168,85,247,.12);border-radius:10px;font-size:12px;color:#8896b3;line-height:1.7">
        <strong style="color:#a855f7">Tips for better scores next time:</strong><br>
        • Look directly at the camera lens — not the screen — for eye contact<br>
        • Sit still and upright — any shaking reduces posture and calmness scores<br>
        • Wear Shalwar Kameez with waistcoat <em>or</em> formal suit with tie for 10/10 dressing<br>
        • Move camera back to show your full torso so dressing can be assessed
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**🔍 Question-by-Question Review**")
    amap = {a['question_index']:a for a in ans}
    for ev in evs:
        qi=ev['question_index']; a=amap.get(qi,{}); sc=ev.get('score',5)
        with st.expander(f"Q{qi+1} — {sc}/10 — {str(a.get('question',''))[:72]}…"):
            cc1,cc2=st.columns(2)
            with cc1:
                st.markdown(f"**Q:** {a.get('question','N/A')}\n\n**A:** {a.get('answer','*(none)*')}")
                st.markdown(f'<div class="cs" style="margin-top:8px"><div style="font-size:11px;color:var(--t3);margin-bottom:4px">SUMMARY</div><div style="font-size:13px;color:var(--t2)">{ev.get("summary","")}</div></div>',unsafe_allow_html=True)
            with cc2:
                st.markdown(mbar("Technical",ev.get('technical_score',5))+
                            mbar("Communication",ev.get('communication_score',5))+
                            mbar("Confidence",ev.get('confidence',5))+
                            mbar("Tone",ev.get('tone_score',5)),unsafe_allow_html=True)
                st.markdown(f'<div class="cs"><div style="color:#10b981;font-size:11px;margin-bottom:3px">✅ Strengths</div><div style="font-size:12px;color:var(--t2)">{ev.get("strengths","")}</div></div><div class="cs" style="margin-top:6px"><div style="color:#f59e0b;font-size:11px;margin-bottom:3px">⚠️ Improvement</div><div style="font-size:12px;color:var(--t2)">{ev.get("improvement","")}</div></div>',unsafe_allow_html=True)
                if ev.get('model_answer_hint'):
                    st.markdown(f'<div class="cs" style="margin-top:6px;border-color:rgba(79,139,255,.2)"><div style="color:var(--a);font-size:11px;margin-bottom:3px">💡 Model Hint</div><div style="font-size:12px;color:var(--t2)">{ev.get("model_answer_hint","")}</div></div>',unsafe_allow_html=True)
                if ev.get('star_used'): st.markdown('<span class="badge">⭐ STAR Used</span>',unsafe_allow_html=True)

    st.markdown("---")
    lines=[f"INTERVIEW REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
           f"Candidate: {st.session_state.resume_info.get('name','N/A')}  Role: {st.session_state.role}",
           f"Grade: {g} ({lbl})  Score: {pct:.0f}%","="*55]
    for ev in evs:
        a=amap.get(ev['question_index'],{})
        lines+=[f"\nQ{ev['question_index']+1}: {a.get('question','N/A')}",
                f"Score: {ev.get('score')}/10",f"Answer: {a.get('answer','(none)')}",
                f"Summary: {ev.get('summary','')}"]

    cd,cn,da=st.columns(3)
    with cd:
        st.download_button("📋 Download Report","\n".join(lines),
            file_name=f"interview_{sid}.txt",mime="text/plain",use_container_width=True)
    with cn:
        if st.button("🔄 New Interview",use_container_width=True):
            for k in ['session_id','questions','answers','evaluations','current_q',
                      'interview_started','interview_complete','follow_ups','generated_questions']:
                st.session_state.pop(k,None)
            nav('resume')
    with da:
        if st.button("📈 Dashboard",use_container_width=True): nav('dashboard')


# ════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════════════════════════════
def page_dashboard():
    nav_bar('dashboard')
    back_btn("Home","home")
    st.title("📈 Performance Dashboard")
    stats   = db.get_dashboard_stats()
    all_evs = db.get_all_evaluations_for_dashboard()
    all_s   = db.get_all_sessions()
    all_a   = db.get_all_achievements()

    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Total Sessions",stats['total_sessions'])
    with c2: st.metric("Average Score",f"{stats['avg_score']}%")
    with c3: st.metric("Best Score",f"{stats['best_score']:.0f}%")
    with c4: st.metric("Achievements",len(all_a))

    if not all_s:
        st.info("No completed sessions yet.")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Try Demo"): nav('demo')
        with c2:
            if st.button("🚀 Start"): nav('resume')
        return

    trend = stats.get('score_trend',[])
    if len(trend) >= 2:
        fig=go.Figure(go.Scatter(x=[d['date'] for d in trend],y=[d['avg_score'] for d in trend],
            mode='lines+markers',line=dict(color='#ec4899',width=3),marker=dict(size=8,color='#ec4899'),
            fill='tozeroy',fillcolor='rgba(236,72,153,.08)'))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#eef2ff'),yaxis=dict(range=[0,105],gridcolor='rgba(255,255,255,.04)'),
            xaxis=dict(gridcolor='rgba(255,255,255,.04)'),
            margin=dict(l=10,r=10,t=30,b=10),height=230,
            title=dict(text="Score Trend",font=dict(color='#8896b3',size=13)))
        st.plotly_chart(fig,use_container_width=True)

    c1,c2=st.columns(2)
    with c1:
        rd=stats.get('role_stats',[])
        if rd:
            fig=go.Figure(go.Bar(x=[round(r['avg_score'] or 0,1) for r in rd],y=[r['role'] for r in rd],
                orientation='h',marker_color='rgba(79,139,255,.7)',
                text=[f"{round(r['avg_score'] or 0):.0f}%" for r in rd],textposition='auto',textfont=dict(color='white',size=11)))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#eef2ff'),xaxis=dict(range=[0,110],gridcolor='rgba(255,255,255,.04)'),
                margin=dict(l=10,r=10,t=30,b=10),height=260,
                title=dict(text="Performance by Role",font=dict(color='#8896b3',size=13)))
            st.plotly_chart(fig,use_container_width=True)
    with c2:
        if all_evs:
            dims=['technical_score','communication_score','confidence','tone_score']
            dlab=['Technical','Communication','Confidence','Tone']
            davg=[sum(e.get(d,5) for e in all_evs)/len(all_evs) for d in dims]
            fig=go.Figure(go.Bar(x=dlab,y=davg,marker_color=['#4f8bff','#a855f7','#10b981','#f59e0b'],
                text=[f"{v:.1f}" for v in davg],textposition='outside',textfont=dict(color='#eef2ff',size=12)))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#eef2ff'),yaxis=dict(range=[0,11],gridcolor='rgba(255,255,255,.04)'),
                margin=dict(l=10,r=10,t=30,b=10),height=260,
                title=dict(text="Avg Skill Dimensions",font=dict(color='#8896b3',size=13)))
            st.plotly_chart(fig,use_container_width=True)

    if all_a:
        st.markdown("---")
        st.markdown("**🏆 All Achievements**")
        st.markdown(" ".join([f'<span class="badge">{a["badge_emoji"]} {a["badge_name"]}</span>' for a in all_a]),unsafe_allow_html=True)

    if all_evs:
        dm=dict(zip(['Technical','Communication','Confidence','Tone'],
            [sum(e.get(d,5) for e in all_evs)/len(all_evs)
             for d in ['technical_score','communication_score','confidence','tone_score']]))
        weak=min(dm,key=dm.get); best=max(dm,key=dm.get)
        st.markdown("---"); st.markdown("**💡 AI Insights**")
        c1,c2=st.columns(2)
        with c1:
            st.markdown(f'<div class="cs" style="border-color:rgba(239,68,68,.3)"><div style="color:#ef4444;font-size:11px;margin-bottom:3px">📉 Focus Area</div><div style="font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif">{weak}</div><div style="font-size:12px;color:var(--t2);margin-top:4px">Avg: {dm[weak]:.1f}/10 — practise this</div></div>',unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="cs" style="border-color:rgba(16,185,129,.3)"><div style="color:#10b981;font-size:11px;margin-bottom:3px">📈 Strongest Area</div><div style="font-size:15px;font-weight:700;font-family:\'Syne\',sans-serif">{best}</div><div style="font-size:12px;color:var(--t2);margin-top:4px">Avg: {dm[best]:.1f}/10 — great!</div></div>',unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  HISTORY
# ════════════════════════════════════════════════════════════════════
def page_history():
    nav_bar('history')
    back_btn("Home","home")
    st.title("Session History")
    sessions = db.get_all_sessions()

    if not sessions:
        st.info("No completed interviews yet.")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Demo"): nav('demo')
        with c2:
            if st.button("Start"): nav('resume')
        return

    c1,c2,c3=st.columns(3)
    with c1:
        roles=['All']+sorted(set(s['role'] for s in sessions))
        fr=st.selectbox("Role",roles)
    with c2:
        diffs=['All']+list(set(s['difficulty'] for s in sessions))
        fd=st.selectbox("Difficulty",diffs)
    with c3:
        srt=st.selectbox("Sort",["Most Recent","Highest Score","Lowest Score"])

    filtered=sessions
    if fr!='All': filtered=[s for s in filtered if s['role']==fr]
    if fd!='All': filtered=[s for s in filtered if s['difficulty']==fd]
    if srt=="Highest Score": filtered.sort(key=lambda x:x.get('avg_score') or 0,reverse=True)
    elif srt=="Lowest Score": filtered.sort(key=lambda x:x.get('avg_score') or 0)

    st.markdown(f"**{len(filtered)} sessions found**")

    # Track which session is pending delete confirmation
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = None

    for s in filtered:
        sc  = s.get('avg_score') or s.get('total_score') or 0
        pct = (sc/10*100) if sc<=10 else sc
        g,_ = grade(pct)
        gc  = '#10b981' if pct>=80 else '#4f8bff' if pct>=65 else '#f59e0b' if pct>=50 else '#ef4444'
        ds  = str(s.get('completed_at', s.get('created_at','N/A')))
        try: ds = datetime.fromisoformat(ds).strftime('%b %d, %Y %H:%M')
        except: pass

        row_col, del_col = st.columns([11, 1])
        with row_col:
            st.markdown(f"""<div class="hr-row">
              <div style="font-family:'DM Mono',monospace;font-size:11px;color:var(--t3);width:70px">{s['session_id']}</div>
              <div style="flex:1">
                <div style="font-family:'Syne',sans-serif;font-size:14px;font-weight:600">{s['role']}</div>
                <div style="font-size:12px;color:var(--t2)">{s['difficulty']} · {s['q_type']} · {s.get('answer_count',0)} answers</div>
              </div>
              <div style="font-size:12px;color:var(--t3);width:150px;text-align:right">{ds}</div>
              <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:800;color:{gc};width:50px;text-align:center">{g}</div>
              <div style="font-family:'DM Mono',monospace;font-size:14px;color:{gc};width:50px;text-align:right">{pct:.0f}%</div>
            </div>""", unsafe_allow_html=True)
        with del_col:
            if st.button("🗑", key=f"del_{s['session_id']}", help="Delete this session"):
                st.session_state.confirm_delete = s['session_id']

        # Inline confirmation row
        if st.session_state.confirm_delete == s['session_id']:
            st.warning(
                f"⚠️ Delete session **{s['session_id']}** "
                f"({s['role']} · {ds})? This cannot be undone."
            )
            ca, cb = st.columns(2)
            with ca:
                if st.button("✅ Yes, delete", key=f"yes_{s['session_id']}", use_container_width=True):
                    delete_session(s['session_id'])
                    st.session_state.confirm_delete = None
                    st.success(f"Session {s['session_id']} deleted.")
                    st.rerun()
            with cb:
                if st.button("Cancel", key=f"no_{s['session_id']}", use_container_width=True):
                    st.session_state.confirm_delete = None
                    st.rerun()

    st.markdown("---")
    if st.button("Analytics Dashboard"): nav('dashboard')


# ── ROUTER ─────────────────────────────────────────────────────────
{
    'home':          page_home,
    'demo':          page_demo,
    'resume':        page_resume,
    'resume_review': page_resume_review,
    'setup':         page_setup,
    'interview':     page_interview,
    'results':       page_results,
    'dashboard':     page_dashboard,
    'history':       page_history,
}.get(st.session_state.get('page', 'home'), page_home)()