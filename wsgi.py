"""
wsgi.py - Production WSGI Entrypoint for SIMS
Used by Gunicorn, uWSGI, and container platforms (Render, Railway, Heroku, Docker).
"""

import os
from app import app, init_db, seed_db

# Ensure database tables and initial deployment seeds exist on boot
try:
    with app.app_context():
        init_db()
        seed_db()
except Exception as e:
    print(f"[WSGI Init] Database setup note: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
