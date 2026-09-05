"""
Reflective Journal Assistant
----------------------------
A generative AI personal journal prompt and reflection assistant built with Streamlit
and powered by the Groq API (xAI) using the OpenAI-compatible endpoint.

Features:
1. Personalized Journaling Prompt Generator
2. Reflective Summary Across Past Entries
3. Prompt-Only Mode (Free Writing Mode)
"""

import os
import sqlite3
from datetime import datetime
from fpdf import FPDF
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------------------------------------------------
# SQLite Database Setup & Utility Functions
# -----------------------------------------------------------------------------
DB_FILE = "journal.db"

def init_db():
    """Create the journal.db file and entries table if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            text TEXT NOT NULL,
            focus_area TEXT,
            tags TEXT DEFAULT '',
            sentiment REAL DEFAULT 0.0
        )
    """)
    cursor.execute("PRAGMA table_info(entries)")
    cols = [col[1] for col in cursor.fetchall()]
    if "sentiment" not in cols:
        cursor.execute("ALTER TABLE entries ADD COLUMN sentiment REAL DEFAULT 0.0")
    conn.commit()
    conn.close()

def analyze_sentiment(text: str, api_key: str | None) -> float:
    """Ask LLM to return sentiment score between -1.0 (very negative) and +1.0 (very positive)."""
    if not api_key:
        print("[SENTIMENT DEBUG] No API key provided, defaulting to 0.0")
        return 0.0
    if not text or not text.strip():
        print("[SENTIMENT DEBUG] Empty text provided, defaulting to 0.0")
        return 0.0
    try:
        import re
        client = get_ai_client(api_key)
        system_msg = (
            "You are an expert sentiment analyzer. "
            "Analyze the emotional tone of the journal entry and output ONLY a single float number "
            "between -1.0 (extremely negative/distressed) and +1.0 (extremely positive/joyful). "
            "0.0 represents neutral. Do not write any explanations, labels, or extra text—ONLY the float score."
        )
        print(f"[DEBUG SENTIMENT] Sending LLM request for text snippet: {repr(text.strip()[:60])}...")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Text to analyze: {text.strip()}"}
            ],
            temperature=0.0,
            max_tokens=150
        )
        val = response.choices[0].message.content.strip()
        print(f"[DEBUG SENTIMENT] Raw LLM response: {repr(val)}")
        
        # Remove thinking tags if model outputs reasoning block
        if "</think>" in val:
            val = val.split("</think>")[-1].strip()
            print(f"[DEBUG SENTIMENT] Response after removing thinking block: {repr(val)}")

        matches = re.findall(r"[-+]?\d*\.?\d+", val)
        if matches:
            for candidate in reversed(matches):
                try:
                    score = float(candidate)
                    if -1.0 <= score <= 1.0:
                        print(f"[DEBUG SENTIMENT] Parsed sentiment score: {score:+.2f}")
                        return score
                except ValueError:
                    continue
        print(f"[SENTIMENT WARNING] Could not parse float between -1.0 and +1.0 from: {repr(val)}")
        return 0.0
    except Exception as e:
        print(f"[SENTIMENT ERROR] Exception in analyze_sentiment: {type(e).__name__}: {e}")
        st.error(f"⚠️ Sentiment Analysis Error: {str(e)}")
        return 0.0

