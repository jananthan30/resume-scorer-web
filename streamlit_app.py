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


# ─── Navigation ──────────────────────────────────────────────────────────────

def render_nav():
    """Top navigation bar."""
    cols = st.columns([1, 1, 1, 1, 4])

    with cols[0]:
        if st.button("Home", use_container_width=True, type="primary" if st.session_state.page == "home" else "secondary"):
            st.session_state.page = "home"
            st.rerun()
    with cols[1]:
        if st.button("Score Resume", use_container_width=True, type="primary" if st.session_state.page == "scorer" else "secondary"):
            st.session_state.page = "scorer"
            st.rerun()
    with cols[2]:
        if is_authenticated():
            if st.button("Dashboard", use_container_width=True, type="primary" if st.session_state.page == "dashboard" else "secondary"):
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            if st.button("Login", use_container_width=True, type="primary" if st.session_state.page == "login" else "secondary"):
                st.session_state.page = "login"
                st.rerun()
    with cols[3]:
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
    """Pricing comparison section."""
    st.markdown('<div class="section-title" style="text-align: center;">Pricing</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle" style="text-align: center;">Simple, transparent pricing</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="card" style="text-align: center; min-height: 320px;">
            <p style="color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Free</p>
            <div class="price-tag">$0</div>
            <hr style="border-color: #334155; margin: 16px 0;">
            <div style="text-align: left; color: #94a3b8; font-size: 14px; line-height: 2;">
                &#10003;&nbsp; 5 total scores<br>
                &#10003;&nbsp; ATS + HR scoring<br>
                &#10003;&nbsp; Domain auto-detection<br>
                &#10007;&nbsp; Detailed explanations<br>
                &#10007;&nbsp; LLM-augmented scoring
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card-accent" style="text-align: center; min-height: 320px;">
            <p style="color: #818cf8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Pro</p>
            <div class="price-tag">$12<span class="price-period">/month</span></div>
            <hr style="border-color: #6366f1; margin: 16px 0;">
            <div style="text-align: left; color: #94a3b8; font-size: 14px; line-height: 2;">
                &#10003;&nbsp; Unlimited scores<br>
                &#10003;&nbsp; ATS + HR + LLM scoring<br>
                &#10003;&nbsp; Detailed explanations & quick wins<br>
                &#10003;&nbsp; API key access<br>
                &#10003;&nbsp; Priority support
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
    is_pro = is_authenticated() and st.session_state.user and st.session_state.user.get("tier") == "pro"

    if is_pro:
        use_llm = st.toggle("Include LLM Analysis (Pro)", value=True, help="Add Claude-powered AI analysis on top of ATS + HR scoring")
    else:
        use_llm = False
        remaining = max(0, 5 - st.session_state.scores_used)
        st.markdown(
            f'<div style="text-align: right; color: #94a3b8; font-size: 13px; margin-bottom: 12px;">'
            f'Free scores remaining: <strong style="color: #818cf8;">{remaining}/5</strong></div>',
            unsafe_allow_html=True,
        )

    # Input columns
    col_resume, col_jd = st.columns(2)
    with col_resume:
        resume_text = st.text_area(
            "Resume",
            height=350,
            placeholder="Paste your resume text here...\n\nInclude all sections: summary, experience, skills, education.",
            key="resume_input",
        )
    with col_jd:
        jd_text = st.text_area(
            "Job Description",
            height=350,
            placeholder="Paste the job description here...\n\nInclude requirements, responsibilities, and qualifications.",
            key="jd_input",
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
    if domain:
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
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Scores", total_used)
        with m2:
            st.metric("Today", today_used)
        with m3:
            if tier == "pro":
                st.metric("Plan", "Pro (Unlimited)")
            elif remaining is not None:
                st.metric("Remaining", f"{remaining}/5")
            else:
                st.metric("Remaining", "5")

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
        st.markdown("""
        <div class="card-accent">
            <p style="color: #818cf8; font-weight: 700; font-size: 18px; margin-bottom: 8px;">
                Upgrade to Pro
            </p>
            <p style="color: #94a3b8; font-size: 14px; margin-bottom: 16px;">
                $12/month &mdash; Unlimited ATS + HR + LLM scoring, detailed explanations,
                API key access, and priority support. Cancel anytime.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Upgrade to Pro", use_container_width=True, type="primary"):
            with st.spinner("Creating checkout session..."):
                result = api("POST", "/billing/checkout", token=token)

            if result["status"] == 200 and "checkout_url" in result["data"]:
                st.link_button(
                    "Complete Payment on Stripe",
                    result["data"]["checkout_url"],
                    use_container_width=True,
                )
            elif result["status"] == 503:
                st.warning("Stripe billing is not configured yet.")
            else:
                st.error(result["data"].get("detail", "Could not create checkout session."))
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

    st.markdown("---")

    # API Key section (collapsed by default)
    with st.expander("Developer: API Keys"):
        st.markdown(
            '<p style="color: #94a3b8; font-size: 13px;">'
            "Generate an API key to use the scorer from scripts, CI/CD, or the CLI.</p>",
            unsafe_allow_html=True,
        )

        with st.form("apikey_form"):
            label = st.text_input("Key label (optional)", placeholder="e.g. my-laptop")
            create_key = st.form_submit_button("Generate API Key")

        if create_key:
            with st.spinner("Generating..."):
                result = api("POST", "/auth/api-key", {"label": label}, token=token)

            if result["status"] == 200:
                st.success("API key created! Copy it now — it won't be shown again.")
                st.code(result["data"]["api_key"], language=None)
                st.markdown(
                    "**Usage:**\n"
                    "```bash\n"
                    "curl -X POST https://resume-scorer.fly.dev/score/both \\\n"
                    '  -H "X-API-Key: YOUR_KEY" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    "  -d '{\"resume_text\":\"...\", \"jd_text\":\"...\"}'\n"
                    "```"
                )
            else:
                st.error(result["data"].get("detail", "Failed to create API key."))


# ─── Main router ─────────────────────────────────────────────────────────────

def main():
    render_nav()

    page = st.session_state.page

    if page == "home":
        page_home()
    elif page == "scorer":
        page_scorer()
    elif page == "register":
        page_register()
    elif page == "login":
        page_login()
    elif page == "dashboard":
        page_dashboard()
    else:
        page_home()


if __name__ == "__main__":
    main()
