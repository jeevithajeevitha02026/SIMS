# Student Information Management System (SIMS)

A complete, production-ready, and deployment-configured **Student Information Management System (SIMS)** built with **Python (Flask)**, **SQLite3**, and **Vanilla HTML5, CSS3, and JavaScript**.

---

## 🌟 Overview & System Highlights

SIMS is tailored for arts, science, and engineering colleges, schools, and higher-education institutions. It provides Role-Based Access Control (RBAC) with dedicated portals for **Administrators**, **Faculty**, and **Students**.

### Core Architecture & Technical Highlights
* **Frontend:** Clean, responsive vanilla HTML5, CSS3, and JavaScript. Zero external JavaScript frameworks. Modern deep navy (`#0f172a` / `#1e3a8a`) and teal (`#0d9488`) design.
* **Backend:** Python 3 + Flask framework with session-based authentication, role decorators, and CSRF protection.
* **Database:** SQLite3 with relational foreign keys (`PRAGMA foreign_keys = ON;`), cascade deletions, and automatic performance indexes.
* **WSGI & Container Ready:** Includes `wsgi.py`, `Procfile`, `Dockerfile`, `.dockerignore`, `render.yaml`, and `runtime.txt`.
* **Currency:** Native Indian Rupees (**₹**) formatting throughout student fee invoices, payment records, and balance calculations.

---

## 🏫 Key Features

### 1. Student Portal
* **Dashboard:** Real-time summary of attendance percentage, fee balance status, upcoming classes with exact period timings, and quick links.
* **Letters & Requests System:** Students can compose formal applications to their faculty for:
  * **Leave Requests** (Medical / Sick / Personal)
  * **On Duty (OD)** (Symposiums, Sports, Inter-college events)
  * **Apology Letters** (Absence, conduct)
  * **Permissions** (Lab, Library, Early departure)
  * Displays real-time approval status (`Approved`, `Pending`, `Declined`) with faculty remarks and an official printable letterhead view.
* **Report Card & Transcript:** Printable official transcript branded with the college logo (`clglogo.jpg`), letter grades, GPAs, and conduct marks.
* **Timetable:** Displays the 5-period college day with exact period timings and tea break.
* **Security Restriction:** Student role is strictly prohibited from modifying passwords (enforced both in the UI and at the server route level).

### 2. Faculty Portal
* **Dashboard:** Assigned courses, total enrolled students, and today's schedule badge.
* **Student Mailbox:** Review incoming student applications (Leave, OD, Apology, Permission) with real-time pending notification counter badge.
  * Filter by *All*, *Pending*, *Approved*, and *Declined*.
  * Review official letter view, provide feedback/remarks, and click **Approve** or **Decline**.
* **Attendance System:** Mark daily student attendance (`Present`, `Absent`, `Late`, `Excused`) with 1-click batch shortcuts.
* **Examinations & Marks:** Enter exam scores, auto-calculate percentages and letter grades (A+, A, B, C, Fail).
* **Timetable:** View weekly lecture and practical lab commitments across classes.

### 3. Admin Portal
* **Analytics Dashboard:** Overall student count, faculty registry, fee collection metrics, and recent activity logs.
* **Student Management:** Full CRUD operations, roll number generation, and photo uploads.
* **Faculty Management:** Register professors and link departmental subjects.
* **Course Catalog:** Associate course subjects with cohorts and assigned faculty.
* **Fee Ledger:** Generate invoices in ₹, record partial or full payments, and download receipts.
* **Timetable Manager:** Interactive weekly schedule matrix with editable target class input and datalist auto-suggestions.

---

## ⏰ College Schedule (5-Period Timings)

Configured to the standard higher-education schedule:

| Period / Hour | Timing | Description |
| :--- | :--- | :--- |
| **Period 1** | `9:00 - 9:50 AM` | Morning Lecture Hour 1 |
| **Period 2** | `9:51 - 10:40 AM` | Morning Lecture Hour 2 |
| **Period 3** | `10:41 - 11:30 AM` | Morning Lecture Hour 3 |
| **Tea Break** | `11:30 - 11:40 AM` | Intermission / Recess |
| **Period 4** | `11:41 - 12:30 PM` | Afternoon Lecture / Lab Hour 4 |
| **Period 5** | `12:31 - 1:20 PM` | Afternoon Lecture / Lab Hour 5 |

* **Day Cycle:** 6 Day Orders (**Day Order I to Day Order VI** mapped to Monday through Saturday).
* **Preloaded Schedule:** Complete departmental schedule preloaded for **III BCA**, **II BCA**, and **I BCA**.

---

## 🔑 Default Credentials

The database auto-initializes on startup with default accounts:

| Role | Username | Password | Linked Profile / Details |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Institutional Administrator |
| **Faculty** | `prof_mahendran` | `faculty123` | Dr. T. Mahendran (Computer Applications) |
| **Faculty** | `prof_devikala` | `faculty123` | Dr. K. Devikala (Computer Applications) |
| **Faculty** | `prof_madhanmohan` | `faculty123` | Dr. S. Madhanmohan (Computer Applications) |
| **Student** | `bca046` | `student123` | Jeevitha (Roll: `bca046`, Class: `III BCA`) |

---

## 📂 Repository File Tree

```text
sims/
├── app.py                     # Core Flask application and route controllers
├── database.py                # Database connection, schema, auto-initializer & seeder
├── wsgi.py                    # Production WSGI entrypoint for Gunicorn/uWSGI
├── requirements.txt           # Python package dependencies
├── Procfile                   # Cloud process manager configuration (Render, Railway, Heroku)
├── Dockerfile                 # Production multi-stage Docker container specification
├── .dockerignore              # Docker build exclusions
├── render.yaml                # Render 1-click blueprint configuration
├── runtime.txt                # Pinned Python runtime (python-3.11.9)
├── .env.example               # Template for environment variables
├── .gitignore                 # Git ignore configuration
├── README.md                  # Comprehensive system documentation
├── sims.db                    # SQLite file database (auto-created on boot)
├── static/
│   ├── css/
│   │   └── style.css          # Responsive stylesheet (Deep Navy & Teal palette)
│   ├── js/
│   │   └── script.js          # Modal controls, sidebar toggles, table search
│   ├── images/
│   │   └── clglogo.jpg        # Official College Logo
│   └── uploads/               # Uploaded student avatars and photos
└── templates/
    ├── base.html              # Master layout with sidebar and role badges
    ├── login.html             # Login portal with 1-click credential auto-fill
    ├── admin_dashboard.html   # Admin analytical dashboard
    ├── faculty_dashboard.html # Faculty home with today's classes
    ├── faculty_mailbox.html   # Faculty student letters mailbox & review modal
    ├── student_dashboard.html # Student progress dashboard
    ├── student_letters.html   # Student formal letters & OD request composer
    ├── students.html          # Student directory & management
    ├── faculty.html           # Faculty member registry
    ├── courses.html           # Course catalog & faculty assignments
    ├── attendance.html        # Daily attendance register
    ├── marks.html             # Exam score records and grades
    ├── fees.html              # Fee invoicing and payment ledger (₹)
    ├── timetable.html         # Weekly timetable matrix (Day Order I - VI)
    ├── report_card.html       # Printable academic transcript with clglogo.jpg
    ├── change_password.html   # Password management (Admin & Faculty only)
    ├── 404.html               # 404 Not Found error page
    └── 500.html               # 500 Server Error page
```

---

## 🚀 Local Development Setup

### 1. Clone the repository
```bash
git clone https://github.com/jeevithajeevitha02026/SIMS.git
cd SIMS
```

### 2. Create and activate virtual environment
```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
```

### 5. Run development server
```bash
python app.py
```
Open your browser at `http://127.0.0.1:5000`.

---

## 🌐 Production Deployment Guide

### Option 1: Deploy to Render (Recommended)
1. Push this repository to your GitHub account.
2. Sign in to [Render](https://render.com).
3. Click **New +** &rarr; **Blueprint**.
4. Connect this repository; Render will automatically read `render.yaml`.
5. Click **Apply**. Your app will build and go live on a secure HTTPS URL with automatic SSL.

### Option 2: Deploy with Docker
```bash
# Build the Docker image
docker build -t sims:latest .

# Run the container
docker run -d -p 5000:5000 -e SECRET_KEY="your-production-secret-key" --name sims-app sims:latest
```
Access at `http://localhost:5000`.

### Option 3: Deploy to Linux VPS (Ubuntu/Debian) with Gunicorn & Nginx
```bash
# 1. Install system packages
sudo apt update && sudo apt install -y python3-venv python3-pip nginx

# 2. Clone and setup
git clone https://github.com/jeevithajeevitha02026/SIMS.git /var/www/sims
cd /var/www/sims
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Test WSGI server
gunicorn --bind 127.0.0.1:5000 wsgi:app
```
Configure Nginx as a reverse proxy to `127.0.0.1:5000` with systemd service managing Gunicorn.

---

## 🔒 Security Summary
* **Authentication:** Password hashes generated with secure scrypt/pbkdf2 algorithms.
* **SQL Injection Prevention:** 100% of database queries use parameterized SQL bindings (`?`).
* **CSRF Protection:** Cryptographic session-bound anti-CSRF tokens validated on all mutating HTTP POST endpoints.
* **Session Security:** `HTTPOnly` and `SameSite=Lax` cookie flags prevent client-side script inspection.
* **File Upload Safety:** Filenames sanitized via `secure_filename()`, extension whitelist enforced, and 2MB payload cap (`MAX_CONTENT_LENGTH`).
* **Role Guards:** Route-level decorators prevent unauthorized access between Admin, Faculty, and Student portals.

---

## 📄 License
Open source and available under the [MIT License](LICENSE).