def generate_followup_question(text: str, api_key: str | None) -> str | None:
    """Generate ONE gentle, optional follow-up question based on saved free-write entry."""
    if not api_key or not text or not text.strip():
        return None
    try:
        client = get_ai_client(api_key)
        system_msg = (
            "You are a gentle, supportive reflective journaling guide. "
            "The user just saved a free-write journal entry. Read what they wrote and craft "
            "ONE soft, open-ended follow-up reflection question to help them go slightly deeper if they wish. "
            "Return ONLY the question, with no introductory text or quotation marks."
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Saved entry: {text.strip()}"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None

def generate_pdf_bytes(title: str, text_content: str) -> bytes:
    """Generate a clean formatted PDF file as bytes using fpdf2."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title
    pdf.set_font("Helvetica", "B", 16)
    clean_title = title.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(0, 10, clean_title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)
    
    # Timestamp
    pdf.set_font("Helvetica", "I", 10)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.cell(0, 8, f"Generated: {now_str}".encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT", align="R")
    pdf.ln(6)
    
    # Body text
    pdf.set_font("Helvetica", "", 11)
    clean_text = text_content.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 7, clean_text)
    
    return bytes(pdf.output())

def save_entry(text: str, focus_area: str = "", tags: str = "", sentiment: float = 0.0) -> bool:
    """Insert a raw journal entry cleanly into the database with sentiment score."""
    if not text or not text.strip():
        return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO entries (date, text, focus_area, tags, sentiment) VALUES (?, ?, ?, ?, ?)",
        (now_str, text.strip(), focus_area.strip(), tags.strip(), float(sentiment))
    )
    conn.commit()
    conn.close()
    return True

def get_all_entries():
    """Retrieve all journal entries from database sorted by date descending."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, text, focus_area, tags, sentiment FROM entries ORDER BY date DESC, id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_recent_entries(limit: int = 5):
    """Retrieve last N journal entries from database sorted by date descending."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, text, focus_area, tags, sentiment FROM entries ORDER BY date DESC, id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_entries_last_7_days():
    """Retrieve journal entries from the last 7 days sorted chronologically."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, text, focus_area, tags, sentiment 
        FROM entries 
        WHERE date >= datetime('now', '-7 days')
        ORDER BY date ASC, id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Initialize database table on app launch
init_db()

# -----------------------------------------------------------------------------
# 1. Environment & API Key Configuration
# -----------------------------------------------------------------------------
# Load environment variables from the local .env file
load_dotenv()

def get_api_key() -> str | None:
    """
    Retrieve the Groq API key.
    Checks the local .env file first, then falls back to Streamlit secrets
    (for Streamlit Community Cloud deployment).
    """
    # 1. Check local environment variable
    api_key = os.getenv("GROQ_API_KEY")
    if api_key and api_key.strip() and api_key != "your_key_here":
        return api_key.strip()

    # 2. Fallback to Streamlit Community Cloud secrets
    try:
        if "GROQ_API_KEY" in st.secrets:
            secret_key = st.secrets["GROQ_API_KEY"]
            if secret_key and secret_key.strip() and secret_key != "your_key_here":
                return secret_key.strip()
    except Exception:
        pass

    return None


def get_ai_client(api_key: str) -> OpenAI:
    """
    Initialize the OpenAI client configured for the Groq API endpoint.
    """
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )


# -----------------------------------------------------------------------------
# 2. Page Setup & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Reflective Journal Assistant",
    page_icon="📓",
    layout="centered"
)

# App Title and Introduction
st.title("📓 Reflective Journal Assistant")
st.markdown(
    "A calm, mindful space to uncover thoughtful journaling prompts, "
    "discover reflections across your writing, or engage in distraction-free free writing."
)

# Verify API key availability
api_key = get_api_key()
if not api_key:
    st.warning(
        "⚠️ **Groq API Key not configured!**\n\n"
        "- **For local development:** Add `GROQ_API_KEY=your_actual_key` to your `.env` file.\n"
        "- **For Streamlit Cloud:** Add `GROQ_API_KEY = \"your_actual_key\"` under **App Settings > Secrets**."
    )

# Model configuration (xAI Grok model)
GROQ_MODEL = "openai/gpt-oss-120b"

# -----------------------------------------------------------------------------
# 3. Mode Selection: Prompt-Only Mode vs. Standard Mode
# -----------------------------------------------------------------------------
st.markdown("---")

prompt_only_mode = st.checkbox(
    "Prompt-Only Mode (just give me something to write about)",
    value=False,
    help="Skip entering past entries. Receive a direct, open-ended prompt and write freely without any AI analysis."
)

