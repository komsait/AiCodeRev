# AiCodeRev

AiCodeRev is a comprehensive, AI-powered code review and repository management platform. It allows developers to seamlessly upload code, automatically run deep static analysis for code smells, generate AI-driven refactoring suggestions, and track changes using a fully integrated Git version control history.

---

## 📸 Screenshots

*(Note: Replace the placeholder image files in the `screenshots/` directory with your actual screenshots)*

### Dashboard
The main command center displaying repository health, critical smells, and recent activities.
![Dashboard Screenshot](screenshots/dashboard.png)

### Code Analysis Report
A detailed breakdown of identified code smells and architectural anti-patterns detected within your repository.
![Analysis Report Screenshot](screenshots/analysis_report.png)

### AI Refactoring Suggestions
View side-by-side comparisons of the original code and the AI-generated refactoring suggestions.
![Refactoring Screenshot](screenshots/refactoring.png)

### Commit History & Diff Viewer
A sleek Git interface to navigate your repository's timeline, view commit messages, and inspect file-by-file code diffs seamlessly.
![Commit History Screenshot](screenshots/commit_history.png)

---

## ✨ Features

- **Multi-LLM AI Integration:** Uses Gemini, OpenAI, or Anthropic models for intelligent code refactoring and smell detection.
- **Automated Code Analysis:** Scans codebases for anti-patterns like "God Class", "Long Method", and more.
- **Git Version Control Tracking:** Fully mimics standard Git operations, recording snapshots of your code and allowing intuitive diff viewing.
- **Interactive Diff Viewer:** A modern, side-by-side syntax-highlighted code comparison tool.
- **Project Workspaces:** Completely isolated repository environments for multiple users.
- **Exporting & Reporting:** Export your refactoring logs and analysis metrics for external use.

---

## 🛠️ Technology Stack

- **Backend:** Python, Django 4.2
- **Database:** PostgreSQL (Production) / SQLite (Development)
- **Version Control Engine:** GitPython
- **Frontend:** HTML5, CSS3 (Custom Design System), Vanilla JS, highlight.js
- **AI / Inference:** google-generativeai, openai, anthropic SDKs
- **Deployment & Orchestration:** Docker, Docker Compose, Gunicorn, WhiteNoise

---

## 🚀 Getting Started

You can run AiCodeRev locally either via standard Python environments or instantly via Docker.

### Option A: Running with Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/AiCodeRev.git
   cd AiCodeRev/code
   ```

2. **Set up Environment Variables:**
   Rename `.env.example.local` to `.env` and insert your API keys:
   ```bash
   cp .env.example.local .env
   ```

3. **Build and Run the Containers:**
   Docker Compose will automatically set up the Django web server and a PostgreSQL database.
   ```bash
   docker-compose up --build
   ```

4. **Run Migrations (On first boot):**
   In a separate terminal, apply the database migrations:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Access the App:**
   Open `http://localhost:8000` in your browser.

---

### Option B: Local Setup (Without Docker)

1. **Install PostgreSQL** (or stick to the default SQLite by removing `DATABASE_URL` from your env).
2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables:**
   Rename `.env.example.local` to `.env` and fill it out.
4. **Apply Migrations & Run Server:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## ☁️ Production Deployment (e.g., Railway / Render)

AiCodeRev is fully primed for modern PaaS deployment.

1. **Provision a PostgreSQL Database** on your platform.
2. **Set Environment Variables:**
   Add the following to your platform's dashboard (refer to `.env.example.production`):
   - `DATABASE_URL` (Provided by your Postgres service)
   - `SECRET_KEY` (Generate a strong random string)
   - `DEBUG=False`
   - `ALLOWED_HOSTS=your-app.railway.app`
   - `GEMINI_API_KEY` (or your preferred LLM key)
3. **Start Command:**
   Ensure your platform executes migrations before booting Gunicorn:
   ```bash
   python manage.py migrate && gunicorn --bind 0.0.0.0:$PORT core.wsgi:application
   ```

---

## 📝 License
This project is licensed under the MIT License.
