"""
Resume Scorer — Consumer Web App (Streamlit)

Polished single-page app for scoring resumes against job descriptions.
Features visual score breakdowns (Plotly gauges), auth dialogs, usage dashboard,
and Stripe billing integration.

Run locally:
    streamlit run cloud/streamlit_app.py

Deploy to Streamlit Cloud:
    1. Push to repo (jananthan30/resume-scorer-web)
    2. Connect to Streamlit Cloud (share.streamlit.io)
    3. Set secrets: SCORER_API_URL, STRIPE_PUBLISHABLE_KEY
"""

import os
import uuid

import plotly.graph_objects as go
import requests
import streamlit as st

# ─── Configuration ───────────────────────────────────────────────────────────
API_URL = os.getenv("SCORER_API_URL", "https://resume-scorer.fly.dev")

# ─── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Resume Scorer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Session state defaults ─────────────────────────────────────────────────
_defaults = {
    "token": None,
    "user": None,
    "session_id": str(uuid.uuid4()),  # Anonymous fingerprint per session
    "page": "home",
    "score_result": None,
    "scores_used": 0,
    # Cross-page handoff from Discover → Score/Rewrite
    "prefill_resume": "",
    "prefill_jd": "",
    "discover_results": None,
    "stored_resume": "",  # Saved resume text persists across pages
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark theme */
    .stApp { background-color: #0f172a; }
    [data-testid="stHeader"] { background-color: #0f172a; }

    /* Hide Streamlit branding and header */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stHeader"] { display: none; }

    /* Card styles */
    .card {
        background: #1e293b;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #334155;
        margin-bottom: 16px;
    }
    .card-accent {
        background: #1e293b;
        border-radius: 12px;
        padding: 24px;
        border: 1px solid #6366f1;
        margin-bottom: 16px;
    }

    /* Hero stat cards */
    .stat-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px 16px;
        text-align: center;
        border: 1px solid #334155;
    }
    .stat-num { font-size: 32px; font-weight: 700; color: #818cf8; }
    .stat-label { font-size: 12px; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }

    /* Keyword chips */
    .chip-matched {
        display: inline-block;
        background: #166534;
        color: #bbf7d0;
        border-radius: 20px;
        padding: 4px 12px;
        margin: 3px;
        font-size: 13px;
        font-weight: 500;
    }
    .chip-missing {
        display: inline-block;
        background: #991b1b;
        color: #fecaca;
        border-radius: 20px;
        padding: 4px 12px;
        margin: 3px;
        font-size: 13px;
        font-weight: 500;
    }

    /* Recommendation badge */
    .badge {
        display: inline-block;
        border-radius: 8px;
        padding: 6px 16px;
        font-weight: 700;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-green { background: #166534; color: #bbf7d0; }
    .badge-yellow { background: #854d0e; color: #fef08a; }
    .badge-red { background: #991b1b; color: #fecaca; }

    /* Nav pills */
    .nav-container {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        padding: 8px 0;
        border-bottom: 1px solid #334155;
    }
    .nav-pill {
        background: transparent;
        color: #94a3b8;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px 20px;
        cursor: pointer;
        font-size: 14px;
        text-decoration: none;
        transition: all 0.2s;
    }
    .nav-pill:hover { background: #1e293b; color: #e2e8f0; }
    .nav-pill-active {
        background: #6366f1 !important;
        color: white !important;
        border-color: #6366f1 !important;
    }

    /* Section headers */
    .section-title {
        color: #e2e8f0;
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .section-subtitle {
        color: #94a3b8;
        font-size: 16px;
        margin-bottom: 24px;
    }

    /* Pricing */
    .price-tag {
        font-size: 40px;
        font-weight: 800;
        color: #818cf8;
    }
    .price-period { font-size: 16px; color: #94a3b8; font-weight: 400; }

    /* Progress bar override */
    .stProgress > div > div > div { background-color: #6366f1; }

    /* Remove extra padding on wide layout */
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ─── API helpers ─────────────────────────────────────────────────────────────

def api(method: str, endpoint: str, json_data: dict = None, token: str = None) -> dict:
    """Call the scorer API with session fingerprinting."""
    url = f"{API_URL.rstrip('/')}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "X-Client-Fingerprint": st.session_state.session_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=30)
        else:
            r = requests.post(url, json=json_data or {}, headers=headers, timeout=60)
        return {"status": r.status_code, "data": r.json()}
    except requests.RequestException as e:
        return {"status": 0, "data": {"detail": str(e)}}


def is_authenticated() -> bool:
    return st.session_state.token is not None and st.session_state.user is not None


def _extract_file_text(uploaded_file) -> str:
    """Extract text from an uploaded PDF, DOCX, or TXT file."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".txt") or name.endswith(".md"):
        return raw.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        try:
            import io
            from docx import Document
            doc = Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs)
            if text.strip():
                return text
            st.warning("DOCX file appears empty. Please paste your resume instead.")
            return ""
        except ImportError:
            st.error("python-docx is not installed. Please paste your resume text instead.")
            return ""
        except Exception as e:
            st.error(f"Could not read DOCX file: {e}")
            return ""
    if name.endswith(".pdf"):
        try:
            import io
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
            if text.strip():
                return text
            st.warning("PDF file appears empty or is scanned. Please paste your resume instead.")
            return ""
        except ImportError:
            st.error("PyPDF2 is not installed. Please paste your resume text instead.")
            return ""
        except Exception as e:
            st.error(f"Could not read PDF file: {e}")
            return ""
    return raw.decode("utf-8", errors="replace")


def resume_input(label: str = "Your Resume", prefill: str = "", key_prefix: str = "r", height: int = 350) -> str:
    """Shared resume input: file upload + text area + save option.

    Returns the resume text (from file, stored resume, or typed).
    """
    text_key = f"{key_prefix}_text"

    # File upload
    uploaded = st.file_uploader(
        "Upload resume (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt", "md"],
        key=f"{key_prefix}_file_upload",
    )

    # When a new file is uploaded, extract and write directly into the text_area's widget key
    if uploaded:
        file_sig = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.get(f"{key_prefix}_file_sig") != file_sig:
            extracted = _extract_file_text(uploaded)
            if extracted and not extracted.startswith("["):
                # Write directly into the widget's session state key so text_area picks it up
                st.session_state[text_key] = extracted
                st.session_state[f"{key_prefix}_file_sig"] = file_sig
                st.session_state.stored_resume = extracted
                st.rerun()

    # Pre-fill from stored resume or prefill (only if text_area hasn't been touched yet)
    if text_key not in st.session_state:
        default = prefill or st.session_state.get("stored_resume", "") or ""
        if default:
            st.session_state[text_key] = default

    # Text area — keyed, so Streamlit reads/writes st.session_state[text_key]
    resume_text = st.text_area(
        label,
        height=height,
        placeholder="Paste your resume text here, or upload a file above.",
        key=text_key,
    )

    # Save toggle
    has_stored = bool(st.session_state.get("stored_resume", ""))
    if resume_text and resume_text.strip():
        if not has_stored:
            if st.button("Save as my resume", key=f"{key_prefix}_save", help="Save this resume for use across all pages"):
                st.session_state.stored_resume = resume_text
                st.success("Resume saved for this session.")
                st.rerun()
        elif resume_text != st.session_state.stored_resume:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Update saved resume", key=f"{key_prefix}_update"):
                    st.session_state.stored_resume = resume_text
                    st.success("Saved resume updated.")
                    st.rerun()
            with col_b:
                if st.button("Clear saved resume", key=f"{key_prefix}_clear"):
                    st.session_state.stored_resume = ""
                    st.session_state.pop(text_key, None)
                    st.rerun()
        else:
            st.markdown(
                '<span style="color: #22c55e; font-size: 12px;">&#10003; Using saved resume</span>',
                unsafe_allow_html=True,
            )

    return resume_text


# ─── Navigation ──────────────────────────────────────────────────────────────

def render_nav():
    """Top navigation bar."""
    cols = st.columns([1, 1, 1, 1, 1, 1, 2])

    with cols[0]:
        if st.button("Home", use_container_width=True, type="primary" if st.session_state.page == "home" else "secondary"):
            st.session_state.page = "home"
            st.rerun()
    with cols[1]:
        if st.button("Score", use_container_width=True, type="primary" if st.session_state.page == "scorer" else "secondary"):
            st.session_state.page = "scorer"
            st.rerun()
    with cols[2]:
        if st.button("Discover", use_container_width=True, type="primary" if st.session_state.page == "discover" else "secondary"):
            st.session_state.page = "discover"
            st.rerun()
    with cols[3]:
        if st.button("Rewrite", use_container_width=True, type="primary" if st.session_state.page == "rewriter" else "secondary"):
            st.session_state.page = "rewriter"
            st.rerun()
    with cols[4]:
        if st.button("Cover Letter", use_container_width=True, type="primary" if st.session_state.page == "cover_letter" else "secondary"):
            st.session_state.page = "cover_letter"
            st.rerun()
    with cols[5]:
        if is_authenticated():
            if st.button("Dashboard", use_container_width=True, type="primary" if st.session_state.page == "dashboard" else "secondary"):
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            if st.button("Login", use_container_width=True, type="primary" if st.session_state.page == "login" else "secondary"):
                st.session_state.page = "login"
                st.rerun()
    with cols[6]:
        if is_authenticated():
            if st.button("Logout", use_container_width=True):
                st.session_state.token = None
                st.session_state.user = None
                st.session_state.page = "home"
                st.rerun()
        else:
            if st.button("Register", use_container_width=True, type="primary" if st.session_state.page == "register" else "secondary"):
                st.session_state.page = "register"
                st.rerun()

    st.markdown("---")


# ─── Plotly gauge charts ─────────────────────────────────────────────────────

def make_gauge(value: float, title: str) -> go.Figure:
    """Create a circular gauge chart for a score."""
    if value >= 75:
        bar_color = "#22c55e"
    elif value >= 50:
        bar_color = "#eab308"
    else:
        bar_color = "#ef4444"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"size": 48, "color": "#e2e8f0"}},
        title={"text": title, "font": {"size": 16, "color": "#94a3b8"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "#1e293b",
                     "tickfont": {"color": "#64748b"}},
            "bar": {"color": bar_color, "thickness": 0.3},
            "bgcolor": "#334155",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 35], "color": "rgba(239,68,68,0.1)"},
                {"range": [35, 50], "color": "rgba(234,179,8,0.05)"},
                {"range": [50, 75], "color": "rgba(234,179,8,0.1)"},
                {"range": [75, 100], "color": "rgba(34,197,94,0.1)"},
            ],
            "threshold": {
                "line": {"color": "#6366f1", "width": 3},
                "thickness": 0.8,
                "value": value,
            },
        },
    ))
    fig.update_layout(
        height=250,
        margin={"t": 50, "b": 10, "l": 30, "r": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
    )
    return fig


def make_bar_chart(labels: list, values: list, title: str) -> go.Figure:
    """Horizontal bar chart for score component breakdown."""
    colors = ["#22c55e" if v >= 70 else "#eab308" if v >= 40 else "#ef4444" for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}%" for v in values],
        textposition="auto",
        textfont={"color": "#e2e8f0", "size": 12},
    ))
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": "#94a3b8"}, "x": 0},
        height=max(200, len(labels) * 40 + 80),
        margin={"t": 40, "b": 20, "l": 150, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"range": [0, 100], "showgrid": True, "gridcolor": "#1e293b",
               "tickfont": {"color": "#64748b"}, "title": ""},
        yaxis={"tickfont": {"color": "#e2e8f0"}, "autorange": "reversed"},
        bargap=0.3,
    )
    return fig


# ─── Score display helpers ───────────────────────────────────────────────────

def render_keyword_chips(matched: list, missing: list):
    """Render matched (green) and missing (red) keyword chips."""
    html = ""
    if matched:
        html += "<div style='margin-bottom: 8px;'><span style='color: #94a3b8; font-size: 13px;'>Matched:</span><br>"
        for kw in matched[:20]:
            html += f'<span class="chip-matched">{kw}</span>'
        html += "</div>"
    if missing:
        html += "<div><span style='color: #94a3b8; font-size: 13px;'>Missing:</span><br>"
        for kw in missing[:15]:
            html += f'<span class="chip-missing">{kw}</span>'
        html += "</div>"
    if html:
        st.markdown(html, unsafe_allow_html=True)


def render_hr_badge(recommendation: str):
    """Render colored HR recommendation badge."""
    rec_upper = recommendation.upper() if recommendation else ""
    if "STRONG" in rec_upper or "INTERVIEW" in rec_upper:
        css_class = "badge-green"
    elif "MAYBE" in rec_upper:
        css_class = "badge-yellow"
    else:
        css_class = "badge-red"

    st.markdown(
        f'<span class="badge {css_class}">{recommendation}</span>',
        unsafe_allow_html=True,
    )


def render_quick_wins(explanation: dict):
    """Render improvement suggestions from ATS explanation."""
    quick_wins = explanation.get("quick_wins", [])
    missing_kw = explanation.get("top_missing_keywords", [])

    if quick_wins:
        st.markdown("##### Quick Wins")
        for win in quick_wins:
            st.markdown(f"- {win}")

    if missing_kw:
        st.markdown("##### Top Missing Keywords")
        for item in missing_kw[:5]:
            delta = item.get("estimated_score_increase", "")
            placement = item.get("suggested_placement", "")
            st.markdown(f"- **{item['keyword']}** — add to _{placement}_ ({delta})")


def render_hr_insights(explanation: dict):
    """Render HR improvement suggestions."""
    improvements = explanation.get("priority_improvements", [])
    strengths = explanation.get("strengths_to_emphasize", [])
    risks = explanation.get("risk_mitigations", [])

    if strengths:
        st.markdown("##### Your Strengths")
        for s in strengths:
            st.markdown(f"- **{s['factor']}** ({s['current_score']:.0f}%) — {s['advice']}")

    if improvements:
        st.markdown("##### Priority Improvements")
        for imp in improvements:
            st.markdown(f"- **{imp['factor']}** ({imp['current_score']:.0f}%) — {imp['suggestion']}")

    if risks:
        st.markdown("##### Risk Mitigations")
        for r in risks:
            st.markdown(f"- **{r['risk']}** ({r['penalty']}) — {r['mitigation']}")


# ─── Pages ───────────────────────────────────────────────────────────────────

def page_home():
    """Landing / hero page."""
    # Hero
    st.markdown("""
    <div style="text-align: center; padding: 40px 0 20px 0;">
        <h1 style="color: #e2e8f0; font-size: 42px; font-weight: 800; margin-bottom: 8px;">
            Score Your Resume in Seconds
        </h1>
        <p style="color: #94a3b8; font-size: 18px; max-width: 600px; margin: 0 auto;">
            AI-powered ATS + HR scoring that tells you exactly how your resume will perform
            with applicant tracking systems and human recruiters.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Benefit cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-num">ATS</div>
            <div class="stat-label">Keyword & Semantic Analysis</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="card" style="min-height: 120px;">
            <p style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px;">Beat the Bots</p>
            <p style="color: #94a3b8; font-size: 14px;">
                8-component scoring: keywords, phrases, semantic matching, BM25 ranking,
                industry terms, skill graphs, job title match, and recency weighting.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-num">HR</div>
            <div class="stat-label">Recruiter Simulation</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="card" style="min-height: 120px;">
            <p style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px;">Impress Humans</p>
            <p style="color: #94a3b8; font-size: 14px;">
                6-factor recruiter evaluation: experience fit, skills match, career trajectory,
                impact signals, competitive edge, and job fit analysis.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-num">5</div>
            <div class="stat-label">Free Scores</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="card" style="min-height: 120px;">
            <p style="color: #e2e8f0; font-weight: 600; margin-bottom: 8px;">Start Free</p>
            <p style="color: #94a3b8; font-size: 14px;">
                No account needed for your first 5 scores. Upgrade to Pro ($12/month)
                for unlimited scoring with detailed explanations.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # CTA
    _, cta_col, _ = st.columns([2, 3, 2])
    with cta_col:
        if st.button("Score My Resume Now", use_container_width=True, type="primary"):
            st.session_state.page = "scorer"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Pricing section
    render_pricing()


def render_pricing():
    """Pricing comparison section — Free / Pro / Ultra."""
    st.markdown('<div class="section-title" style="text-align: center;">Pricing</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle" style="text-align: center;">Simple, transparent pricing</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="card" style="text-align: center; min-height: 380px;">
            <p style="color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Free</p>
            <div class="price-tag">$0</div>
            <hr style="border-color: #334155; margin: 16px 0;">
            <div style="text-align: left; color: #94a3b8; font-size: 14px; line-height: 2;">
                &#10003;&nbsp; 5 total scores<br>
                &#10003;&nbsp; ATS + HR scoring<br>
                &#10003;&nbsp; Domain auto-detection<br>
                &#10007;&nbsp; LLM-augmented scoring<br>
                &#10007;&nbsp; AI resume rewriting
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card-accent" style="text-align: center; min-height: 380px;">
            <p style="color: #818cf8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Pro</p>
            <div class="price-tag">$12<span class="price-period">/month</span></div>
            <hr style="border-color: #6366f1; margin: 16px 0;">
            <div style="text-align: left; color: #94a3b8; font-size: 14px; line-height: 2;">
                &#10003;&nbsp; Unlimited scores<br>
                &#10003;&nbsp; ATS + HR + LLM scoring<br>
                &#10003;&nbsp; Detailed explanations<br>
                &#10003;&nbsp; API key access<br>
                &#10003;&nbsp; 10 AI rewrites/month
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="card-accent" style="text-align: center; min-height: 380px; border-color: #a855f7;">
            <p style="color: #a855f7; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Ultra</p>
            <div class="price-tag" style="color: #c084fc;">$29<span class="price-period">/month</span></div>
            <hr style="border-color: #a855f7; margin: 16px 0;">
            <div style="text-align: left; color: #94a3b8; font-size: 14px; line-height: 2;">
                &#10003;&nbsp; Everything in Pro<br>
                &#10003;&nbsp; Unlimited AI rewrites<br>
                &#10003;&nbsp; Before/after scoring<br>
                &#10003;&nbsp; Download tailored DOCX<br>
                &#10003;&nbsp; Change tracking
            </div>
        </div>
        """, unsafe_allow_html=True)


def page_scorer():
    """Interactive resume scorer — paste resume + JD, get visual results."""
    st.markdown('<div class="section-title">Score Your Resume</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Paste your resume and job description to see how well they match.</div>',
        unsafe_allow_html=True,
    )

    # Free scores counter / Pro LLM toggle
    is_paid = is_authenticated() and st.session_state.user and st.session_state.user.get("tier") in ("pro", "ultra")

    if is_paid:
        use_llm = st.toggle("Include LLM Analysis (Pro)", value=True, help="Add Claude-powered AI analysis on top of ATS + HR scoring")
    else:
        use_llm = False
        remaining = max(0, 5 - st.session_state.scores_used)
        st.markdown(
            f'<div style="text-align: right; color: #94a3b8; font-size: 13px; margin-bottom: 12px;">'
            f'Free scores remaining: <strong style="color: #818cf8;">{remaining}/5</strong></div>',
            unsafe_allow_html=True,
        )
        # Signup prompt for anonymous users
        if not is_authenticated():
            signup_col1, signup_col2 = st.columns([5, 2])
            with signup_col1:
                st.markdown(
                    '<p style="color: #94a3b8; font-size: 14px; margin: 0;">'
                    'Create a free account to track your scores and unlock Pro features.</p>',
                    unsafe_allow_html=True,
                )
            with signup_col2:
                if st.button("Sign Up Free", key="top_signup", type="secondary", use_container_width=True):
                    st.session_state.page = "register"
                    st.rerun()

    # Pre-fill from Discover page handoff (if any)
    prefill_resume = st.session_state.pop("prefill_resume", "") or ""
    prefill_jd = st.session_state.pop("prefill_jd", "") or ""
    if prefill_jd and "score_jd_text" not in st.session_state:
        st.session_state["score_jd_text"] = prefill_jd

    # Input columns
    col_resume, col_jd = st.columns(2)
    with col_resume:
        resume_text = resume_input("Resume", prefill=prefill_resume, key_prefix="score")
    with col_jd:
        jd_text = st.text_area(
            "Job Description",
            height=350,
            placeholder="Paste the job description here...\n\nInclude requirements, responsibilities, and qualifications.",
            key="score_jd_text",
        )

    # Score button
    _, btn_col, _ = st.columns([3, 2, 3])
    with btn_col:
        score_clicked = st.button("Analyze Resume", use_container_width=True, type="primary")

    if score_clicked:
        if not resume_text or not jd_text:
            st.error("Please paste both your resume and the job description.")
            return
        if len(resume_text.strip()) < 100:
            st.warning("Resume seems too short. Please paste the full text.")
            return
        if len(jd_text.strip()) < 50:
            st.warning("Job description seems too short. Please paste the full listing.")
            return

        endpoint = "/score/combined" if use_llm else "/score/both"
        spinner_msg = "Analyzing with ATS + HR + LLM..." if use_llm else "Analyzing your resume against the job description..."

        with st.spinner(spinner_msg):
            token = st.session_state.token
            payload = {"resume_text": resume_text, "jd_text": jd_text}
            if not use_llm:
                payload["include_explanation"] = True
            result = api("POST", endpoint, payload, token=token)

        if result["status"] == 402:
            # Free tier exhausted
            st.error("You've used all 5 free scores.")
            st.markdown("---")
            st.markdown(
                "**Upgrade to Pro** for unlimited scoring, detailed explanations, and LLM-augmented analysis."
            )
            if is_authenticated():
                if st.button("Upgrade to Pro ($12/month)", type="primary", use_container_width=True):
                    checkout = api("POST", "/billing/checkout", token=st.session_state.token)
                    if checkout["status"] == 200 and "checkout_url" in checkout["data"]:
                        st.link_button("Complete Payment on Stripe", checkout["data"]["checkout_url"], use_container_width=True)
                    else:
                        st.error(checkout["data"].get("detail", "Could not create checkout session."))
            else:
                st.info("Create a free account first, then upgrade to Pro.")
                if st.button("Create Account", type="primary"):
                    st.session_state.page = "register"
                    st.rerun()
            return

        if result["status"] != 200:
            st.error(f"Scoring failed: {result['data'].get('detail', 'Unknown error')}")
            return

        # Success — store result and bump counter
        data = result["data"]
        # Normalize /score/combined response to match /score/both shape
        if use_llm and "rules_ats" in data:
            data["_llm_mode"] = True
            data["ats"] = data.get("rules_ats", {})
            data["hr"] = data.get("rules_hr", {}) or {}
            data["summary"] = {
                "ats_score": data.get("combined_ats", data["ats"].get("total_score", 0)),
                "hr_score": data.get("combined_hr", data["hr"].get("overall_score", 0)),
                "ats_rating": data["ats"].get("rating", ""),
                "hr_recommendation": data["hr"].get("recommendation", ""),
                "overall_assessment": "",
            }
        st.session_state.score_result = data
        st.session_state.scores_used += 1

    # Display results if available
    data = st.session_state.score_result
    if data:
        render_score_results(data)

        # Post-score signup/upgrade prompt
        if not is_authenticated():
            st.markdown("---")
            st.markdown("""
            <div class="card-accent" style="text-align: center;">
                <p style="color: #818cf8; font-weight: 700; font-size: 18px; margin-bottom: 4px;">
                    Want unlimited scores + AI-powered analysis?
                </p>
                <p style="color: #94a3b8; font-size: 14px;">
                    Create a free account to save your results, then upgrade to Pro ($12/month)
                    for unlimited scoring and Claude-powered LLM analysis.
                </p>
            </div>
            """, unsafe_allow_html=True)
            _, cta_col, _ = st.columns([2, 3, 2])
            with cta_col:
                if st.button("Create Free Account", key="post_score_signup", type="primary", use_container_width=True):
                    st.session_state.page = "register"
                    st.rerun()
        elif not is_pro:
            st.markdown("---")
            st.markdown("""
            <div class="card-accent" style="text-align: center;">
                <p style="color: #818cf8; font-weight: 700; font-size: 18px; margin-bottom: 4px;">
                    Unlock LLM-Powered Analysis
                </p>
                <p style="color: #94a3b8; font-size: 14px;">
                    Upgrade to Pro ($12/month) for unlimited scoring and Claude AI analysis
                    with detailed evidence and improvement suggestions.
                </p>
            </div>
            """, unsafe_allow_html=True)
            _, cta_col, _ = st.columns([2, 3, 2])
            with cta_col:
                if st.button("Upgrade to Pro", key="post_score_upgrade", type="primary", use_container_width=True):
                    st.session_state.page = "dashboard"
                    st.rerun()


def render_score_results(data: dict):
    """Render visual score breakdown from API response."""
    ats = data.get("ats", {})
    hr = data.get("hr", {})
    summary = data.get("summary", {})
    explanation = data.get("explanation", {})

    ats_score = summary.get("ats_score", ats.get("total_score", 0))
    hr_score = summary.get("hr_score", hr.get("overall_score", 0))

    st.markdown("---")

    # ─── Gauges ──────────────────────────────────────────────────────────
    gauge_col1, gauge_col2 = st.columns(2)
    with gauge_col1:
        st.plotly_chart(make_gauge(ats_score, "ATS Score"), use_container_width=True)
    with gauge_col2:
        st.plotly_chart(make_gauge(hr_score, "HR Score"), use_container_width=True)

    # Overall assessment
    assessment = summary.get("overall_assessment", "")
    if assessment:
        st.markdown(
            f'<div style="text-align: center; color: #94a3b8; font-size: 16px; margin-bottom: 16px;">'
            f'{assessment}</div>',
            unsafe_allow_html=True,
        )

    # HR recommendation badge
    hr_rec = summary.get("hr_recommendation", hr.get("recommendation", ""))
    if hr_rec:
        st.markdown(
            '<div style="text-align: center; margin-bottom: 24px;">',
            unsafe_allow_html=True,
        )
        render_hr_badge(hr_rec)
        st.markdown('</div>', unsafe_allow_html=True)

    # ─── Detailed Tabs ───────────────────────────────────────────────────
    llm_data = data.get("llm") if data.get("_llm_mode") else None
    if llm_data and not llm_data.get("error"):
        tab_ats, tab_hr, tab_llm = st.tabs(["ATS Analysis", "HR Analysis", "LLM Analysis"])
    else:
        tab_ats, tab_hr = st.tabs(["ATS Analysis", "HR Analysis"])
        tab_llm = None

    with tab_ats:
        render_ats_tab(ats, explanation.get("ats", {}))

    with tab_hr:
        render_hr_tab(hr, explanation.get("hr", {}))

    if tab_llm is not None:
        with tab_llm:
            render_llm_tab(llm_data, data.get("blend_details", {}))


def render_ats_tab(ats: dict, ats_explanation: dict):
    """ATS detailed breakdown tab."""
    # Component bar chart
    component_map = {
        "Keyword Match": ats.get("keyword_score", 0),
        "Phrase Match": ats.get("phrase_score", 0),
        "Industry Terms": ats.get("weighted_score", 0),
        "Semantic Similarity": ats.get("semantic_score", 0),
        "BM25 Relevance": ats.get("bm25_score", 0),
        "Job Title Match": ats.get("job_title_score", 0),
        "Graph Centrality": ats.get("graph_score", 0),
        "Skill Recency": ats.get("recency_score", 0),
    }
    # Filter out zero/missing components
    labels = [k for k, v in component_map.items() if v is not None]
    values = [component_map[k] for k in labels]

    if labels:
        st.plotly_chart(
            make_bar_chart(labels, values, "ATS Component Breakdown"),
            use_container_width=True,
        )

    # Keyword chips
    matched = ats.get("matched_keywords", [])
    missing = ats.get("missing_keywords", [])
    if matched or missing:
        st.markdown("##### Keywords")
        render_keyword_chips(matched, missing)

    # Matched phrases
    matched_phrases = ats.get("matched_phrases", [])
    if matched_phrases:
        st.markdown("##### Matched Phrases")
        phrase_html = "".join(f'<span class="chip-matched">{p}</span>' for p in matched_phrases[:15])
        st.markdown(phrase_html, unsafe_allow_html=True)

    # Domain detection
    domain = ats.get("domain", "")
    if domain and isinstance(domain, str):
        st.markdown(f"**Detected Domain:** {domain.replace('_', ' ').title()}")

    # Readability
    readability = ats.get("readability", {})
    if isinstance(readability, dict) and readability.get("flesch_kincaid_grade"):
        grade = readability["flesch_kincaid_grade"]
        st.markdown(f"**Readability:** Grade {grade:.1f} (optimal: 10-12)")

    # Format risk
    format_risk = ats.get("format_risk_score")
    if format_risk is not None:
        risk_label = "Low" if format_risk < 20 else "Medium" if format_risk < 50 else "High"
        st.markdown(f"**Format Risk:** {format_risk:.0f}% ({risk_label})")

    # ATS rating
    rating = ats.get("rating", "")
    likelihood = ats.get("likelihood", "")
    if rating:
        st.markdown(f"**Rating:** {rating} — {likelihood}")

    # Quick wins from explanation
    if ats_explanation:
        st.markdown("---")
        render_quick_wins(ats_explanation)


def render_hr_tab(hr: dict, hr_explanation: dict):
    """HR detailed breakdown tab."""
    # Factor bar chart
    breakdown = hr.get("factor_breakdown", {})
    factor_labels = {
        "experience": "Experience Fit",
        "skills": "Skills Match",
        "trajectory": "Career Trajectory",
        "impact": "Impact Signals",
        "competitive": "Competitive Edge",
        "job_fit": "Job Fit",
    }

    labels = []
    values = []
    for key, label in factor_labels.items():
        val = breakdown.get(key)
        if val is not None and isinstance(val, (int, float)):
            labels.append(label)
            values.append(val)

    if labels:
        st.plotly_chart(
            make_bar_chart(labels, values, "HR Factor Breakdown"),
            use_container_width=True,
        )

    # Penalties
    penalties = hr.get("penalties_applied", {})
    if penalties:
        active_penalties = {k: v for k, v in penalties.items() if v and v > 0}
        if active_penalties:
            st.markdown("##### Penalties Applied")
            for name, val in active_penalties.items():
                st.markdown(f"- **{name.replace('_', ' ').title()}**: -{val:.1f} points")

    # Visual / F-pattern score
    visual = hr.get("visual_score")
    if visual is not None:
        st.markdown(f"**Visual/F-Pattern Score:** {visual:+.1f} points")

    # Metrics density
    metrics_density = hr.get("metrics_density")
    if metrics_density is not None:
        pct = metrics_density * 100 if metrics_density <= 1 else metrics_density
        st.markdown(f"**Metrics Density:** {pct:.0f}% of bullets have quantified impact")

    # HR explanation insights
    if hr_explanation:
        st.markdown("---")
        render_hr_insights(hr_explanation)


def render_llm_tab(llm_data: dict, blend_details: dict):
    """LLM (Claude) analysis tab — Pro only."""
    llm_ats = llm_data.get("ats_score")
    llm_hr = llm_data.get("hr_score")

    # LLM scores gauges
    if llm_ats is not None and llm_hr is not None:
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(make_gauge(llm_ats, "LLM ATS Score"), use_container_width=True)
        with g2:
            st.plotly_chart(make_gauge(llm_hr, "LLM HR Score"), use_container_width=True)

    # Blend details
    if blend_details and blend_details.get("method") != "rules_only":
        st.markdown(
            '<p style="color: #94a3b8; font-size: 13px; text-align: center;">'
            "Scores above are from Claude AI. The combined scores on the gauges blend rules-based and LLM analysis.</p>",
            unsafe_allow_html=True,
        )

    # Explanation summary
    explanation = llm_data.get("explanation", "")
    if explanation:
        st.markdown("##### AI Summary")
        st.info(explanation)

    # Dimension breakdown — ATS
    dimensions = llm_data.get("dimensions", {})
    ats_dims = dimensions.get("ats", {})
    if ats_dims:
        dim_labels_ats = {
            "keyword_match": "Keyword Match",
            "phrase_match": "Phrase Match",
            "industry_terms": "Industry Terms",
            "semantic_similarity": "Semantic Similarity",
            "bm25_relevance": "BM25 Relevance",
            "graph_centrality": "Graph Centrality",
            "skill_recency": "Skill Recency",
            "job_title_match": "Job Title Match",
        }
        labels = []
        values = []
        for key, label in dim_labels_ats.items():
            dim = ats_dims.get(key, {})
            if isinstance(dim, dict) and "score" in dim:
                labels.append(label)
                values.append(dim["score"] * 20)  # 0-5 scale → 0-100
        if labels:
            st.plotly_chart(make_bar_chart(labels, values, "LLM ATS Dimensions"), use_container_width=True)

        # Evidence details
        with st.expander("ATS Dimension Evidence"):
            for key, label in dim_labels_ats.items():
                dim = ats_dims.get(key, {})
                if isinstance(dim, dict) and dim.get("evidence"):
                    st.markdown(f"**{label}** ({dim.get('score', 0)}/5): {dim['evidence']}")

    # Dimension breakdown — HR
    hr_dims = dimensions.get("hr", {})
    if hr_dims:
        dim_labels_hr = {
            "job_fit": "Job Fit",
            "experience_fit": "Experience Fit",
            "skills_in_action": "Skills in Action",
            "impact_signals": "Impact Signals",
            "career_trajectory": "Career Trajectory",
            "competitive_edge": "Competitive Edge",
        }
        labels = []
        values = []
        for key, label in dim_labels_hr.items():
            dim = hr_dims.get(key, {})
            if isinstance(dim, dict) and "score" in dim:
                labels.append(label)
                values.append(dim["score"] * 20)
        if labels:
            st.plotly_chart(make_bar_chart(labels, values, "LLM HR Dimensions"), use_container_width=True)

        with st.expander("HR Dimension Evidence"):
            for key, label in dim_labels_hr.items():
                dim = hr_dims.get(key, {})
                if isinstance(dim, dict) and dim.get("evidence"):
                    st.markdown(f"**{label}** ({dim.get('score', 0)}/5): {dim['evidence']}")

    # Penalties
    penalties = llm_data.get("hr_penalties", {})
    if penalties:
        hopping = penalties.get("job_hopping", 0)
        gaps = penalties.get("gaps", 0)
        notes = penalties.get("notes", "")
        if hopping or gaps:
            st.markdown("##### LLM Risk Penalties")
            if hopping:
                st.markdown(f"- **Job Hopping**: {hopping} points")
            if gaps:
                st.markdown(f"- **Gaps**: {gaps} points")
            if notes:
                st.markdown(f"- _{notes}_")

    # Domain detected
    domain = llm_data.get("domain_detected", "")
    if domain:
        st.markdown(f"**Domain Detected (LLM):** {domain.replace('_', ' ').title()}")

    st.markdown(f"**Model:** {llm_data.get('model_used', 'claude-sonnet-4-6')}")


# ─── Rewriter page (Ultra) ──────────────────────────────────────────────────

def page_rewriter():
    """Pro + Ultra tier: AI resume rewriting with before/after scores."""
    st.markdown('<div class="section-title">AI Resume Rewriter</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Upload your resume and job description. '
        'Claude AI will tailor your resume and show before/after scores.</div>',
        unsafe_allow_html=True,
    )

    user_tier = ""
    if is_authenticated() and st.session_state.user:
        user_tier = st.session_state.user.get("tier", "free")

    can_rewrite = user_tier in ("pro", "ultra")

    if not can_rewrite:
        # Show upgrade prompt for free/anonymous users
        st.markdown("""
        <div class="card-accent" style="text-align: center; border-color: #818cf8;">
            <p style="color: #818cf8; font-weight: 700; font-size: 20px; margin-bottom: 8px;">
                Pro Feature
            </p>
            <p style="color: #94a3b8; font-size: 15px; margin-bottom: 16px;">
                AI resume rewriting is available on Pro ($12/month, 10 rewrites) and
                Ultra ($29/month, unlimited). Claude AI tailors your resume to match
                the job description while keeping your real experience intact.
            </p>
            <p style="color: #94a3b8; font-size: 14px;">
                &#10003; Before/after ATS + HR scores &nbsp;&nbsp;
                &#10003; Download tailored resume &nbsp;&nbsp;
                &#10003; Change tracking
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")
        if not is_authenticated():
            _, cta_col, _ = st.columns([2, 3, 2])
            with cta_col:
                if st.button("Sign Up to Get Started", type="primary", use_container_width=True):
                    st.session_state.page = "register"
                    st.rerun()
        else:
            _, pro_col, ultra_col, _ = st.columns([1, 2, 2, 1])
            with pro_col:
                if st.button("Pro — $12/month", type="primary", use_container_width=True):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "pro"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
                    elif result["status"] == 503:
                        st.warning("Stripe billing is not configured yet.")
                    else:
                        st.error(result["data"].get("detail", "Could not create checkout session."))
            with ultra_col:
                if st.button("Ultra — $29/month", use_container_width=True):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "ultra"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
                    elif result["status"] == 503:
                        st.warning("Stripe billing is not configured yet.")
                    else:
                        st.error(result["data"].get("detail", "Could not create checkout session."))

        st.markdown("---")
        render_pricing()
        return

    # ─── Pro / Ultra user: show the rewriter ──────────────────────────────
    # Show remaining rewrites for Pro users
    if user_tier == "pro":
        usage = api("GET", "/auth/usage", token=st.session_state.token)
        if usage["status"] == 200:
            rewrites_info = usage["data"].get("rewrites", {})
            remaining = rewrites_info.get("remaining", 10)
            limit = rewrites_info.get("limit", 10)
            st.markdown(
                f'<div style="text-align: right; color: #94a3b8; font-size: 13px; margin-bottom: 12px;">'
                f'Rewrites remaining: <strong style="color: #818cf8;">{remaining}/{limit}</strong> this month</div>',
                unsafe_allow_html=True,
            )
    # Pre-fill from Discover page handoff (if any)
    prefill_resume = st.session_state.pop("prefill_resume", "") or ""
    prefill_jd = st.session_state.pop("prefill_jd", "") or ""
    if prefill_jd and "rewrite_jd_text" not in st.session_state:
        st.session_state["rewrite_jd_text"] = prefill_jd

    col_resume, col_jd = st.columns(2)
    with col_resume:
        resume_text = resume_input("Your Resume", prefill=prefill_resume, key_prefix="rewrite", height=400)
    with col_jd:
        jd_text = st.text_area(
            "Target Job Description",
            height=400,
            placeholder="Paste the job description you're applying for...",
            key="rewrite_jd_text",
        )

    _, btn_col, _ = st.columns([3, 2, 3])
    with btn_col:
        rewrite_clicked = st.button("Rewrite My Resume", use_container_width=True, type="primary")

    if rewrite_clicked:
        if not resume_text or not jd_text:
            st.error("Please paste both your resume and the job description.")
            return
        if len(resume_text.strip()) < 100:
            st.warning("Resume seems too short. Please paste the full text.")
            return

        with st.spinner("AI is tailoring your resume... This may take 30-60 seconds."):
            result = api("POST", "/rewrite", {
                "resume_text": resume_text,
                "jd_text": jd_text,
            }, token=st.session_state.token)

        if result["status"] != 200:
            st.error(f"Rewrite failed: {result['data'].get('detail', 'Unknown error')}")
            return

        st.session_state.rewrite_result = result["data"]

    # Display rewrite results
    data = st.session_state.get("rewrite_result")
    if data:
        render_rewrite_results(data)


def render_rewrite_results(data: dict):
    """Show before/after scores, changes, and download button."""
    original = data.get("original_scores", {})
    rewritten = data.get("rewritten_scores", {})

    st.markdown("---")

    # ─── Before / After score comparison ──────────────────────────────────
    st.markdown("##### Score Comparison")

    score_col1, score_col2, score_col3, score_col4 = st.columns(4)
    with score_col1:
        st.metric("Original ATS", f"{original.get('ats', 0):.0f}%")
    with score_col2:
        ats_delta = rewritten.get("ats", 0) - original.get("ats", 0)
        st.metric("Rewritten ATS", f"{rewritten.get('ats', 0):.0f}%", delta=f"{ats_delta:+.0f}%")
    with score_col3:
        st.metric("Original HR", f"{original.get('hr', 0):.0f}%")
    with score_col4:
        hr_delta = rewritten.get("hr", 0) - original.get("hr", 0)
        st.metric("Rewritten HR", f"{rewritten.get('hr', 0):.0f}%", delta=f"{hr_delta:+.0f}%")

    # Visual gauge comparison
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(make_gauge(rewritten.get("ats", 0), "Rewritten ATS Score"), use_container_width=True)
    with g2:
        st.plotly_chart(make_gauge(rewritten.get("hr", 0), "Rewritten HR Score"), use_container_width=True)

    # ─── Explanation ──────────────────────────────────────────────────────
    explanation = data.get("explanation", "")
    if explanation:
        st.markdown("##### Tailoring Strategy")
        st.info(explanation)

    # ─── Changes made ─────────────────────────────────────────────────────
    changes = data.get("changes_made", [])
    if changes:
        st.markdown("##### Changes Made")
        for change in changes:
            st.markdown(f"- {change}")

    # ─── Rewritten resume text ────────────────────────────────────────────
    rewritten_text = data.get("rewritten_resume", "")
    if rewritten_text:
        st.markdown("---")
        st.markdown("##### Tailored Resume")
        st.text_area("Copy your tailored resume", value=rewritten_text, height=400, key="rewritten_output")

        # Download as .txt
        st.download_button(
            label="Download Tailored Resume (.txt)",
            data=rewritten_text,
            file_name="tailored_resume.txt",
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )

    st.markdown(f"**Model:** {data.get('model_used', 'claude-sonnet-4-6')}")


# ─── Auth pages ──────────────────────────────────────────────────────────────

def page_register():
    """Registration page."""
    _, form_col, _ = st.columns([1, 2, 1])
    with form_col:
        st.markdown('<div class="section-title">Create Account</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Sign up to track your usage and unlock Pro features.</div>',
            unsafe_allow_html=True,
        )

        with st.form("register_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="Min 6 characters")
            submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Email and password are required.")
                return
            if len(password) < 6:
                st.error("Password must be at least 6 characters.")
                return

            with st.spinner("Creating account..."):
                result = api("POST", "/auth/register", {"email": email, "password": password})

            if result["status"] == 200:
                data = result["data"]
                st.session_state.token = data["token"]
                st.session_state.user = data["user"]
                st.session_state.page = "scorer"
                st.success("Account created! Redirecting to scorer...")
                st.rerun()
            elif result["status"] == 409:
                st.error("Email already registered. Try logging in.")
            else:
                st.error(result["data"].get("detail", "Registration failed."))

        st.markdown("---")
        st.markdown("Already have an account?")
        if st.button("Log in instead"):
            st.session_state.page = "login"
            st.rerun()


def page_login():
    """Login page."""
    _, form_col, _ = st.columns([1, 2, 1])
    with form_col:
        st.markdown('<div class="section-title">Welcome Back</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">Sign in to access your dashboard and scoring history.</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Email and password are required.")
                return

            with st.spinner("Signing in..."):
                result = api("POST", "/auth/login", {"email": email, "password": password})

            if result["status"] == 200:
                data = result["data"]
                st.session_state.token = data["token"]
                st.session_state.user = data["user"]
                st.session_state.page = "dashboard"
                st.success("Signed in!")
                st.rerun()
            else:
                st.error(result["data"].get("detail", "Login failed. Check your credentials."))

        st.markdown("---")
        st.markdown("Don't have an account?")
        if st.button("Create one now"):
            st.session_state.page = "register"
            st.rerun()


# ─── Dashboard ───────────────────────────────────────────────────────────────

def page_dashboard():
    """Authenticated user dashboard."""
    if not is_authenticated():
        st.session_state.page = "login"
        st.rerun()
        return

    user = st.session_state.user
    token = st.session_state.token

    st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-subtitle">Signed in as {user["email"]} &middot; '
        f'{user.get("tier", "free").title()} plan</div>',
        unsafe_allow_html=True,
    )

    # Fetch usage stats
    usage = api("GET", "/auth/usage", token=token)

    if usage["status"] == 200:
        stats = usage["data"]
        total_used = stats.get("total_scores", 0)
        today_used = stats.get("today_scores", 0)
        remaining = stats.get("remaining")
        tier = user.get("tier", "free")

        # Metrics row
        rewrites_info = stats.get("rewrites", {})
        if tier in ("pro", "ultra"):
            m1, m2, m3, m4 = st.columns(4)
        else:
            m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Scores", total_used)
        with m2:
            st.metric("Today", today_used)
        with m3:
            if tier == "ultra":
                st.metric("Plan", "Ultra")
            elif tier == "pro":
                st.metric("Plan", "Pro")
            elif remaining is not None:
                st.metric("Remaining", f"{remaining}/5")
            else:
                st.metric("Remaining", "5")
        if tier in ("pro", "ultra"):
            with m4:
                if tier == "ultra":
                    st.metric("Rewrites", "Unlimited")
                else:
                    rw_remaining = rewrites_info.get("remaining", 10)
                    rw_limit = rewrites_info.get("limit", 10)
                    st.metric("Rewrites", f"{rw_remaining}/{rw_limit}")

        # Usage progress bar (free tier)
        if tier == "free" and remaining is not None:
            used_pct = min(1.0, total_used / 5)
            st.progress(used_pct, text=f"{total_used}/5 free scores used")
    elif usage["status"] == 401:
        st.warning("Session expired. Please log in again.")
        st.session_state.token = None
        st.session_state.user = None
        st.session_state.page = "login"
        st.rerun()
        return
    else:
        st.warning("Could not fetch usage stats.")

    st.markdown("---")

    # Upgrade / Billing section
    tier = user.get("tier", "free")
    if tier == "free":
        up1, up2 = st.columns(2)
        with up1:
            st.markdown("""
            <div class="card-accent">
                <p style="color: #818cf8; font-weight: 700; font-size: 16px; margin-bottom: 4px;">Pro — $12/month</p>
                <p style="color: #94a3b8; font-size: 13px;">Unlimited scoring + LLM analysis + 10 AI rewrites/month</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Upgrade to Pro", use_container_width=True, type="primary", key="dash_pro"):
                with st.spinner("Creating checkout session..."):
                    result = api("POST", "/billing/checkout", {"tier": "pro"}, token=token)
                if result["status"] == 200 and "checkout_url" in result["data"]:
                    st.link_button("Pay on Stripe", result["data"]["checkout_url"], use_container_width=True)
                elif result["status"] == 503:
                    st.warning("Stripe billing is not configured yet.")
                else:
                    st.error(result["data"].get("detail", "Checkout failed."))
        with up2:
            st.markdown("""
            <div class="card-accent" style="border-color: #a855f7;">
                <p style="color: #a855f7; font-weight: 700; font-size: 16px; margin-bottom: 4px;">Ultra — $29/month</p>
                <p style="color: #94a3b8; font-size: 13px;">Everything in Pro + unlimited AI rewrites</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Upgrade to Ultra", use_container_width=True, type="primary", key="dash_ultra"):
                with st.spinner("Creating checkout session..."):
                    result = api("POST", "/billing/checkout", {"tier": "ultra"}, token=token)
                if result["status"] == 200 and "checkout_url" in result["data"]:
                    st.link_button("Pay on Stripe", result["data"]["checkout_url"], use_container_width=True)
                elif result["status"] == 503:
                    st.warning("Stripe billing is not configured yet.")
                else:
                    st.error(result["data"].get("detail", "Checkout failed."))

    elif tier == "pro":
        st.markdown("""
        <div class="card-accent" style="border-color: #a855f7;">
            <p style="color: #a855f7; font-weight: 700; font-size: 16px; margin-bottom: 4px;">Upgrade to Ultra — $29/month</p>
            <p style="color: #94a3b8; font-size: 13px;">Everything you have now + unlimited AI rewrites (instead of 10/month)</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Upgrade to Ultra", use_container_width=True, type="primary", key="dash_pro_to_ultra"):
            with st.spinner("Creating checkout session..."):
                result = api("POST", "/billing/checkout", {"tier": "ultra"}, token=token)
            if result["status"] == 200 and "checkout_url" in result["data"]:
                st.link_button("Pay on Stripe", result["data"]["checkout_url"], use_container_width=True)
            elif result["status"] == 503:
                st.warning("Stripe billing is not configured yet.")
            else:
                st.error(result["data"].get("detail", "Checkout failed."))
    else:
        st.markdown("##### Manage Subscription")
        if st.button("Open Billing Portal", use_container_width=True):
            with st.spinner("Opening billing portal..."):
                result = api("POST", "/billing/portal", token=token)

            if result["status"] == 200:
                url = result["data"] if isinstance(result["data"], str) else result["data"].get("url", "")
                if url:
                    st.link_button("Open Stripe Billing Portal", url, use_container_width=True)
                else:
                    st.warning("Could not retrieve portal URL.")
            else:
                st.error(result["data"].get("detail", "Billing portal unavailable."))

    # ─── Claude Code Plugin setup (Pro / Ultra only) ─────────────────────
    if tier in ("pro", "ultra"):
        st.markdown("---")
        st.markdown("##### Claude Code Plugin Setup")
        st.markdown(
            '<p style="color: #94a3b8; font-size: 13px;">'
            "Generate an API key to connect your account to the local Claude Code plugin. "
            "<strong>Claude Code users only need Pro</strong> — your Anthropic subscription "
            "handles resume writing; this key unlocks unlimited <em>scoring</em> in the plugin."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.form("plugin_apikey_form"):
            label = st.text_input("Key label (optional)", placeholder="e.g. my-laptop")
            create_key = st.form_submit_button("Generate Plugin API Key", type="primary")

        if create_key:
            with st.spinner("Generating..."):
                result = api("POST", "/auth/api-key", {"label": label or "plugin"}, token=token)

            if result["status"] == 200:
                api_key = result["data"]["api_key"]
                st.success("API key created. Copy it now — it won't be shown again.")
                st.code(api_key, language=None)
                st.markdown("**Add to your `.env` file in the Resume Builder folder:**")
                st.code(f"SCORER_CLOUD_URL=https://resume-scorer.fly.dev\nSCORER_CLOUD_API_KEY={api_key}", language="bash")
                st.markdown(
                    '<p style="color: #94a3b8; font-size: 13px; margin-top: 8px;">'
                    "After saving, restart the scorer server: "
                    "<code>powershell -ExecutionPolicy Bypass -File restart_scorer.ps1</code>"
                    "</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.error(result["data"].get("detail", "Failed to create API key."))



# ─── Cover Letter page ───────────────────────────────────────────────────────


def page_cover_letter():
    """Pro + Ultra tier: AI cover letter generation."""
    st.markdown('<div class="section-title">AI Cover Letter</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Generate a tailored cover letter from your resume and a job description.</div>',
        unsafe_allow_html=True,
    )

    user_tier = ""
    if is_authenticated() and st.session_state.user:
        user_tier = st.session_state.user.get("tier", "free")

    can_generate = user_tier in ("pro", "ultra")

    if not can_generate:
        st.markdown("""
        <div class="card-accent" style="text-align: center; border-color: #818cf8;">
            <p style="color: #818cf8; font-weight: 700; font-size: 20px; margin-bottom: 8px;">
                Pro Feature
            </p>
            <p style="color: #94a3b8; font-size: 15px; margin-bottom: 16px;">
                AI cover letter generation is available on Pro ($12/month) and
                Ultra ($29/month). Claude AI writes a compelling, ready-to-send
                cover letter tailored to each job.
            </p>
            <p style="color: #94a3b8; font-size: 14px;">
                &#10003; Personalized to each JD &nbsp;&nbsp;
                &#10003; Highlights your best matches &nbsp;&nbsp;
                &#10003; Ready to send (no blanks)
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")
        if not is_authenticated():
            _, cta_col, _ = st.columns([2, 3, 2])
            with cta_col:
                if st.button("Sign Up to Get Started", type="primary", use_container_width=True, key="cl_signup"):
                    st.session_state.page = "register"
                    st.rerun()
        else:
            _, pro_col, ultra_col, _ = st.columns([1, 2, 2, 1])
            with pro_col:
                if st.button("Pro — $12/month", type="primary", use_container_width=True, key="cl_pro"):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "pro"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
                    elif result["status"] == 503:
                        st.warning("Stripe billing is not configured yet.")
                    else:
                        st.error(result["data"].get("detail", "Could not create checkout session."))
            with ultra_col:
                if st.button("Ultra — $29/month", use_container_width=True, key="cl_ultra"):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "ultra"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
                    elif result["status"] == 503:
                        st.warning("Stripe billing is not configured yet.")
                    else:
                        st.error(result["data"].get("detail", "Could not create checkout session."))
        return

    # ─── Pro / Ultra user: show the generator ─────────────────────────────
    prefill_resume = st.session_state.pop("prefill_resume", "") or ""
    prefill_jd = st.session_state.pop("prefill_jd", "") or ""
    if prefill_jd and "cover_jd_text" not in st.session_state:
        st.session_state["cover_jd_text"] = prefill_jd

    col_resume, col_jd = st.columns(2)
    with col_resume:
        resume_text = resume_input("Your Resume", prefill=prefill_resume, key_prefix="cover", height=350)
    with col_jd:
        jd_text = st.text_area(
            "Target Job Description",
            height=350,
            placeholder="Paste the job description here...",
            key="cover_jd_text",
        )

    _, btn_col, _ = st.columns([3, 2, 3])
    with btn_col:
        generate_clicked = st.button("Generate Cover Letter", use_container_width=True, type="primary")

    if generate_clicked:
        if not resume_text or not jd_text:
            st.error("Please paste both your resume and the job description.")
            return
        if len(resume_text.strip()) < 100:
            st.warning("Resume seems too short. Please paste the full text.")
            return

        with st.spinner("Claude is writing your cover letter... This may take 15-30 seconds."):
            result = api("POST", "/cover-letter", {
                "resume_text": resume_text,
                "jd_text": jd_text,
            }, token=st.session_state.token)

        if result["status"] != 200:
            st.error(f"Generation failed: {result['data'].get('detail', 'Unknown error')}")
            return

        st.session_state.cover_letter_result = result["data"]

    # Display result
    data = st.session_state.get("cover_letter_result")
    if data:
        render_cover_letter_result(data)


def render_cover_letter_result(data: dict):
    """Display generated cover letter with copy/download options."""
    paragraphs = data.get("paragraphs", [])
    full_text = data.get("full_text", "")
    company = data.get("company", "")
    title = data.get("job_title", "")
    word_count = data.get("word_count", 0)

    st.markdown("---")

    # Header info
    meta_cols = st.columns(3)
    with meta_cols[0]:
        st.metric("Company", company or "Detected")
    with meta_cols[1]:
        st.metric("Position", title or "Detected")
    with meta_cols[2]:
        color = "#22c55e" if word_count <= 400 else "#eab308"
        st.metric("Word Count", f"{word_count}")
        if word_count > 400:
            st.caption("Slightly over 1-page target")

    st.markdown("---")

    # Render each paragraph
    st.markdown("### Your Cover Letter")
    for i, para in enumerate(paragraphs):
        st.markdown(f"<p style='color: #e2e8f0; line-height: 1.7; margin-bottom: 16px;'>{para}</p>", unsafe_allow_html=True)

    # Copy/download
    st.markdown("---")
    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        st.download_button(
            "Download as .txt",
            data=full_text,
            file_name=f"Cover_Letter_{company.replace(' ', '_')}.txt" if company else "Cover_Letter.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with action_cols[1]:
        st.code(full_text, language=None)


# ─── Job Discovery page ──────────────────────────────────────────────────────


def render_job_card(rank: int, job: dict, resume_text: str = ""):
    """Render a single job result card with action buttons."""
    ats = job.get("ats_score", 0)
    hr = job.get("hr_score", 0)

    # Score color
    if ats >= 75:
        ats_color = "#22c55e"
    elif ats >= 60:
        ats_color = "#eab308"
    else:
        ats_color = "#ef4444"

    if hr >= 70:
        hr_color = "#22c55e"
    elif hr >= 55:
        hr_color = "#eab308"
    else:
        hr_color = "#ef4444"

    salary_text = ""
    if job.get("salary_min") and job.get("salary_max"):
        salary_text = f"${job['salary_min']:,.0f} – ${job['salary_max']:,.0f}"
    elif job.get("salary_min"):
        salary_text = f"${job['salary_min']:,.0f}+"

    rec = job.get("hr_detail", {}).get("recommendation", "")
    rec_badge = ""
    if rec:
        badge_colors = {
            "STRONG INTERVIEW": "#22c55e",
            "INTERVIEW": "#22c55e",
            "MAYBE": "#eab308",
            "PASS": "#ef4444",
        }
        bc = badge_colors.get(rec, "#94a3b8")
        rec_badge = f'<span style="background: {bc}22; color: {bc}; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">{rec}</span>'

    import html as _html
    matched_kw = job.get("ats_detail", {}).get("matched_keywords", [])
    missing_kw = job.get("ats_detail", {}).get("missing_keywords", [])

    matched_chips = " ".join(
        f'<span style="background: #22c55e22; color: #22c55e; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin: 1px;">{_html.escape(str(kw))}</span>'
        for kw in matched_kw[:8]
    )
    missing_chips = " ".join(
        f'<span style="background: #ef444422; color: #ef4444; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin: 1px;">{_html.escape(str(kw))}</span>'
        for kw in missing_kw[:5]
    )

    title_esc = _html.escape(job.get("title", "Unknown"))
    company_esc = _html.escape(job.get("company", ""))
    location_esc = _html.escape(job.get("location", ""))
    posted = job.get("posted_date", "")

    salary_html = f' &nbsp;&bull;&nbsp; <span style="color: #818cf8;">{salary_text}</span>' if salary_text else ""
    posted_html = f" &nbsp;&bull;&nbsp; Posted: {posted}" if posted else ""

    card_html = (
        '<div class="card" style="margin-bottom: 12px;">'
        '<div style="display: flex; justify-content: space-between; align-items: start;">'
        '<div>'
        f'<span style="color: #818cf8; font-weight: 700; font-size: 14px;">#{rank}</span>'
        f'<span style="color: #e2e8f0; font-weight: 600; font-size: 16px; margin-left: 8px;">{title_esc}</span>'
        f'{rec_badge}'
        '</div>'
        '<div style="text-align: right;">'
        f'<span style="color: {ats_color}; font-weight: 700; font-size: 18px;">ATS {ats}%</span>'
        '<span style="color: #475569; margin: 0 6px;">|</span>'
        f'<span style="color: {hr_color}; font-weight: 700; font-size: 18px;">HR {hr}%</span>'
        '</div>'
        '</div>'
        '<div style="margin-top: 6px; color: #94a3b8; font-size: 14px;">'
        f'<strong>{company_esc}</strong> &nbsp;&bull;&nbsp; {location_esc}'
        f'{salary_html}{posted_html}'
        '</div>'
    )
    if matched_chips or missing_chips:
        card_html += '<div style="margin-top: 8px;">'
        if matched_chips:
            card_html += f'<div style="margin-bottom: 4px;"><span style="color: #64748b; font-size: 11px;">MATCHED:</span> {matched_chips}</div>'
        if missing_chips:
            card_html += f'<div><span style="color: #64748b; font-size: 11px;">MISSING:</span> {missing_chips}</div>'
        card_html += '</div>'
    card_html += '</div>'
    st.markdown(card_html, unsafe_allow_html=True)

    # Action buttons row
    btn_cols = st.columns([1, 1, 1, 1, 2])
    jd_text = job.get("description", "")

    with btn_cols[0]:
        if job.get("url"):
            st.link_button("View Listing", job["url"], use_container_width=True)

    with btn_cols[1]:
        if st.button("Score", key=f"score_{rank}", use_container_width=True):
            st.session_state.prefill_resume = resume_text
            st.session_state.prefill_jd = jd_text
            st.session_state.page = "scorer"
            st.rerun()

    with btn_cols[2]:
        if st.button("Tailor Resume", key=f"tailor_{rank}", use_container_width=True):
            st.session_state.prefill_resume = resume_text
            st.session_state.prefill_jd = jd_text
            st.session_state.page = "rewriter"
            st.rerun()

    with btn_cols[3]:
        if st.button("Cover Letter", key=f"cl_{rank}", use_container_width=True, type="primary"):
            st.session_state.prefill_resume = resume_text
            st.session_state.prefill_jd = jd_text
            st.session_state.page = "cover_letter"
            st.rerun()


def page_discover():
    """Job Discovery page — search and score jobs against your resume."""
    st.markdown("## Discover Jobs")
    st.markdown(
        '<p style="color: #94a3b8;">Search for jobs and see how your resume scores against each one.</p>',
        unsafe_allow_html=True,
    )

    # ─── Auth gate: require login ─────────────────────────────────────────
    if not is_authenticated():
        st.markdown("""
        <div class="card-accent" style="text-align: center; border-color: #818cf8;">
            <p style="color: #818cf8; font-weight: 700; font-size: 20px; margin-bottom: 8px;">
                Sign Up to Discover Jobs
            </p>
            <p style="color: #94a3b8; font-size: 15px; margin-bottom: 16px;">
                Job discovery searches thousands of openings and scores each one against
                your resume with ATS + HR analysis. Create a free account to get started.
            </p>
            <p style="color: #94a3b8; font-size: 14px;">
                &#10003; Free: 2 discoveries included &nbsp;&nbsp;
                &#10003; Pro: unlimited &nbsp;&nbsp;
                &#10003; Real job listings from Adzuna
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        _, cta_col, _ = st.columns([2, 3, 2])
        with cta_col:
            if st.button("Sign Up Free", type="primary", use_container_width=True, key="discover_signup"):
                st.session_state.page = "register"
                st.rerun()
        return

    # ─── Usage check for free tier ────────────────────────────────────────
    user_tier = st.session_state.user.get("tier", "free") if st.session_state.user else "free"
    if user_tier == "free":
        remaining = max(0, 5 - st.session_state.scores_used)
        if remaining <= 0:
            st.markdown("""
            <div class="card-accent" style="text-align: center; border-color: #eab308;">
                <p style="color: #eab308; font-weight: 700; font-size: 18px; margin-bottom: 8px;">
                    Free Limit Reached
                </p>
                <p style="color: #94a3b8; font-size: 15px;">
                    You've used all 5 free scores. Each job discovery counts as 1 score.
                    Upgrade to Pro for unlimited discoveries.
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")
            _, pro_col, ultra_col, _ = st.columns([1, 2, 2, 1])
            with pro_col:
                if st.button("Pro — $12/month", type="primary", use_container_width=True, key="discover_pro"):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "pro"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
            with ultra_col:
                if st.button("Ultra — $29/month", use_container_width=True, key="discover_ultra"):
                    with st.spinner("Creating checkout session..."):
                        result = api("POST", "/billing/checkout", {"tier": "ultra"}, token=st.session_state.token)
                    if result["status"] == 200 and "checkout_url" in result["data"]:
                        st.link_button("Complete Payment on Stripe", result["data"]["checkout_url"], use_container_width=True)
            return
        st.markdown(
            f'<div style="text-align: right; color: #94a3b8; font-size: 13px; margin-bottom: 12px;">'
            f'Free scores remaining: <strong style="color: #818cf8;">{remaining}/5</strong> (each discovery = 1 score)</div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([2, 1])

    with col1:
        resume_text = resume_input("Your Resume", key_prefix="discover", height=200)

    with col2:
        job_title = st.text_input("Job title", placeholder="e.g., Data Scientist", key="discover_title")
        location = st.text_input("Location (optional)", placeholder="e.g., New York", key="discover_location")
        remote_only = st.checkbox("Include remote jobs", key="discover_remote")
        max_results = st.slider("Max results", 3, 20, 10, key="discover_max")

    if st.button("Search & Score", type="primary", use_container_width=True, disabled=not resume_text or not job_title):
        with st.spinner("Searching jobs and scoring matches..."):
            result = api("POST", "/jobs/discover", json_data={
                "resume_text": resume_text,
                "job_title": job_title,
                "location": location,
                "remote_only": remote_only,
                "max_results": max_results,
            }, token=st.session_state.token)

            if result["status"] == 200:
                data = result["data"]
                if data.get("setup_required"):
                    st.info(data.get("message", "API keys required for job discovery."))
                    st.session_state.discover_results = None
                elif not data.get("jobs"):
                    st.warning(data.get("message", "No jobs found. Try a different job title or location."))
                    st.session_state.discover_results = None
                else:
                    st.session_state.discover_results = {
                        "jobs": data["jobs"],
                        "resume_text": resume_text,
                        "attribution": data.get("attribution", ""),
                    }
            else:
                detail = result.get("data", {}).get("detail", "Job discovery failed.")
                st.error(detail)
                st.session_state.discover_results = None

    # Render persisted results (survives reruns for button clicks)
    cached = st.session_state.get("discover_results")
    if cached:
        jobs = cached["jobs"]
        cached_resume = cached.get("resume_text", "")
        st.success(f"Found {len(jobs)} matching jobs, ranked by fit score.")

        for job in jobs:
            render_job_card(job["rank"], job, resume_text=cached_resume)

        attr = cached.get("attribution", "")
        if attr:
            st.markdown(
                f'<div style="text-align: center; color: #64748b; font-size: 12px; margin-top: 16px;">{attr}</div>',
                unsafe_allow_html=True,
            )


# ─── Main router ─────────────────────────────────────────────────────────────

def render_footer():
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; padding: 16px 0; color: #64748b; font-size: 13px;">'
        'AI Resume Tuner &nbsp;|&nbsp; '
        '<a href="https://stats.uptimerobot.com/GrOgAbj0Nz" target="_blank" style="color: #818cf8; text-decoration: none;">System Status</a> &nbsp;|&nbsp; '
        '<a href="https://github.com/jananthan30/Resume-Builder" target="_blank" style="color: #818cf8; text-decoration: none;">GitHub</a> &nbsp;|&nbsp; '
        'MIT License'
        '</div>',
        unsafe_allow_html=True,
    )


def main():
    render_nav()

    page = st.session_state.page

    if page == "home":
        page_home()
    elif page == "scorer":
        page_scorer()
    elif page == "discover":
        page_discover()
    elif page == "cover_letter":
        page_cover_letter()
    elif page == "rewriter":
        page_rewriter()
    elif page == "register":
        page_register()
    elif page == "login":
        page_login()
    elif page == "dashboard":
        page_dashboard()
    else:
        page_home()

    render_footer()


if __name__ == "__main__":
    main()