# =============================================================================
# FEATURE 3: Prompt-Only Mode (Free Writing Mode)
# =============================================================================
if prompt_only_mode:
    st.subheader("✍️ Free Writing Mode")
    st.caption("Select an optional focus area to receive a gentle prompt, then use the space below for distraction-free writing.")

    # Focus area options for prompt-only mode
    focus_selection = st.selectbox(
        "Life focus area:",
        ["Random / Open-ended", "Career", "Relationships", "Growth", "Custom..."]
    )

    custom_focus_text = ""
    if focus_selection == "Custom...":
        custom_focus_text = st.text_input("Enter your custom focus area:", placeholder="e.g., Mindfulness, Creative Passion, Life Transitions")

    # Determine focus description
    if focus_selection == "Custom..." and custom_focus_text.strip():
        active_focus = custom_focus_text.strip()
    elif focus_selection != "Random / Open-ended" and focus_selection != "Custom...":
        active_focus = focus_selection
    else:
        active_focus = "open-ended and contemplative"

    # Button to generate prompt
    if st.button("Generate Prompt", key="btn_free_prompt"):
        if not api_key:
            st.error("Please configure your Grok API key to generate prompts.")
        else:
            with st.spinner("Crafting a thoughtful journaling prompt..."):
                try:
                    client = get_ai_client(api_key)
                    system_prompt = (
                        "You are a compassionate, mindful journaling assistant. "
                        "Your job is to generate exactly ONE gentle, open-ended journaling prompt or question "
                        "designed to spark deep, reflective writing. "
                        "Return ONLY the prompt question itself. Do not include any introductory text, quotes, or explanations."
                    )
                    user_prompt = f"Focus Area: {active_focus}. Generate a single, inspiring journaling prompt."

                    print(f"[DEBUG] Exact model string being sent: {repr(GROQ_MODEL)}")
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=150
                    )
                    st.session_state["free_prompt"] = response.choices[0].message.content.strip()
                except Exception as e:
                    st.error(f"Error communicating with Groq API: {str(e)}")

    # Display generated prompt if available
    if "free_prompt" in st.session_state and st.session_state["free_prompt"]:
        st.info(f"💡 **Your Prompt:**\n\n{st.session_state['free_prompt']}")

        # Distraction-free writing area (no AI analysis or feedback)
        free_writing_text = st.text_area(
            "Distraction-Free Writing Area",
            height=300,
            placeholder="Let your thoughts flow freely here... (This area is purely for your own writing; no analysis will be performed).",
            key="free_writing_canvas"
        )
        if st.button("💾 Save Entry", key="btn_save_free_writing"):
            if free_writing_text and free_writing_text.strip():
                with st.spinner("Analyzing sentiment, generating follow-up & saving entry..."):
                    sentiment_score = analyze_sentiment(free_writing_text, api_key)
                    save_entry(free_writing_text, focus_area=active_focus, sentiment=sentiment_score)
                    followup_q = generate_followup_question(free_writing_text, api_key)
                    st.session_state["free_write_followup"] = followup_q
                st.success(f"✅ Journal entry saved successfully! (Mood score: {sentiment_score:+.2f})")
            else:
                st.warning("⚠️ Please write something in the entry area before saving.")

        if "free_write_followup" in st.session_state and st.session_state["free_write_followup"]:
            st.markdown("---")
            st.info(f"🌿 **Optional Reflection Follow-up:**\n\n{st.session_state['free_write_followup']}\n\n*(This question is completely optional — feel free to explore or ignore!)*")

