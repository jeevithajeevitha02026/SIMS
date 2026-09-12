"""
Student Information Management System (SIMS)
A complete, lightweight, and deployment-ready web application built with Flask and SQLite.
"""

import os
import secrets
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from database import get_db, close_db, init_db, seed_db

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Secret key configuration
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if os.getenv('FLASK_ENV') == 'production' and not os.getenv('FLASK_DEBUG'):
        secret_key = secrets.token_hex(32)
    else:
        secret_key = 'sims-default-development-secret-key-2026'
app.secret_key = secret_key

# Security & Session cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.getenv('FLASK_ENV') == 'production' and os.getenv('USE_HTTPS', '0') == '1':
    app.config['SESSION_COOKIE_SECURE'] = True

# File upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 Megabytes max

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Register database teardown
app.teardown_appcontext(close_db)

# Auto-initialize database on application boot
with app.app_context():
    try:
        init_db()
        seed_db()
    except Exception as e:
        print(f"[App Boot] Database setup note: {e}")


# ==============================================================================
# HELPER FUNCTIONS & DECORATORS
# ==============================================================================

def allowed_file(filename):
    """Check if uploaded file has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def calculate_grade(percentage):
    """Calculates letter grade, grade points, and remarks from percentage."""
    if percentage >= 90:
        return 'A+', 4.0, 'Outstanding'
    elif percentage >= 80:
        return 'A', 3.7, 'Excellent'
    elif percentage >= 70:
        return 'B+', 3.3, 'Very Good'
    elif percentage >= 60:
        return 'B', 3.0, 'Good'
    elif percentage >= 50:
        return 'C', 2.0, 'Average'
    elif percentage >= 40:
        return 'D', 1.0, 'Pass'
    else:
        return 'F', 0.0, 'Fail'


# Standard College Timetable Structure (5 Hours / Periods + Tea Break)
# 1st = 9:00 - 9:50, 2nd = 9:50 - 10:40, 3rd = 10:40 - 11:30
# Break = 11:30 - 11:40
# 4th = 11:40 - 12:30, 5th = 12:30 - 1:20
PERIODS = [1, 2, 3, 4, 5]
PERIOD_TIMINGS = {
    1: '9:00 - 9:50',
    2: '9:50 - 10:40',
    3: '10:40 - 11:30',
    4: '11:40 - 12:30',
    5: '12:30 - 1:20'
}
BREAK_TIMING = '11:30 - 11:40'


def get_csrf_token():
    """Generates and retrieves the active CSRF token for the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(24)
    return session['_csrf_token']


# Context processor to expose helpers & current user info to all templates
@app.context_processor
def inject_global_template_data():
    current_user = None
    pending_letters_count = 0
    if 'user_id' in session:
        current_user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'name': session.get('full_name', session.get('username')),
            'linked_id': session.get('linked_id')
        }
        if current_user['role'] == 'faculty' and current_user['linked_id']:
            try:
                db = get_db()
                row = db.execute(
                    "SELECT COUNT(*) FROM letters WHERE faculty_id = ? AND status = 'Pending'",
                    (current_user['linked_id'],)
                ).fetchone()
                if row:
                    pending_letters_count = row[0]
            except Exception:
                pass

    return {
        'csrf_token': get_csrf_token,
        'current_user': current_user,
        'now': datetime.now(),
        'periods': PERIODS,
        'period_timings': PERIOD_TIMINGS,
        'break_timing': BREAK_TIMING,
        'pending_letters_count': pending_letters_count
    }


# CSRF Verification Hook for POST requests
@app.before_request
def verify_csrf():
    if app.config.get('TESTING') and not app.config.get('WTF_CSRF_ENABLED', True):
        return
    if request.method == "POST":
        # Check token in form data or headers
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        session_token = session.get('_csrf_token')
        if not session_token or not token or token != session_token:
            # If token is invalid or missing, abort with 400
            flash('Security token invalid or expired. Please try again.', 'danger')
            return redirect(request.referrer or url_for('login'))


