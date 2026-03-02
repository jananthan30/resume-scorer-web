"""
Resume Scorer — Web Dashboard (Streamlit)

Provides registration, login, usage tracking, and Stripe billing UI.
Talks to the FastAPI scorer server at SCORER_API_URL.

Run locally:
    streamlit run cloud/streamlit_app.py

Deploy to Streamlit Cloud:
    1. Create a private repo with this file + requirements-streamlit.txt
    2. Connect to Streamlit Cloud (share.streamlit.io)
    3. Set secrets: SCORER_API_URL, STRIPE_PUBLISHABLE_KEY
"""

import os
import requests
import streamlit as st

# ─── Configuration ───
API_URL = os.getenv("SCORER_API_URL", "https://resume-scorer.fly.dev")


def api(method: str, endpoint: str, json_data: dict = None, token: str = None) -> dict:
    """Call the scorer API."""
    url = f"{API_URL.rstrip('/')}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        else:
            r = requests.post(url, json=json_data or {}, headers=headers, timeout=30)
        return {"status": r.status_code, "data": r.json()}
    except requests.RequestException as e:
        return {"status": 0, "data": {"detail": str(e)}}


# ─── Page config ───
st.set_page_config(
    page_title="Resume Scorer",
    page_icon="📄",
    layout="centered",
)

# ─── Custom CSS ───
st.markdown("""
<style>
    .stApp { background-color: #0f172a; }
    [data-testid="stHeader"] { background-color: #0f172a; }
    .score-card {
        background: #1e293b; border-radius: 12px; padding: 24px;
        text-align: center; border: 1px solid #334155;
    }
    .score-num { font-size: 36px; font-weight: 700; color: #818cf8; }
    .score-label { font-size: 12px; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ───
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None


def show_landing():
    """Landing page — unauthenticated."""
    st.title("📄 Resume Scorer")
    st.caption("AI-powered ATS + HR resume scoring — free to start")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="score-card"><div class="score-num">5</div><div class="score-label">FREE SCORES</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="score-card"><div class="score-num">8</div><div class="score-label">ATS COMPONENTS</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="score-card"><div class="score-num">6</div><div class="score-label">HR FACTORS</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    **How it works:**
    - Score resumes instantly — no API key needed for first 5 scores
    - ATS keyword matching + semantic similarity + BM25 ranking
    - HR recruiter simulation with career trajectory analysis
    - Domain auto-detection (tech, clinical, finance, consulting, healthcare)
    - Optional LLM-augmented scoring via Claude

    **Quick start** — paste this in your terminal:
    """)

    st.code(
        'curl -X POST https://resume-scorer.fly.dev/score/ats \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"resume_text":"Your resume...", "jd_text":"Job description..."}\'',
        language="bash",
    )

    st.markdown("---")

    st.markdown("**Want more than 5 scores?** Create a free account below, or upgrade to Pro ($12/month) for unlimited.")


def show_register():
    """Registration form."""
    st.subheader("Create Account")
    st.caption("Register to track usage and upgrade to Pro when ready.")

    with st.form("register_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Min 6 characters")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

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
            st.success("Account created!")
            st.info(f"Your JWT token (save it for API access):")
            st.code(data["token"], language=None)
            st.rerun()
        elif result["status"] == 409:
            st.error("Email already registered. Try logging in instead.")
        else:
            st.error(result["data"].get("detail", "Registration failed."))


def show_login():
    """Login form."""
    st.subheader("Login")
    st.caption("Sign in to view usage, create API keys, or manage billing.")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
            return

        with st.spinner("Logging in..."):
            result = api("POST", "/auth/login", {"email": email, "password": password})

        if result["status"] == 200:
            data = result["data"]
            st.session_state.token = data["token"]
            st.session_state.user = data["user"]
            st.success("Logged in!")
            st.rerun()
        else:
            st.error(result["data"].get("detail", "Login failed."))


def show_dashboard():
    """Authenticated user dashboard."""
    user = st.session_state.user
    token = st.session_state.token

    st.title("📊 Dashboard")
    st.caption(f"Logged in as **{user['email']}** · Tier: **{user['tier'].upper()}**")

    # Fetch usage stats
    usage = api("GET", "/auth/usage", token=token)

    if usage["status"] == 200:
        stats = usage["data"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Scores Used", stats.get("total_scores", 0))
        with col2:
            st.metric("Today", stats.get("today_scores", 0))
        with col3:
            remaining = stats.get("remaining")
            if remaining is not None:
                st.metric("Remaining (Free)", remaining)
            else:
                st.metric("Plan", "Pro ∞")
    else:
        st.warning("Could not fetch usage stats.")

    st.markdown("---")

    # API Key management
    st.subheader("API Keys")
    st.caption("Create an API key to use in your scripts or CI/CD pipeline.")

    with st.form("apikey_form"):
        label = st.text_input("Key label (optional)", placeholder="e.g. my-laptop")
        create_key = st.form_submit_button("Generate API Key")

    if create_key:
        with st.spinner("Generating..."):
            result = api("POST", "/auth/api-key", {"label": label}, token=token)

        if result["status"] == 200:
            st.success("API key created! Save it — it won't be shown again.")
            st.code(result["data"]["api_key"], language=None)
        else:
            st.error(result["data"].get("detail", "Failed to create key."))

    st.markdown("---")

    # Upgrade / Billing
    if user.get("tier") == "free":
        st.subheader("Upgrade to Pro")
        st.markdown("""
        **$12/month** — unlimited resume scoring

        - Unlimited ATS + HR + LLM scoring
        - Priority API access
        - Cancel anytime
        """)

        if st.button("Upgrade to Pro", use_container_width=True, type="primary"):
            with st.spinner("Creating checkout session..."):
                result = api("POST", "/billing/checkout", token=token)

            if result["status"] == 200 and "checkout_url" in result["data"]:
                st.markdown(f"[Click here to complete payment]({result['data']['checkout_url']})")
            elif result["status"] == 503:
                st.warning("Stripe billing is not configured yet. Contact the admin.")
            else:
                st.error(result["data"].get("detail", "Could not create checkout session."))
    else:
        st.subheader("Manage Subscription")
        if st.button("Open Billing Portal", use_container_width=True):
            with st.spinner("Opening portal..."):
                result = api("POST", "/billing/portal", token=token)

            if result["status"] == 200:
                url = result["data"] if isinstance(result["data"], str) else result["data"].get("url", "")
                if url:
                    st.markdown(f"[Open Stripe Portal]({url})")
                else:
                    st.warning("Could not get portal URL.")
            else:
                st.error(result["data"].get("detail", "Portal unavailable."))

    st.markdown("---")

    # Logout
    if st.button("Logout"):
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()


# ─── Main router ───
def main():
    if st.session_state.token and st.session_state.user:
        show_dashboard()
    else:
        show_landing()

        tab1, tab2 = st.tabs(["Register", "Login"])
        with tab1:
            show_register()
        with tab2:
            show_login()


if __name__ == "__main__":
    main()