# =============================================================================
# STANDARD MODE: Features 1 & 2
# =============================================================================
else:
    # -------------------------------------------------------------------------
    # FEATURE 1: Personalized Journaling Prompt Generator
    # -------------------------------------------------------------------------
    st.subheader("1. Personalized Journaling Prompt Generator")
    st.caption("Receive a customized journaling prompt tailored to your recent thoughts and life focus.")

    recent_entries = st.text_area(
        "Recent Journal Entries (optional):",
        placeholder="Paste or write recent thoughts, journal entries, or daily notes here to help personalize the prompt...",
        height=130,
        key="recent_entries_input"
    )
    focus_choices = st.multiselect(
    "Life focus area(s):",
    ["Career", "Relationships", "Growth", "Custom focus area..."],
    default=["Growth"]
)

    focus_summary = ", ".join(focus_choices)
    if st.button("💾 Save Entry", key="btn_save_recent_entry"):
        if recent_entries and recent_entries.strip():
            with st.spinner("Analyzing sentiment & saving entry..."):
                sentiment_score = analyze_sentiment(recent_entries, api_key)
                save_entry(recent_entries, focus_area=focus_summary, sentiment=sentiment_score)
            st.success(f"✅ Journal entry saved successfully! (Mood score: {sentiment_score:+.2f})")
        else:
            st.warning("⚠️ Please write or paste an entry before saving.")

    custom_entry_focus = ""
    if "Custom focus area..." in focus_choices:
        custom_entry_focus = st.text_input(
            "Specify your custom focus area:",
            placeholder="e.g., Creative expression, Mental well-being, Physical health",
            key="custom_entry_focus_input"
        )

    # Format selected focus areas
    cleaned_focus = [f for f in focus_choices if f != "Custom focus area..."]
    if custom_entry_focus.strip():
        cleaned_focus.append(custom_entry_focus.strip())
    focus_summary = ", ".join(cleaned_focus) if cleaned_focus else "General Self-Reflection"

    if st.button("Generate Prompt", key="btn_personalized_prompt"):
        if not api_key:
            st.error("Please configure your Grok API key to generate prompts.")
        else:
            with st.spinner("Generating your personalized prompt..."):
                try:
                    client = get_ai_client(api_key)
                    system_msg = (
                        "You are a perceptive, empathetic journaling assistant. "
                        "Create exactly ONE thoughtful, personalized journaling prompt/question based on the user's focus area "
                        "and their recent journal entries (if provided). "
                        "The prompt should invite deep self-discovery and introspective clarity. "
                        "Return ONLY the prompt text, without any conversational filler or quotation marks."
                    )
                    user_msg = f"Life Focus Area(s): {focus_summary}\n\n"
                    if recent_entries.strip():
                        user_msg += f"Recent Journal Entries:\n{recent_entries.strip()}"
                    else:
                        user_msg += "Recent Journal Entries: (None provided, craft an insightful prompt for this focus area)"

                    print(f"[DEBUG] Exact model string being sent: {repr(GROQ_MODEL)}")
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg}
                        ],
                        temperature=0.7,
                        max_tokens=150
                    )
                    st.session_state["personalized_prompt"] = response.choices[0].message.content.strip()
                except Exception as e:
                    st.error(f"Error communicating with Groq API: {str(e)}")

    # Display generated prompt
    if "personalized_prompt" in st.session_state and st.session_state["personalized_prompt"]:
        st.info(f"✨ **Personalized Prompt:**\n\n{st.session_state['personalized_prompt']}")

    # -------------------------------------------------------------------------
    # FEATURE 2: Reflective Summary Across Past Entries
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("2. Reflective Summary Across Past Entries")
    st.caption("Analyze multiple journal entries to identify recurring patterns, themes, and emotional threads.")

    # Option to choose entry source
    summary_source = st.radio(
        "Source for Reflection Summary:",
        ["Use saved entries from database", "Paste text manually / reuse Feature 1 text"],
        horizontal=True
    )

    if summary_source == "Use saved entries from database":
        n_entries = st.number_input("Number of recent saved entries to analyze:", min_value=1, max_value=50, value=5, step=1)
        db_rows = get_recent_entries(limit=int(n_entries))
        if db_rows:
            st.caption(f"Loaded {len(db_rows)} recent entries from database.")
            formatted_entries = []
            for entry_id, entry_date, entry_text, focus_area, tags, _ in reversed(db_rows):                 formatted_entries.append(f"[{entry_date} - Focus: {focus_area or 'General'}]\n{entry_text}")
            reflection_entries_text = "\n\n".join(formatted_entries)
        else:
            reflection_entries_text = ""
            st.info("No saved journal entries found in database yet. Save entries above first!")
    else:
        # Option to reuse entries from Feature 1
        reuse_entries = st.checkbox("Reuse recent entries from Feature 1 above", value=False)

        if reuse_entries:
            reflection_entries_text = recent_entries
            if recent_entries.strip():
                st.success("Using the entries pasted in Feature 1 above.")
            else:
                st.info("No entries found in Feature 1 yet. Type or paste your entries below or above.")
        else:
            reflection_entries_text = st.text_area(
                "Past Journal Entries:",
                placeholder="Paste multiple past journal entries, weekly notes, or reflections here...",
                height=160,
                key="reflection_entries_input"
            )

    if st.button("Generate Reflection Summary", key="btn_summary"):
        if not api_key:
            st.error("Please configure your Groq API key to generate reflections.")
        elif not reflection_entries_text.strip():
            st.warning("Please provide past journal entries to generate a reflective summary.")
        else:
            with st.spinner("Analyzing themes, patterns, and emotional threads across your entries..."):
                try:
                    client = get_ai_client(api_key)
                    system_msg = (
                        "You are an empathetic, insightful reflective journaling assistant. "
                        "Review the user's past journal entries and provide a friendly, short, and structured summary. "
                        "Identify:\n"
                        "1. Recurring Themes & Topics\n"
                        "2. Emotional Threads & Shifts\n"
                        "3. Gentle Insights for Personal Growth\n\n"
                        "Maintain a warm, encouraging, non-judgmental tone. Format clearly with bullet points."
                    )
                    user_msg = f"Here are my past journal entries for reflection:\n\n{reflection_entries_text.strip()}"

                    print(f"[DEBUG] Exact model string being sent: {repr(GROQ_MODEL)}")
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg}
                        ],
                        temperature=0.6,
                        max_tokens=600
                    )
                    st.session_state["reflection_summary"] = response.choices[0].message.content.strip()
                except Exception as e:
                    st.error(f"Error communicating with Grok API: {str(e)}")

    # Display generated reflective summary
    if "reflection_summary" in st.session_state and st.session_state["reflection_summary"]:
        st.markdown("### 🌿 Reflection Summary")
        st.markdown(st.session_state["reflection_summary"])
        
        summary_pdf = generate_pdf_bytes("Journal Reflection Summary", st.session_state["reflection_summary"])
        st.download_button(
            label="📄 Download Reflection Summary as PDF",
            data=summary_pdf,
            file_name="reflection_summary.pdf",
            mime="application/pdf",
            key="btn_dl_reflection_pdf"
        )

