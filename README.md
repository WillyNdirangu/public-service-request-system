# Public Service Request System (Mini eCitizen-style)

Citizens report local problems (streetlights, water, garbage...) and track progress.
Admins manage requests and see simple analytics.

## Features
- Citizen registration & login (passwords are hashed)
- Submit request: category, location, description, optional image
- Status tracking: Pending → In Progress → Resolved (visual tracker)
- Admin dashboard: all requests, update status
- Analytics: total / open / resolved + requests per category
- **Bonus:** admin notes to citizens, filter by status, image upload validation, mobile-friendly layout

## Tech
Python 3, Flask, SQLite (no database server needed), plain HTML/CSS.

## Setup
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 (the database `service.db` is created automatically).

## Demo login
- Admin: `admin@city.go.ke` / `admin123`
- Citizen: register a new account from the Register page.

## Project structure
```
app.py            all routes + database logic
templates/        HTML pages (base.html is the shared layout)
static/style.css  styling
static/uploads/   uploaded photos
```

## Possible improvements
Email notifications, pagination, map location picker, password reset, CSRF protection.
