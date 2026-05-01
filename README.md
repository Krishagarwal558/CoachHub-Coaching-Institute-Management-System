# CoachHub Coaching Institute Management System

A complete Flask + SQLite SaaS-style management system for small coaching institutes. It includes role-based dashboards for Admin, Teacher, and Student users, secure password hashing, sessions, attendance, marks, content, announcements, doubts, feedback, fee tracking, and Chart.js analytics.

## Run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## First Admin

The SQLite database is created automatically as `coaching.db` on first request. A fresh install starts empty, with no sample users or records. Open `/setup-admin` to create the first admin account, then add teachers and students from the admin dashboard.

## Features

- Secure login and registration with Werkzeug password hashing
- Admin-controlled user creation and profile management
- Role-based dashboards for Admin, Teacher, and Student
- Fee tracking, student search, and full user visibility for admins
- Daily attendance marking and student-wise attendance percentages
- Test marks, performance summaries, and class analytics
- Notes, assignments, file uploads, and lecture links
- Assignment submission workflow for students
- Announcements for all users or role-specific audiences
- Doubt solving Q&A and student feedback review
- Responsive SaaS dashboard UI with sidebar navigation and Chart.js graphs