# -----------------------------------------------------------------------------
# Entry History View (Step 2)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📖 Journal Entry History")
with st.expander("Scroll through past saved entries", expanded=True):
    entries = get_all_entries()
    if not entries:
        st.info("No saved journal entries found yet. Write and save an entry above to see it here!")
    else:
        st.caption(f"Showing {len(entries)} saved entries (most recent first):")
        for row in entries:
            entry_id = row[0]
            entry_date = row[1]
            entry_text = row[2]
            focus_area = row[3]
            tags = row[4]
            sentiment_val = row[5] if len(row) > 5 and row[5] is not None else 0.0
            st.markdown(f"**🗓️ {entry_date}** &nbsp;|&nbsp; *Focus: {focus_area or 'General'}* &nbsp;|&nbsp; *Mood Score: {sentiment_val:+.2f}*")
            st.write(entry_text)
            if tags:
                st.caption(f"Tags: {tags}")
            
            entry_pdf = generate_pdf_bytes(
                f"Journal Entry #{entry_id}",
                f"Date: {entry_date}\nFocus Area: {focus_area or 'General'}\nMood Score: {sentiment_val:+.2f}\n\nEntry Content:\n{entry_text}"
            )
            st.download_button(
                label=f"📄 Download Entry #{entry_id} as PDF",
                data=entry_pdf,
                file_name=f"journal_entry_{entry_id}.pdf",
                mime="application/pdf",
                key=f"btn_dl_entry_pdf_{entry_id}"
            )
            st.divider()

