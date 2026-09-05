# 📓 Reflective Journal Assistant

A minimalist, calm, and distraction-free generative AI personal journal prompt and reflection assistant built with **Streamlit** and powered by the **Groq API** via the OpenAI-compatible endpoint.

---

## ✨ Features

1. **Personalized Journaling Prompt Generator**
   - Provide optional recent journal entries and select life focus areas (*Career*, *Relationships*, *Growth*, or custom focus).
   - Generates one thoughtful, personalized journaling prompt or question for self-reflection.

2. **Reflective Summary Across Past Entries**
   - Paste multiple past journal entries or reuse entries from Feature 1.
   - Generates an empathetic AI reflection identifying recurring themes, emotional threads, and personal growth patterns.

3. **Prompt-Only Mode (Free Writing Mode)**
   - Distraction-free writing experience.
   - Skips past entries and generates an open-ended journaling prompt directly based on your selected focus.
   - Features a clean writing canvas with **no AI feedback or analysis**—purely for free-form writing.

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **Streamlit**
- **Groq API** via `openai` SDK (`base_url="https://api.x.ai/v1"`)
- **python-dotenv**

---

## 🚀 Local Setup & Installation

### 1. Clone or navigate to the repository
```bash
cd path/to/reflective-journal-assistant
```

### 2. Create and activate a virtual environment (optional but recommended)
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install requirements
```bash
pip install -r requirements.txt
```

### 4. Configure your API key
Create or edit the `.env` file in the project root:
```env
GROQ_API_KEY=your-actual-api-key-here

### 5. Run the application
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deploying to Streamlit Community Cloud

1. **Push your code to GitHub**:
   Ensure `.env` is **not** committed (`.gitignore` protects this).
   ```bash
   git init
   git add app.py requirements.txt .gitignore README.md
   git commit -m "Initial commit of Reflective Journal Assistant"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and log in with GitHub.
   - Click **New app**, select your repository, branch (`main`), and set the main file path to `app.py`.
   - Before launching, open **Advanced Settings > Secrets**.
   - Paste your Groq API key:
     ```toml
     GROQ_API_KEY = "your-actual-api-key-here"
     ```
   - Click **Save** and **Deploy!**

The app will seamlessly detect `st.secrets["GROQ_API_KEY"]` on Streamlit Community Cloud!
