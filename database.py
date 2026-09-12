"""
database.py - Database connection and schema management for SIMS.
Configured for production deployment with SQLite3.
Only initializes schema and seeds the default Admin account.
"""

import os
import sqlite3
from flask import g
from werkzeug.security import generate_password_hash

# Database path (stored in project root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'sims.db')


def get_db():
    """
    Returns an active SQLite database connection for the current application context.
    Configures foreign keys and Row factory so query columns can be accessed by name.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        # Enforce foreign key constraints
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e=None):
    """Closes the active database connection when the request context ends."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_standalone_connection():
    """Returns a standalone database connection (used for CLI scripts and setup)."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Creates all required tables and indexes if they do not already exist."""
    conn = get_standalone_connection()
    cursor = conn.cursor()

    # 1. users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'faculty', 'student')),
            linked_id INTEGER
        );
    """)

    # 2. students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT,
            class TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            contact TEXT,
            address TEXT,
            photo_path TEXT
        );
    """)

    # 3. faculty table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            contact TEXT
        );
    """)

    # 4. courses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class TEXT NOT NULL,
            faculty_id INTEGER,
            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL
        );
    """)

    # 5. attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late', 'Excused')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(student_id, course_id, date)
        );
    """)

    # 6. marks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            marks_obtained REAL NOT NULL,
            total_marks REAL NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(student_id, course_id, exam_name)
        );
    """)

    # 7. fees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            amount_due REAL NOT NULL,
            amount_paid REAL NOT NULL DEFAULT 0,
            due_date TEXT,
            status TEXT NOT NULL CHECK(status IN ('Paid', 'Partial', 'Unpaid')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        );
    """)

    # 8. timetable table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class TEXT NOT NULL,
            day TEXT NOT NULL,
            period INTEGER NOT NULL,
            subject TEXT NOT NULL,
            faculty_id INTEGER,
            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL
        );
    """)

    # 9. letters table (Leave, OD, Apology, Permission requests from students to faculty)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            faculty_id INTEGER NOT NULL,
            letter_type TEXT NOT NULL CHECK(letter_type IN ('Leave Request', 'On Duty (OD)', 'Apology Letter', 'Permission Request', 'Permission', 'General Letter', 'Other')),
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            from_date TEXT,
            to_date TEXT,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Declined')),
            faculty_remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE
        );
    """)

    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_class ON students(class);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_roll_no ON students(roll_no);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_class ON courses(class);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_marks_student ON marks(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fees_student ON fees(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timetable_class ON timetable(class);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letters_student ON letters(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letters_faculty ON letters(faculty_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letters_status ON letters(status);")

    conn.commit()
    conn.close()


def seed_db():
    """
    Deployment-ready seeder:
    Idempotently sets up initial administrator, faculty members, demo student,
    courses, and the complete departmental timetable if not already present.
    """
    conn = get_standalone_connection()
    cursor = conn.cursor()

    # 1. Admin account
    cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1;")
    if not cursor.fetchone():
        print("Seeding initial deployment admin account...")
        admin_hash = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            ('admin', admin_hash, 'admin')
        )

    # 2. Faculty members
    faculty_specs = [
        ('DR. T. Mahendran', 'Computer Applications', 'mahendran@clg.edu', 'prof_mahendran', 'faculty123'),
        ('DR. K. Devikala', 'Computer Applications', 'devikala@clg.edu', 'prof_devikala', 'faculty123'),
        ('DR. S. Madhanmohan', 'Computer Applications', 'madhanmohan@clg.edu', 'prof_madhanmohan', 'faculty123'),
        ('New Staff', 'Computer Applications', '', None, None),
        ('Dept. of Tamil', 'Tamil', '', None, None),
        ('Dept. of English', 'English', '', None, None),
        ('Dept. of Statistics', 'Statistics', '', None, None),
        ('Dept. of Commerce', 'Commerce', '', None, None),
        ('Dept. of Economics', 'Economics', '', None, None),
    ]

    fac_map = {}
    for name, subject, contact, username, password in faculty_specs:
        row = cursor.execute("SELECT id FROM faculty WHERE name = ?", (name,)).fetchone()
        if not row:
            cursor.execute("INSERT INTO faculty (name, subject, contact) VALUES (?, ?, ?)", (name, subject, contact))
            fac_id = cursor.lastrowid
        else:
            fac_id = row['id']
        fac_map[name] = fac_id

        if username and password:
            u_row = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not u_row:
                p_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, linked_id) VALUES (?, ?, 'faculty', ?)",
                    (username, p_hash, fac_id)
                )

    # 3. Student account (Jeevitha - III BCA)
    st_row = cursor.execute("SELECT id FROM students WHERE roll_no = 'bca046' LIMIT 1").fetchone()
    if not st_row:
        cursor.execute("""
            INSERT INTO students (name, dob, class, roll_no, contact, address, photo_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('jeevitha', '2006-09-06', 'III BCA', 'bca046', '8270104829', 'villupuram', 'student_bca046_b0b6b853.jpg'))
        student_id = cursor.lastrowid
        s_hash = generate_password_hash('student123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, linked_id) VALUES (?, ?, 'student', ?)",
            ('bca046', s_hash, student_id)
        )

    # 4. Courses
    courses_spec = [
        ('Operating system', 'III BCA', fac_map.get('DR. K. Devikala')),
        ('Software engineering', 'III BCA', fac_map.get('DR. S. Madhanmohan')),
        ('RDBMS', 'III BCA', fac_map.get('DR. T. Mahendran')),
    ]
    for c_name, c_class, c_fac in courses_spec:
        c_row = cursor.execute("SELECT id FROM courses WHERE name = ? AND class = ?", (c_name, c_class)).fetchone()
        if not c_row:
            cursor.execute("INSERT INTO courses (name, class, faculty_id) VALUES (?, ?, ?)", (c_name, c_class, c_fac))

    # 5. Timetable slots
    tt_count = cursor.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
    if tt_count == 0:
        days_map = {'I': 'Monday', 'II': 'Tuesday', 'III': 'Wednesday', 'IV': 'Thursday', 'V': 'Friday', 'VI': 'Saturday'}
        
        iii_bca_data = [
            ('I', 1, 'PROJECT [SM]', 'DR. S. Madhanmohan'), ('I', 2, 'OS', 'DR. K. Devikala'), ('I', 3, 'ASP', 'New Staff'), ('I', 4, 'ASP', 'New Staff'), ('I', 5, 'S/W', 'DR. S. Madhanmohan'),
            ('II', 1, 'PROJECT [NS]', 'New Staff'), ('II', 2, 'DBMS', 'DR. T. Mahendran'), ('II', 3, 'ASP LAB', 'New Staff'), ('II', 4, 'ASP LAB', 'New Staff'), ('II', 5, 'ASP LAB', 'New Staff'),
            ('III', 1, 'S/W', 'DR. S. Madhanmohan'), ('III', 2, 'OS', 'DR. K. Devikala'), ('III', 3, 'DBMS', 'DR. T. Mahendran'), ('III', 4, 'ASP', 'New Staff'), ('III', 5, 'N/M', 'DR. T. Mahendran'),
            ('IV', 1, 'PROJECT [SM]', 'DR. S. Madhanmohan'), ('IV', 2, 'DBMS', 'DR. T. Mahendran'), ('IV', 3, 'OS', 'DR. K. Devikala'), ('IV', 4, 'S/W', 'DR. S. Madhanmohan'), ('IV', 5, 'ASP', 'New Staff'),
            ('V', 1, 'OS', 'DR. K. Devikala'), ('V', 2, 'S/W', 'DR. S. Madhanmohan'), ('V', 3, 'VE', 'DR. S. Madhanmohan'), ('V', 4, 'ASP', 'New Staff'), ('V', 5, 'DBMS', 'DR. T. Mahendran'),
            ('VI', 1, 'OS', 'DR. K. Devikala'), ('VI', 2, 'VE', 'DR. S. Madhanmohan'), ('VI', 3, 'ASP LAB', 'New Staff'), ('VI', 4, 'ASP LAB', 'New Staff'), ('VI', 5, 'N/M', 'DR. T. Mahendran'),
        ]

        ii_bca_data = [
            ('I', 1, 'TAM [FREE]', 'Dept. of Tamil'), ('I', 2, 'TAMIL', 'Dept. of Tamil'), ('I', 3, 'ENGLISH', 'Dept. of English'), ('I', 4, 'DS', 'DR. K. Devikala'), ('I', 5, 'NM', 'DR. K. Devikala'),
            ('II', 1, 'DS', 'DR. K. Devikala'), ('II', 2, 'DS - LAB', 'DR. K. Devikala'), ('II', 3, 'DS - LAB', 'DR. K. Devikala'), ('II', 4, 'FA', 'Dept. of Commerce'), ('II', 5, 'ENGLISH', 'Dept. of English'),
            ('III', 1, 'TAMIL', 'Dept. of Tamil'), ('III', 2, 'FA', 'Dept. of Commerce'), ('III', 3, 'DS', 'DR. K. Devikala'), ('III', 4, 'EVS', 'DR. S. Madhanmohan'), ('III', 5, 'ENG [FREE]', 'Dept. of English'),
            ('IV', 1, 'ENGLISH', 'Dept. of English'), ('IV', 2, 'DS', 'DR. K. Devikala'), ('IV', 3, 'FA', 'Dept. of Commerce'), ('IV', 4, 'TAMIL', 'Dept. of Tamil'), ('IV', 5, 'NM', 'DR. K. Devikala'),
            ('V', 1, 'TAM [FREE]', 'Dept. of Tamil'), ('V', 2, 'DS - LAB', 'DR. K. Devikala'), ('V', 3, 'DS - LAB', 'DR. K. Devikala'), ('V', 4, 'FA', 'Dept. of Commerce'), ('V', 5, 'ENGLISH', 'Dept. of English'),
            ('VI', 1, 'TAM [FREE]', 'Dept. of Tamil'), ('VI', 2, 'DS', 'DR. K. Devikala'), ('VI', 3, 'ERP', 'New Staff'), ('VI', 4, 'ERP', 'New Staff'), ('VI', 5, 'ENG [FREE]', 'Dept. of English'),
        ]

        i_bca_data = [
            ('I', 1, 'TAM', 'Dept. of Tamil'), ('I', 2, 'DEMO', 'Dept. of Economics'), ('I', 3, 'PYTHON', 'DR. T. Mahendran'), ('I', 4, 'PYTHON LAB', 'DR. T. Mahendran'), ('I', 5, 'PYTHON LAB', 'DR. T. Mahendran'),
            ('II', 1, 'ENG [FREE]', 'Dept. of English'), ('II', 2, 'ENGLISH', 'Dept. of English'), ('II', 3, 'PYTHON', 'DR. T. Mahendran'), ('II', 4, 'DEMO', 'Dept. of Economics'), ('II', 5, 'TAM [FREE]', 'Dept. of Tamil'),
            ('III', 1, 'TAM [FREE]', 'Dept. of Tamil'), ('III', 2, 'PYTHON', 'DR. T. Mahendran'), ('III', 3, 'TAMIL', 'Dept. of Tamil'), ('III', 4, 'STAT', 'Dept. of Statistics'), ('III', 5, 'ENGLISH', 'Dept. of English'),
            ('IV', 1, 'TAM [FREE]', 'Dept. of Tamil'), ('IV', 2, 'C', 'New Staff'), ('IV', 3, 'C', 'New Staff'), ('IV', 4, 'PYTHON', 'DR. T. Mahendran'), ('IV', 5, 'STAT', 'Dept. of Statistics'),
            ('V', 1, 'ENG [FREE]', 'Dept. of English'), ('V', 2, 'PYTHON', 'DR. T. Mahendran'), ('V', 3, 'TAMIL', 'Dept. of Tamil'), ('V', 4, 'STAT', 'Dept. of Statistics'), ('V', 5, 'ENGLISH', 'Dept. of English'),
            ('VI', 1, 'PYTHON LAB', 'DR. T. Mahendran'), ('VI', 2, 'PYTHON LAB', 'DR. T. Mahendran'), ('VI', 3, 'PYTHON LAB', 'DR. T. Mahendran'), ('VI', 4, 'ENGLISH', 'Dept. of English'), ('VI', 5, 'STAT', 'Dept. of Statistics'),
        ]

        for cls, dset in [('III BCA', iii_bca_data), ('Bca-Year3', iii_bca_data),
                          ('II BCA', ii_bca_data), ('Bca-Year2', ii_bca_data),
                          ('I BCA', i_bca_data), ('Bca-Year1', i_bca_data)]:
            for d_order, period, subj, f_name in dset:
                cursor.execute(
                    "INSERT INTO timetable (class, day, period, subject, faculty_id) VALUES (?, ?, ?, ?, ?)",
                    (cls, days_map[d_order], period, subj, fac_map.get(f_name))
                )

    conn.commit()
    conn.close()


def clear_sample_data():
    """
    Removes all sample records and resets the database for clean production deployment.
    Retains only the default administrator account.
    """
    conn = get_standalone_connection()
    cursor = conn.cursor()

    # Clear all operational data
    cursor.execute("DELETE FROM attendance;")
    cursor.execute("DELETE FROM marks;")
    cursor.execute("DELETE FROM fees;")
    cursor.execute("DELETE FROM timetable;")
    cursor.execute("DELETE FROM courses;")
    cursor.execute("DELETE FROM letters;")
    cursor.execute("DELETE FROM students;")
    cursor.execute("DELETE FROM faculty;")
    cursor.execute("DELETE FROM users WHERE role != 'admin';")

    # Reset SQLite autoincrement counters where applicable
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('attendance', 'marks', 'fees', 'timetable', 'courses', 'letters', 'students', 'faculty');")

    # Ensure default admin exists
    cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1;")
    if not cursor.fetchone():
        admin_hash = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            ('admin', admin_hash, 'admin')
        )

    conn.commit()
    conn.close()
    print("All sample data deleted successfully. Clean deployment state active.")


if __name__ == '__main__':
    init_db()
    clear_sample_data()
    print("Database verified and clean for deployment.")