# -----------------------------------------------------------------------------
# Mood Trend Visualization (Step 4)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 Mood & Sentiment Trend Over Time")
all_entries = get_all_entries()
if all_entries:
    import pandas as pd
    chart_data = []
    for r in reversed(all_entries):
        dt_str = r[1]
        sent_val = r[5] if len(r) > 5 and r[5] is not None else 0.0
        chart_data.append({"Date": dt_str, "Sentiment Score": sent_val})
    df_chart = pd.DataFrame(chart_data)
    if not df_chart.empty:
        df_chart.set_index("Date", inplace=True)
        st.line_chart(df_chart)
        st.caption("Sentiment Score scale: -1.0 (Very Negative) to +1.0 (Very Positive)")
else:
    st.info("No saved journal entries found to display mood trends.")

# -----------------------------------------------------------------------------
# Weekly Digest: Letter to Yourself (Step 5)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("💌 Weekly Digest: Letter to Yourself")
st.caption("Generate a warm, encouraging reflection letter summarizing your past 7 days of journal entries.")

if st.button("Generate My Weekly Letter", key="btn_weekly_letter"):
    if not api_key:
        st.error("Please configure your Grok API key to generate your weekly letter.")
    else:
        recent_7_days = get_entries_last_7_days()
        if not recent_7_days:
            # Fallback to recent entries if date range filter returns empty in test mode
            recent_7_days = get_recent_entries(limit=10)
        
        if not recent_7_days:
            st.warning("No saved journal entries found in database. Save some entries above first!")
        else:
            with st.spinner("Writing your warm weekly letter..."):
                try:
                    client = get_ai_client(api_key)
                    entry_blocks = []
                    for r in recent_7_days:
                        entry_blocks.append(f"[{r[1]} - Focus: {r[3] or 'General'}]\n{r[2]}")
                    combined_text = "\n\n".join(entry_blocks)

                    system_msg = (
                        "You are a compassionate, thoughtful journaling guide writing a 'letter to yourself'. "
                        "Read the user's journal entries from the past week and write a warm, encouraging, "
                        "and deeply reflective letter addressed to the user. Highlight their resilience, "
                        "emotional patterns, progress, and offer gentle encouragement for the week ahead. "
                        "Format it gracefully as a personal letter (e.g. starting with 'Dear Self,' or 'Dear Writer,')."
                    )
                    user_msg = f"Here are my journal entries from the past week:\n\n{combined_text}"

                    print(f"[DEBUG] Sending Groq API request for Weekly Letter with model: '{GROQ_MODEL}'")
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg}
                        ],
                        temperature=0.7,
                        max_tokens=700
                    )
                    st.session_state["weekly_letter"] = response.choices[0].message.content.strip()
                except Exception as e:
                    st.error(f"Error generating weekly letter: {str(e)}")

if "weekly_letter" in st.session_state and st.session_state["weekly_letter"]:
    st.markdown("### 💌 Your Weekly Reflection Letter")
    st.info(st.session_state["weekly_letter"])
    
    letter_pdf = generate_pdf_bytes("Weekly Reflection Letter", st.session_state["weekly_letter"])
    st.download_button(
        label="📄 Download Weekly Letter as PDF",
        data=letter_pdf,
        file_name="weekly_letter.pdf",
        mime="application/pdf",
        key="btn_dl_weekly_letter_pdf"
    )