def login_required(f):
    """Restricts access to authenticated users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Restricts access based on user role (admin, faculty, student)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash('You do not have permission to access that resource.', 'danger')
                if user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user_role == 'faculty':
                    return redirect(url_for('faculty_dashboard'))
                elif user_role == 'student':
                    return redirect(url_for('student_dashboard'))
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==============================================================================
# AUTHENTICATION ROUTES
# ==============================================================================

@app.route('/')
def index():
    """Root redirector: routes logged-in users to their dashboard, otherwise to login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Single login page for Admin, Faculty, and Students. Role auto-detected."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please provide both username and password.', 'warning')
            return render_template('login.html')

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # Session assignment
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['linked_id'] = user['linked_id']
            session['_csrf_token'] = secrets.token_hex(24)

            # Retrieve user display name from linked table
            full_name = user['username']
            if user['role'] == 'faculty' and user['linked_id']:
                fac = db.execute("SELECT name FROM faculty WHERE id = ?", (user['linked_id'],)).fetchone()
                if fac:
                    full_name = fac['name']
            elif user['role'] == 'student' and user['linked_id']:
                stu = db.execute("SELECT name FROM students WHERE id = ?", (user['linked_id'],)).fetchone()
                if stu:
                    full_name = stu['name']
            elif user['role'] == 'admin':
                full_name = 'System Administrator'

            session['full_name'] = full_name
            flash(f'Welcome back, {full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logs out user and clears session."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Redirects user to their specific dashboard based on role."""
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'faculty':
        return redirect(url_for('faculty_dashboard'))
    elif role == 'student':
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allows Admin and Faculty to change their password. Students are restricted."""
    if session.get('role') == 'student':
        flash('Students are not permitted to change passwords. Please contact the administrator.', 'warning')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_password or not new_password:
            flash('All password fields are required.', 'warning')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'warning')
            return render_template('change_password.html')

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

        if not user or not check_password_hash(user['password_hash'], current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html')

        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, session['user_id']))
        db.commit()

        flash('Your password has been updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


# ==============================================================================
# ADMIN ROUTES
# ==============================================================================

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    """Admin Dashboard: Metrics, financial overview, and recent activity."""
    db = get_db()

    total_students = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_faculty = db.execute("SELECT COUNT(*) FROM faculty").fetchone()[0]
    total_courses = db.execute("SELECT COUNT(*) FROM courses").fetchone()[0]

    # Fee metrics
    fee_row = db.execute("""
        SELECT 
            COALESCE(SUM(amount_due), 0) AS total_due,
            COALESCE(SUM(amount_paid), 0) AS total_paid
        FROM fees
    """).fetchone()

    total_fee_due = fee_row['total_due']
    total_fee_paid = fee_row['total_paid']
    total_fee_pending = total_fee_due - total_fee_paid

    # Unpaid count
    unpaid_count = db.execute(
        "SELECT COUNT(*) FROM fees WHERE status != 'Paid'"
    ).fetchone()[0]

    # Recent student admissions
    recent_students = db.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 5"
    ).fetchall()

    # Classes summary
    classes_summary = db.execute("""
        SELECT class, COUNT(*) as count 
        FROM students 
        GROUP BY class 
        ORDER BY class
    """).fetchall()

    # Recent fee transactions
    recent_fees = db.execute("""
        SELECT f.*, s.name as student_name, s.roll_no, s.class 
        FROM fees f
        JOIN students s ON f.student_id = s.id
        ORDER BY f.id DESC LIMIT 5
    """).fetchall()

    return render_template(
        'admin_dashboard.html',
        total_students=total_students,
        total_faculty=total_faculty,
        total_courses=total_courses,
        total_fee_due=total_fee_due,
        total_fee_paid=total_fee_paid,
        total_fee_pending=total_fee_pending,
        unpaid_count=unpaid_count,
        recent_students=recent_students,
        classes_summary=classes_summary,
        recent_fees=recent_fees
    )


# --- Admin Student Management ---
@app.route('/admin/students')
@role_required('admin')
def admin_students():
    """Lists students with search and class filtering."""
    db = get_db()
    search_query = request.args.get('q', '').strip()
    class_filter = request.args.get('class', '').strip()

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if search_query:
        query += " AND (name LIKE ? OR roll_no LIKE ? OR contact LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term])

    if class_filter:
        query += " AND class = ?"
        params.append(class_filter)

    query += " ORDER BY class, roll_no"
    students = db.execute(query, params).fetchall()

    # Get distinct classes for filter dropdown
    classes = db.execute("SELECT DISTINCT class FROM students ORDER BY class").fetchall()

    return render_template(
        'students.html',
        students=students,
        classes=classes,
        search_query=search_query,
        selected_class=class_filter
    )


@app.route('/admin/students/add', methods=['POST'])
@role_required('admin')
def add_student():
    """Adds a new student and automatically generates login credentials."""
    name = request.form.get('name', '').strip()
    roll_no = request.form.get('roll_no', '').strip()
    s_class = request.form.get('class', '').strip()
    dob = request.form.get('dob', '').strip()
    contact = request.form.get('contact', '').strip()
    address = request.form.get('address', '').strip()
    password = request.form.get('password', '').strip() or 'student123'

    if not name or not roll_no or not s_class:
        flash('Name, Roll Number, and Class are required.', 'danger')
        return redirect(url_for('admin_students'))

    db = get_db()

    # Check for duplicate roll_no
    existing = db.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
    if existing:
        flash(f'Student with Roll No {roll_no} already exists.', 'danger')
        return redirect(url_for('admin_students'))

    # Check for duplicate user
    existing_user = db.execute("SELECT id FROM users WHERE username = ?", (roll_no,)).fetchone()
    if existing_user:
        flash(f'Username {roll_no} is already taken.', 'danger')
        return redirect(url_for('admin_students'))

    # Handle photo upload
    photo_filename = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"student_{roll_no}_{secrets.token_hex(4)}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            photo_filename = unique_name

    # Insert into students
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO students (name, dob, class, roll_no, contact, address, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, dob, s_class, roll_no, contact, address, photo_filename))
    student_id = cursor.lastrowid

    # Create user login account (username = roll_no)
    password_hash = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, linked_id)
        VALUES (?, ?, 'student', ?)
    """, (roll_no, password_hash, student_id))

    # Initialize a default fee record for the student
    cursor.execute("""
        INSERT INTO fees (student_id, amount_due, amount_paid, due_date, status)
        VALUES (?, 2500.0, 0.0, date('now', '+30 days'), 'Unpaid')
    """, (student_id,))

    db.commit()
    flash(f'Student {name} added successfully with username "{roll_no}".', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/students/edit/<int:student_id>', methods=['POST'])
@role_required('admin')
def edit_student(student_id):
    """Updates an existing student's details."""
    name = request.form.get('name', '').strip()
    s_class = request.form.get('class', '').strip()
    dob = request.form.get('dob', '').strip()
    contact = request.form.get('contact', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not s_class:
        flash('Name and Class are required.', 'danger')
        return redirect(url_for('admin_students'))

    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('admin_students'))

    photo_filename = student['photo_path']
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"student_{student['roll_no']}_{secrets.token_hex(4)}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            photo_filename = unique_name

    db.execute("""
        UPDATE students 
        SET name = ?, dob = ?, class = ?, contact = ?, address = ?, photo_path = ?
        WHERE id = ?
    """, (name, dob, s_class, contact, address, photo_filename, student_id))
    db.commit()

    flash(f'Student {name} updated successfully.', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    """Deletes a student and their associated user account."""
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if student:
        # Delete user account
        db.execute("DELETE FROM users WHERE role = 'student' AND linked_id = ?", (student_id,))
        # Delete student (cascades to attendance, marks, fees)
        db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        db.commit()
        flash(f'Student {student["name"]} ({student["roll_no"]}) was deleted.', 'success')
    else:
        flash('Student not found.', 'danger')
    return redirect(url_for('admin_students'))


# --- Admin Faculty Management ---
@app.route('/admin/faculty')
@role_required('admin')
def admin_faculty():
    """Lists all faculty members and assigned courses."""
    db = get_db()
    faculty_list = db.execute("""
        SELECT f.*, u.username,
               (SELECT GROUP_CONCAT(name, ', ') FROM courses WHERE faculty_id = f.id) AS assigned_courses
        FROM faculty f
        LEFT JOIN users u ON u.role = 'faculty' AND u.linked_id = f.id
        ORDER BY f.name
    """).fetchall()

    return render_template('faculty.html', faculty_list=faculty_list)


@app.route('/admin/faculty/add', methods=['POST'])
@role_required('admin')
def add_faculty():
    """Adds a faculty member and generates login credentials."""
    name = request.form.get('name', '').strip()
    subject = request.form.get('subject', '').strip()
    contact = request.form.get('contact', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip() or 'faculty123'

    if not name or not username:
        flash('Name and Username are required.', 'danger')
        return redirect(url_for('admin_faculty'))

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        flash(f'Username "{username}" is already taken.', 'danger')
        return redirect(url_for('admin_faculty'))

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO faculty (name, subject, contact) VALUES (?, ?, ?)",
        (name, subject, contact)
    )
    faculty_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO users (username, password_hash, role, linked_id)
        VALUES (?, ?, 'faculty', ?)
    """, (username, generate_password_hash(password), faculty_id))

    db.commit()
    flash(f'Faculty member {name} created with username "{username}".', 'success')
    return redirect(url_for('admin_faculty'))


@app.route('/admin/faculty/edit/<int:faculty_id>', methods=['POST'])
@role_required('admin')
def edit_faculty(faculty_id):
    """Edits faculty details."""
    name = request.form.get('name', '').strip()
    subject = request.form.get('subject', '').strip()
    contact = request.form.get('contact', '').strip()

    if not name:
        flash('Faculty name is required.', 'danger')
        return redirect(url_for('admin_faculty'))

    db = get_db()
    db.execute(
        "UPDATE faculty SET name = ?, subject = ?, contact = ? WHERE id = ?",
        (name, subject, contact, faculty_id)
    )
    db.commit()
    flash('Faculty updated successfully.', 'success')
    return redirect(url_for('admin_faculty'))


@app.route('/admin/faculty/delete/<int:faculty_id>', methods=['POST'])
@role_required('admin')
def delete_faculty(faculty_id):
    """Deletes a faculty member and their login account."""
    db = get_db()
    fac = db.execute("SELECT name FROM faculty WHERE id = ?", (faculty_id,)).fetchone()
    if fac:
        db.execute("DELETE FROM users WHERE role = 'faculty' AND linked_id = ?", (faculty_id,))
        db.execute("DELETE FROM faculty WHERE id = ?", (faculty_id,))
        db.commit()
        flash(f'Faculty member {fac["name"]} deleted.', 'success')
    return redirect(url_for('admin_faculty'))


# --- Admin Course Management ---
@app.route('/admin/courses')
@role_required('admin')
def admin_courses():
    """Lists courses and lets admin assign faculty."""
    db = get_db()
    courses = db.execute("""
        SELECT c.*, f.name AS faculty_name,
               (SELECT COUNT(*) FROM students s WHERE s.class = c.class) AS student_count
        FROM courses c
        LEFT JOIN faculty f ON c.faculty_id = f.id
        ORDER BY c.class, c.name
    """).fetchall()

    faculty_list = db.execute("SELECT id, name FROM faculty ORDER BY name").fetchall()
    classes = db.execute("SELECT DISTINCT class FROM students ORDER BY class").fetchall()

    return render_template(
        'courses.html',
        courses=courses,
        faculty_list=faculty_list,
        classes=classes
    )


@app.route('/admin/courses/add', methods=['POST'])
@role_required('admin')
def add_course():
    """Creates a new course."""
    name = request.form.get('name', '').strip()
    c_class = request.form.get('class', '').strip()
    faculty_id = request.form.get('faculty_id') or None

    if not name or not c_class:
        flash('Course name and Class are required.', 'danger')
        return redirect(url_for('admin_courses'))

    db = get_db()
    db.execute(
        "INSERT INTO courses (name, class, faculty_id) VALUES (?, ?, ?)",
        (name, c_class, faculty_id)
    )
    db.commit()
    flash(f'Course "{name}" created successfully.', 'success')
    return redirect(url_for('admin_courses'))


@app.route('/admin/courses/edit/<int:course_id>', methods=['POST'])
@role_required('admin')
def edit_course(course_id):
    """Edits an existing course."""
    name = request.form.get('name', '').strip()
    c_class = request.form.get('class', '').strip()
    faculty_id = request.form.get('faculty_id') or None

    if not name or not c_class:
        flash('Course name and Class are required.', 'danger')
        return redirect(url_for('admin_courses'))

    db = get_db()
    db.execute(
        "UPDATE courses SET name = ?, class = ?, faculty_id = ? WHERE id = ?",
        (name, c_class, faculty_id, course_id)
    )
    db.commit()
    flash(f'Course updated successfully.', 'success')
    return redirect(url_for('admin_courses'))


@app.route('/admin/courses/delete/<int:course_id>', methods=['POST'])
@role_required('admin')
def delete_course(course_id):
    """Deletes a course."""
    db = get_db()
    db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    db.commit()
    flash('Course deleted successfully.', 'success')
    return redirect(url_for('admin_courses'))


# --- Admin Fee Management ---
@app.route('/admin/fees')
@role_required('admin')
def admin_fees():
    """Manages student fees, records payments, and filters by status."""
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    class_filter = request.args.get('class', '').strip()
    search_query = request.args.get('q', '').strip()

    query = """
        SELECT f.*, s.name as student_name, s.roll_no, s.class 
        FROM fees f
        JOIN students s ON f.student_id = s.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND f.status = ?"
        params.append(status_filter)

    if class_filter:
        query += " AND s.class = ?"
        params.append(class_filter)

    if search_query:
        query += " AND (s.name LIKE ? OR s.roll_no LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term])

    query += " ORDER BY f.id DESC"
    fee_records = db.execute(query, params).fetchall()

    students = db.execute("SELECT id, name, roll_no, class FROM students ORDER BY name").fetchall()
    classes = db.execute("SELECT DISTINCT class FROM students ORDER BY class").fetchall()

    # Fee totals
    stats = db.execute("""
        SELECT 
            COALESCE(SUM(amount_due), 0) as total_due,
            COALESCE(SUM(amount_paid), 0) as total_paid
        FROM fees
    """).fetchone()

    total_due = stats['total_due']
    total_paid = stats['total_paid']
    total_pending = total_due - total_paid

    return render_template(
        'fees.html',
        fee_records=fee_records,
        students=students,
        classes=classes,
        selected_status=status_filter,
        selected_class=class_filter,
        search_query=search_query,
        total_due=total_due,
        total_paid=total_paid,
        total_pending=total_pending
    )


@app.route('/admin/fees/add', methods=['POST'])
@role_required('admin')
def add_fee():
    """Assigns a new fee obligation to a student."""
    student_id = request.form.get('student_id')
    amount_due = float(request.form.get('amount_due', 0))
    amount_paid = float(request.form.get('amount_paid', 0))
    due_date = request.form.get('due_date', '')

    if not student_id or amount_due <= 0:
        flash('Valid student and due amount are required.', 'danger')
        return redirect(url_for('admin_fees'))

    if amount_paid >= amount_due:
        status = 'Paid'
    elif amount_paid > 0:
        status = 'Partial'
    else:
        status = 'Unpaid'

    db = get_db()
    db.execute("""
        INSERT INTO fees (student_id, amount_due, amount_paid, due_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (student_id, amount_due, amount_paid, due_date, status))
    db.commit()

    flash('Fee record added successfully.', 'success')
    return redirect(url_for('admin_fees'))


@app.route('/admin/fees/pay/<int:fee_id>', methods=['POST'])
@role_required('admin')
def record_payment(fee_id):
    """Records a payment against an existing fee entry."""
    payment_amount = float(request.form.get('payment_amount', 0))

    if payment_amount <= 0:
        flash('Payment amount must be greater than zero.', 'warning')
        return redirect(url_for('admin_fees'))

    db = get_db()
    fee = db.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    if not fee:
        flash('Fee record not found.', 'danger')
        return redirect(url_for('admin_fees'))

    new_paid = fee['amount_paid'] + payment_amount
    due = fee['amount_due']

    if new_paid >= due:
        status = 'Paid'
        new_paid = due  # cap at due amount
    elif new_paid > 0:
        status = 'Partial'
    else:
        status = 'Unpaid'

    db.execute("""
        UPDATE fees 
        SET amount_paid = ?, status = ?
        WHERE id = ?
    """, (new_paid, status, fee_id))
    db.commit()

    flash(f'Payment of ₹{payment_amount:,.2f} recorded successfully.', 'success')
    return redirect(url_for('admin_fees'))


@app.route('/admin/fees/delete/<int:fee_id>', methods=['POST'])
@role_required('admin')
def delete_fee(fee_id):
    """Deletes a fee record."""
    db = get_db()
    db.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
    db.commit()
    flash('Fee record deleted.', 'success')
    return redirect(url_for('admin_fees'))


# --- Admin & General Timetable Management ---
@app.route('/admin/timetable')
@role_required('admin')
def admin_timetable():
    """Timetable management interface for Admin."""
    db = get_db()
    # Distinct classes from students, courses, and existing timetable entries
    classes_rows = db.execute("""
        SELECT DISTINCT class FROM (
            SELECT class FROM students WHERE class IS NOT NULL AND class != ''
            UNION
            SELECT class FROM courses WHERE class IS NOT NULL AND class != ''
            UNION
            SELECT class FROM timetable WHERE class IS NOT NULL AND class != ''
        ) ORDER BY class
    """).fetchall()

    default_class = classes_rows[0]['class'] if classes_rows else 'CS-Year1'
    selected_class = request.args.get('class', default_class).strip() or default_class

    timetable_entries = db.execute("""
        SELECT t.*, f.name as faculty_name 
        FROM timetable t
        LEFT JOIN faculty f ON t.faculty_id = f.id
        WHERE t.class = ?
        ORDER BY 
            CASE t.day 
                WHEN 'Monday' THEN 1 
                WHEN 'Tuesday' THEN 2 
                WHEN 'Wednesday' THEN 3 
                WHEN 'Thursday' THEN 4 
                WHEN 'Friday' THEN 5 
                WHEN 'Saturday' THEN 6 
                ELSE 7 
            END,
            t.period
    """, (selected_class,)).fetchall()

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    schedule = {day: {p: None for p in PERIODS} for day in days}
    for item in timetable_entries:
        if item['day'] in schedule and item['period'] in schedule[item['day']]:
            schedule[item['day']][item['period']] = item

    faculty_list = db.execute("SELECT id, name FROM faculty ORDER BY name").fetchall()

    return render_template(
        'timetable.html',
        schedule=schedule,
        days=days,
        periods=PERIODS,
        period_timings=PERIOD_TIMINGS,
        break_timing=BREAK_TIMING,
        selected_class=selected_class,
        classes=classes_rows,
        faculty_list=faculty_list,
        timetable_entries=timetable_entries
    )


@app.route('/admin/timetable/add', methods=['POST'])
@role_required('admin')
def add_timetable():
    """Adds or updates a timetable slot."""
    t_class = request.form.get('class', '').strip()
    day = request.form.get('day', '').strip()
    period = int(request.form.get('period', 1))
    subject = request.form.get('subject', '').strip()
    faculty_id = request.form.get('faculty_id') or None

    if not t_class or not day or not subject:
        flash('Class, Day, and Subject are required.', 'danger')
        return redirect(url_for('admin_timetable', **{'class': t_class or 'CS-Year1'}))

    if period not in PERIODS:
        flash('Invalid period selected. College schedule supports Periods 1 to 5.', 'danger')
        return redirect(url_for('admin_timetable', **{'class': t_class}))

    db = get_db()
    # Check if a slot already exists for that class, day, and period
    existing = db.execute("""
        SELECT id FROM timetable WHERE class = ? AND day = ? AND period = ?
    """, (t_class, day, period)).fetchone()

    if existing:
        db.execute("""
            UPDATE timetable SET subject = ?, faculty_id = ?
            WHERE id = ?
        """, (subject, faculty_id, existing['id']))
        flash(f'Timetable slot for {t_class} ({day} Period {period}) updated successfully.', 'success')
    else:
        db.execute("""
            INSERT INTO timetable (class, day, period, subject, faculty_id)
            VALUES (?, ?, ?, ?, ?)
        """, (t_class, day, period, subject, faculty_id))
        flash(f'Timetable slot for {t_class} ({day} Period {period}) added successfully.', 'success')

    db.commit()
    return redirect(url_for('admin_timetable', **{'class': t_class}))


@app.route('/admin/timetable/delete/<int:item_id>', methods=['POST'])
@role_required('admin')
def delete_timetable(item_id):
    """Deletes a timetable slot."""
    db = get_db()
    entry = db.execute("SELECT class FROM timetable WHERE id = ?", (item_id,)).fetchone()
    t_class = entry['class'] if entry else 'CS-Year1'
    db.execute("DELETE FROM timetable WHERE id = ?", (item_id,))
    db.commit()
    flash('Timetable slot cleared.', 'success')
    return redirect(url_for('admin_timetable', **{'class': t_class}))


# ==============================================================================
# FACULTY ROUTES
# ==============================================================================

@app.route('/faculty/dashboard')
@role_required('faculty')
def faculty_dashboard():
    """Faculty dashboard showing assigned courses, student counts, and schedule."""
    db = get_db()
    faculty_id = session.get('linked_id')

    faculty_info = db.execute(
        "SELECT * FROM faculty WHERE id = ?", (faculty_id,)
    ).fetchone()

    # Assigned courses
    courses = db.execute("""
        SELECT c.*, 
               (SELECT COUNT(*) FROM students s WHERE s.class = c.class) AS student_count
        FROM courses c 
        WHERE c.faculty_id = ?
        ORDER BY c.name
    """, (faculty_id,)).fetchall()

    # Today's timetable
    day_name = datetime.now().strftime('%A')
    today_schedule = db.execute("""
        SELECT * FROM timetable 
        WHERE faculty_id = ? AND day = ?
        ORDER BY period
    """, (faculty_id, day_name)).fetchall()

    # Total students across taught classes
    taught_classes = [c['class'] for c in courses]
    total_students = 0
    if taught_classes:
        placeholders = ', '.join(['?'] * len(taught_classes))
        total_students = db.execute(
            f"SELECT COUNT(DISTINCT id) FROM students WHERE class IN ({placeholders})",
            taught_classes
        ).fetchone()[0]

    return render_template(
        'faculty_dashboard.html',
        faculty_info=faculty_info,
        courses=courses,
        today_schedule=today_schedule,
        day_name=day_name,
        total_students=total_students
    )


# --- Faculty Attendance Management ---
@app.route('/faculty/attendance', methods=['GET', 'POST'])
@role_required('faculty', 'admin')
def faculty_attendance():
    """Faculty marks daily attendance per subject/class."""
    db = get_db()
    faculty_id = session.get('linked_id')
    user_role = session.get('role')

    # Available courses for this faculty (or all courses if admin)
    if user_role == 'admin':
        courses = db.execute("SELECT * FROM courses ORDER BY name").fetchall()
    else:
        courses = db.execute(
            "SELECT * FROM courses WHERE faculty_id = ? ORDER BY name",
            (faculty_id,)
        ).fetchall()

    # Selected course and date
    selected_course_id = request.args.get('course_id') or (courses[0]['id'] if courses else None)
    if selected_course_id:
        selected_course_id = int(selected_course_id)

    selected_date = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')

    current_course = None
    students_roster = []
    attendance_stats = {'present': 0, 'absent': 0, 'late': 0, 'total': 0}

    if selected_course_id:
        current_course = db.execute(
            "SELECT * FROM courses WHERE id = ?", (selected_course_id,)
        ).fetchone()

        if current_course:
            # Fetch students in the course's class, alongside their attendance status for this date
            students_roster = db.execute("""
                SELECT s.id, s.name, s.roll_no, s.class, s.photo_path,
                       COALESCE(a.status, 'Present') AS attendance_status
                FROM students s
                LEFT JOIN attendance a 
                    ON a.student_id = s.id 
                    AND a.course_id = ? 
                    AND a.date = ?
                WHERE s.class = ?
                ORDER BY s.roll_no
            """, (selected_course_id, selected_date, current_course['class'])).fetchall()

            for s in students_roster:
                status = s['attendance_status']
                attendance_stats['total'] += 1
                if status == 'Present':
                    attendance_stats['present'] += 1
                elif status == 'Absent':
                    attendance_stats['absent'] += 1
                elif status == 'Late':
                    attendance_stats['late'] += 1

    # Form submission: Save attendance for roster
    if request.method == 'POST':
        course_id = int(request.form.get('course_id'))
        date = request.form.get('date')

        # Find all student status fields in request form: status_<student_id>
        for key, value in request.form.items():
            if key.startswith('status_'):
                student_id = int(key.split('_')[1])
                status = value.strip()
                if status in ['Present', 'Absent', 'Late', 'Excused']:
                    db.execute("""
                        INSERT INTO attendance (student_id, course_id, date, status)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(student_id, course_id, date)
                        DO UPDATE SET status = excluded.status
                    """, (student_id, course_id, date, status))

        db.commit()
        flash(f'Attendance recorded successfully for {date}.', 'success')
        return redirect(url_for('faculty_attendance', course_id=course_id, date=date))

    return render_template(
        'attendance.html',
        courses=courses,
        selected_course_id=selected_course_id,
        current_course=current_course,
        selected_date=selected_date,
        students_roster=students_roster,
        attendance_stats=attendance_stats
    )


# --- Faculty Marks Entry ---
@app.route('/faculty/marks', methods=['GET', 'POST'])
@role_required('faculty', 'admin')
def faculty_marks():
    """Faculty enters and updates exam marks per course."""
    db = get_db()
    faculty_id = session.get('linked_id')
    user_role = session.get('role')

    if user_role == 'admin':
        courses = db.execute("SELECT * FROM courses ORDER BY name").fetchall()
    else:
        courses = db.execute(
            "SELECT * FROM courses WHERE faculty_id = ? ORDER BY name",
            (faculty_id,)
        ).fetchall()

    selected_course_id = request.args.get('course_id') or (courses[0]['id'] if courses else None)
    if selected_course_id:
        selected_course_id = int(selected_course_id)

    selected_exam = request.args.get('exam_name', 'Midterm Examination')

    current_course = None
    marks_roster = []

    if selected_course_id:
        current_course = db.execute(
            "SELECT * FROM courses WHERE id = ?", (selected_course_id,)
        ).fetchone()

        if current_course:
            marks_roster = db.execute("""
                SELECT s.id, s.name, s.roll_no, s.class,
                       m.marks_obtained, m.total_marks
                FROM students s
                LEFT JOIN marks m 
                    ON m.student_id = s.id 
                    AND m.course_id = ? 
                    AND m.exam_name = ?
                WHERE s.class = ?
                ORDER BY s.roll_no
            """, (selected_course_id, selected_exam, current_course['class'])).fetchall()

    # Form submission: save marks
    if request.method == 'POST':
        course_id = int(request.form.get('course_id'))
        exam_name = request.form.get('exam_name', '').strip()
        default_total = float(request.form.get('default_total', 100))

        if not exam_name:
            flash('Exam name is required.', 'danger')
            return redirect(url_for('faculty_marks', course_id=course_id))

        for key, value in request.form.items():
            if key.startswith('marks_') and value != '':
                student_id = int(key.split('_')[1])
                try:
                    obtained = float(value)
                    total_field = request.form.get(f'total_{student_id}', default_total)
                    total = float(total_field) if total_field else default_total

                    if obtained > total:
                        flash(f'Marks obtained cannot exceed total marks for student #{student_id}.', 'warning')
                        continue

                    db.execute("""
                        INSERT INTO marks (student_id, course_id, exam_name, marks_obtained, total_marks)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(student_id, course_id, exam_name)
                        DO UPDATE SET marks_obtained = excluded.marks_obtained, total_marks = excluded.total_marks
                    """, (student_id, course_id, exam_name, obtained, total))
                except ValueError:
                    continue

        db.commit()
        flash(f'Marks saved successfully for {exam_name}.', 'success')
        return redirect(url_for('faculty_marks', course_id=course_id, exam_name=exam_name))

    # Standard exam types for the dropdown
    exam_types = ['Midterm Examination', 'Final Examination', 'Unit Test 1', 'Unit Test 2', 'Assignment Project']

    return render_template(
        'marks.html',
        courses=courses,
        selected_course_id=selected_course_id,
        current_course=current_course,
        selected_exam=selected_exam,
        marks_roster=marks_roster,
        exam_types=exam_types
    )


@app.route('/faculty/timetable')
@role_required('faculty')
def faculty_timetable():
    """Weekly timetable for faculty members."""
    db = get_db()
    faculty_id = session.get('linked_id')

    timetable_entries = db.execute("""
        SELECT * FROM timetable 
        WHERE faculty_id = ?
        ORDER BY 
            CASE day 
                WHEN 'Monday' THEN 1 
                WHEN 'Tuesday' THEN 2 
                WHEN 'Wednesday' THEN 3 
                WHEN 'Thursday' THEN 4 
                WHEN 'Friday' THEN 5 
                WHEN 'Saturday' THEN 6 
                ELSE 7 
            END,
            period
    """, (faculty_id,)).fetchall()

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    schedule = {day: {p: None for p in PERIODS} for day in days}
    for item in timetable_entries:
        if item['day'] in schedule and item['period'] in schedule[item['day']]:
            schedule[item['day']][item['period']] = item

    return render_template(
        'timetable.html',
        schedule=schedule,
        days=days,
        periods=PERIODS,
        period_timings=PERIOD_TIMINGS,
        break_timing=BREAK_TIMING,
        view_only=True
    )


# ==============================================================================
# STUDENT ROUTES
# ==============================================================================

@app.route('/student/dashboard')
@role_required('student')
def student_dashboard():
    """Student Dashboard: Attendance, marks, fees, and today's schedule."""
    db = get_db()
    student_id = session.get('linked_id')

    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('logout'))

    # Overall Attendance %
    attendance_records = db.execute(
        "SELECT status FROM attendance WHERE student_id = ?", (student_id,)
    ).fetchall()
    total_classes = len(attendance_records)
    attended_classes = sum(1 for a in attendance_records if a['status'] in ['Present', 'Late'])
    attendance_pct = round((attended_classes / total_classes * 100), 1) if total_classes > 0 else 0

    # Fee Summary
    fee_row = db.execute("""
        SELECT 
            COALESCE(SUM(amount_due), 0) as total_due,
            COALESCE(SUM(amount_paid), 0) as total_paid
        FROM fees WHERE student_id = ?
    """, (student_id,)).fetchone()
    fee_due = fee_row['total_due']
    fee_paid = fee_row['total_paid']
    fee_pending = fee_due - fee_paid

    # Latest Exam Marks
    recent_marks = db.execute("""
        SELECT m.*, c.name as course_name 
        FROM marks m
        JOIN courses c ON m.course_id = c.id
        WHERE m.student_id = ?
        ORDER BY m.id DESC LIMIT 4
    """, (student_id,)).fetchall()

    # Today's timetable
    day_name = datetime.now().strftime('%A')
    today_schedule = db.execute("""
        SELECT t.*, f.name as faculty_name
        FROM timetable t
        LEFT JOIN faculty f ON t.faculty_id = f.id
        WHERE t.class = ? AND t.day = ?
        ORDER BY t.period
    """, (student['class'], day_name)).fetchall()

    return render_template(
        'student_dashboard.html',
        student=student,
        attendance_pct=attendance_pct,
        total_classes=total_classes,
        attended_classes=attended_classes,
        fee_due=fee_due,
        fee_paid=fee_paid,
        fee_pending=fee_pending,
        recent_marks=recent_marks,
        today_schedule=today_schedule,
        day_name=day_name
    )


@app.route('/student/attendance')
@role_required('student')
def student_attendance():
    """Detailed view of student's own attendance records and percentages."""
    db = get_db()
    student_id = session.get('linked_id')

    # Subject-wise attendance breakdown
    subject_stats = db.execute("""
        SELECT 
            c.id AS course_id,
            c.name AS course_name,
            COUNT(a.id) AS total_sessions,
            SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS attended_sessions,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_sessions
        FROM courses c
        JOIN students s ON s.class = c.class AND s.id = ?
        LEFT JOIN attendance a ON a.course_id = c.id AND a.student_id = s.id
        GROUP BY c.id, c.name
        ORDER BY c.name
    """, (student_id,)).fetchall()

    # Overall totals
    all_attendance = db.execute(
        "SELECT * FROM attendance WHERE student_id = ? ORDER BY date DESC",
        (student_id,)
    ).fetchall()
    total_sessions = len(all_attendance)
    total_attended = sum(1 for a in all_attendance if a['status'] in ['Present', 'Late'])
    overall_pct = round((total_attended / total_sessions * 100), 1) if total_sessions > 0 else 0

    # Detailed history log
    attendance_logs = db.execute("""
        SELECT a.*, c.name as course_name 
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.date DESC
    """, (student_id,)).fetchall()

    return render_template(
        'attendance.html',
        student_mode=True,
        subject_stats=subject_stats,
        overall_pct=overall_pct,
        total_sessions=total_sessions,
        total_attended=total_attended,
        attendance_logs=attendance_logs
    )


@app.route('/student/marks')
@role_required('student')
def student_marks():
    """Detailed report of marks, grades, and link to printable report card."""
    db = get_db()
    student_id = session.get('linked_id')

    marks_data = db.execute("""
        SELECT m.*, c.name as course_name 
        FROM marks m
        JOIN courses c ON m.course_id = c.id
        WHERE m.student_id = ?
        ORDER BY m.exam_name, c.name
    """, (student_id,)).fetchall()

    # Compute percentage and letter grade for each
    processed_marks = []
    total_points = 0
    total_courses = 0

    for m in marks_data:
        pct = round((m['marks_obtained'] / m['total_marks'] * 100), 1) if m['total_marks'] > 0 else 0
        letter, grade_point, remark = calculate_grade(pct)
        processed_marks.append({
            'exam_name': m['exam_name'],
            'course_name': m['course_name'],
            'marks_obtained': m['marks_obtained'],
            'total_marks': m['total_marks'],
            'percentage': pct,
            'grade': letter,
            'remark': remark
        })
        total_points += grade_point
        total_courses += 1

    gpa = round(total_points / total_courses, 2) if total_courses > 0 else 0.0

    return render_template(
        'marks.html',
        student_mode=True,
        marks=processed_marks,
        gpa=gpa,
        student_id=student_id
    )


@app.route('/student/fees')
@role_required('student')
def student_fees():
    """Student fee status and payment history."""
    db = get_db()
    student_id = session.get('linked_id')

    fees = db.execute("""
        SELECT * FROM fees WHERE student_id = ? ORDER BY id DESC
    """, (student_id,)).fetchall()

    total_due = sum(f['amount_due'] for f in fees)
    total_paid = sum(f['amount_paid'] for f in fees)
    total_pending = total_due - total_paid

    return render_template(
        'fees.html',
        student_mode=True,
        fee_records=fees,
        total_due=total_due,
        total_paid=total_paid,
        total_pending=total_pending
    )


@app.route('/student/timetable')
@role_required('student')
def student_timetable():
    """Weekly class timetable for the student's enrolled class."""
    db = get_db()
    student_id = session.get('linked_id')
    student = db.execute("SELECT class FROM students WHERE id = ?", (student_id,)).fetchone()
    student_class = student['class'] if student else 'CS-Year1'

    timetable_entries = db.execute("""
        SELECT t.*, f.name as faculty_name 
        FROM timetable t
        LEFT JOIN faculty f ON t.faculty_id = f.id
        WHERE t.class = ?
        ORDER BY 
            CASE t.day 
                WHEN 'Monday' THEN 1 
                WHEN 'Tuesday' THEN 2 
                WHEN 'Wednesday' THEN 3 
                WHEN 'Thursday' THEN 4 
                WHEN 'Friday' THEN 5 
                WHEN 'Saturday' THEN 6 
                ELSE 7 
            END,
            t.period
    """, (student_class,)).fetchall()

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    schedule = {day: {p: None for p in PERIODS} for day in days}
    for item in timetable_entries:
        if item['day'] in schedule and item['period'] in schedule[item['day']]:
            schedule[item['day']][item['period']] = item

    return render_template(
        'timetable.html',
        schedule=schedule,
        days=days,
        periods=PERIODS,
        period_timings=PERIOD_TIMINGS,
        break_timing=BREAK_TIMING,
        selected_class=student_class,
        view_only=True
    )


# ==============================================================================
# REPORT CARD GENERATION (PRINTABLE & DOWNLOADABLE)
# ==============================================================================

@app.route('/report-card/<int:student_id>')
@login_required
def report_card(student_id):
    """
    Renders an official, printable academic report card.
    Accessible by: Admin, Faculty, or the specific Student themselves.
    """
    # Authorization check
    if session.get('role') == 'student' and session.get('linked_id') != student_id:
        flash('You can only view your own report card.', 'danger')
        return redirect(url_for('student_dashboard'))

    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Retrieve all marks
    marks_records = db.execute("""
        SELECT m.*, c.name as course_name 
        FROM marks m
        JOIN courses c ON m.course_id = c.id
        WHERE m.student_id = ?
        ORDER BY c.name, m.exam_name
    """, (student_id,)).fetchall()

    processed_marks = []
    total_obtained = 0
    total_max = 0
    total_points = 0

    for m in marks_records:
        pct = round((m['marks_obtained'] / m['total_marks'] * 100), 1) if m['total_marks'] > 0 else 0
        grade, point, remark = calculate_grade(pct)
        total_obtained += m['marks_obtained']
        total_max += m['total_marks']
        total_points += point
        processed_marks.append({
            'course_name': m['course_name'],
            'exam_name': m['exam_name'],
            'marks_obtained': m['marks_obtained'],
            'total_marks': m['total_marks'],
            'percentage': pct,
            'grade': grade,
            'remark': remark
        })

    overall_pct = round((total_obtained / total_max * 100), 1) if total_max > 0 else 0
    gpa = round(total_points / len(processed_marks), 2) if processed_marks else 0.0
    overall_grade, _, final_remark = calculate_grade(overall_pct)

    # Attendance summary
    attendance_records = db.execute(
        "SELECT status FROM attendance WHERE student_id = ?", (student_id,)
    ).fetchall()
    total_classes = len(attendance_records)
    attended_classes = sum(1 for a in attendance_records if a['status'] in ['Present', 'Late'])
    attendance_pct = round((attended_classes / total_classes * 100), 1) if total_classes > 0 else 0

    return render_template(
        'report_card.html',
        student=student,
        marks=processed_marks,
        total_obtained=total_obtained,
        total_max=total_max,
        overall_pct=overall_pct,
        overall_grade=overall_grade,
        gpa=gpa,
        final_remark=final_remark,
        attendance_pct=attendance_pct,
        total_classes=total_classes,
        attended_classes=attended_classes,
        issue_date=datetime.now().strftime('%B %d, %Y')
    )


# ==============================================================================
# STUDENT LETTERS & FACULTY MAILBOX ROUTES (Leave, OD, Apology, Permission)
# ==============================================================================

@app.route('/student/letters', methods=['GET', 'POST'])
@role_required('student')
def student_letters():
    """Allows students to write formal letters (Leave, OD, Apology, Permission) to their faculty."""
    db = get_db()
    student_id = session.get('linked_id')

    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        faculty_id = request.form.get('faculty_id')
        letter_type = request.form.get('letter_type', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        from_date = request.form.get('from_date', '').strip()
        to_date = request.form.get('to_date', '').strip() or from_date

        if not faculty_id or not letter_type or not subject or not message:
            flash('Recipient faculty, letter type, subject, and message are required.', 'danger')
            return redirect(url_for('student_letters'))

        fac = db.execute("SELECT id, name FROM faculty WHERE id = ?", (faculty_id,)).fetchone()
        if not fac:
            flash('Selected faculty member not found.', 'danger')
            return redirect(url_for('student_letters'))

        db.execute("""
            INSERT INTO letters (student_id, faculty_id, letter_type, subject, message, from_date, to_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (student_id, faculty_id, letter_type, subject, message, from_date, to_date))
        db.commit()

        flash(f'Your {letter_type} has been sent to {fac["name"]}.', 'success')
        return redirect(url_for('student_letters'))

    # GET: List submitted letters
    letters = db.execute("""
        SELECT l.*, f.name AS faculty_name, f.subject AS faculty_dept
        FROM letters l
        JOIN faculty f ON l.faculty_id = f.id
        WHERE l.student_id = ?
        ORDER BY l.id DESC
    """, (student_id,)).fetchall()

    # List of faculty for recipient dropdown
    faculty_list = db.execute("""
        SELECT DISTINCT f.id, f.name, f.subject
        FROM faculty f
        ORDER BY f.name ASC
    """).fetchall()

    stats = {
        'total': len(letters),
        'pending': sum(1 for l in letters if l['status'] == 'Pending'),
        'approved': sum(1 for l in letters if l['status'] == 'Approved'),
        'declined': sum(1 for l in letters if l['status'] == 'Declined')
    }

    return render_template(
        'student_letters.html',
        letters=letters,
        faculty_list=faculty_list,
        student=student,
        stats=stats
    )


@app.route('/faculty/mailbox')
@role_required('faculty')
def faculty_mailbox():
    """Faculty Mailbox: View and review letters/requests sent by students."""
    db = get_db()
    faculty_id = session.get('linked_id')
    status_filter = request.args.get('status', '').strip()

    query = """
        SELECT l.*, s.name AS student_name, s.roll_no, s.class, s.contact, s.photo_path
        FROM letters l
        JOIN students s ON l.student_id = s.id
        WHERE l.faculty_id = ?
    """
    params = [faculty_id]

    if status_filter in ['Pending', 'Approved', 'Declined']:
        query += " AND l.status = ?"
        params.append(status_filter)

    query += " ORDER BY CASE l.status WHEN 'Pending' THEN 1 ELSE 2 END, l.id DESC"
    letters = db.execute(query, params).fetchall()

    counts_row = db.execute("""
        SELECT 
            COUNT(*) as total,
            COALESCE(SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END), 0) as pending,
            COALESCE(SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END), 0) as approved,
            COALESCE(SUM(CASE WHEN status = 'Declined' THEN 1 ELSE 0 END), 0) as declined
        FROM letters
        WHERE faculty_id = ?
    """, (faculty_id,)).fetchone()

    counts = {
        'total': counts_row['total'] if counts_row else 0,
        'pending': counts_row['pending'] if counts_row else 0,
        'approved': counts_row['approved'] if counts_row else 0,
        'declined': counts_row['declined'] if counts_row else 0
    }

    return render_template(
        'faculty_mailbox.html',
        letters=letters,
        counts=counts,
        selected_status=status_filter
    )


@app.route('/faculty/letters/respond/<int:letter_id>', methods=['POST'])
@role_required('faculty')
def respond_letter(letter_id):
    """Faculty approves or declines a student's letter request."""
    db = get_db()
    faculty_id = session.get('linked_id')
    action = request.form.get('action', '').strip()
    remark = request.form.get('faculty_remark', '').strip()

    if action not in ['Approved', 'Declined']:
        flash('Invalid response action.', 'danger')
        return redirect(url_for('faculty_mailbox'))

    letter = db.execute(
        "SELECT l.*, s.name as student_name FROM letters l JOIN students s ON l.student_id = s.id WHERE l.id = ? AND l.faculty_id = ?",
        (letter_id, faculty_id)
    ).fetchone()

    if not letter:
        flash('Letter not found or not addressed to your account.', 'danger')
        return redirect(url_for('faculty_mailbox'))

    db.execute("""
        UPDATE letters 
        SET status = ?, faculty_remark = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (action, remark, letter_id))
    db.commit()

    flash(f'{letter["letter_type"]} from {letter["student_name"]} has been {action}.', 'success')
    return redirect(url_for('faculty_mailbox'))


# ==============================================================================
# STATIC UPLOADS SERVING & ERROR HANDLERS
# ==============================================================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded student photos securely."""
    safe_name = secure_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.errorhandler(413)
def file_too_large(e):
    flash('File upload exceeded the 2MB size limit.', 'danger')
    return redirect(request.referrer or url_for('dashboard'))


# Application Entry Point
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
