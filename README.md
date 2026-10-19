# Public Service Request System (Mini eCitizen-style)

A web app where citizens report local problems (broken streetlights, water issues, uncollected garbage) and track their progress, while administrators manage the requests from a dashboard with simple analytics.

**Live demo:** _add your PythonAnywhere link here once deployed_
**Repository:** https://github.com/WillyNdirangu/public-service-request-system

**Author:** Willy Macharia

---

## Features

### Citizens
- Registration and login (passwords are stored hashed, never as plain text)
- Submit a request with category, location, description, priority (Low / Medium / Urgent) and an optional photo
- Track status visually: Pending, In Progress, Resolved
- Receive responses from the admin, shown as "unread" messages (bold, glowing) until opened, with an unread counter in the menu
- Edit or cancel a request while it is still Pending
- Forgot password with a secure one-time reset link

### Administrators
- Dashboard listing all requests, with urgent and unresolved ones shown first
- Update the status of any request and leave a note for the citizen
- Basic analytics: total, open and resolved cases, plus requests per category
- Filter requests by status
- Instant search by name, location, keyword, status or priority
- New (Pending) requests flicker so they are easy to spot; urgent ones are highlighted in red

### Interface
- Murang'a town background, splash screen, and subtle animations (hover effects, fade-ins, animated bars)
- Responsive layout that works on phones and computers

---

## Tech stack
- Python 3 and Flask
- SQLite (the database file is created automatically, no server needed)
- HTML, CSS and a little JavaScript

---

## How to run it locally

1. Install Python 3 from python.org (tick "Add Python to PATH").
2. Open a terminal in the project folder and install Flask:
```
   pip install -r requirements.txt
```
3. Start the app:
```
   python app.py
```
4. Open http://127.0.0.1:5000 in your browser.

The database (`service.db`) and the default admin account are created automatically the first time the app runs.

---

## Demo login

| Role    | Email               | Password   |
|---------|---------------------|------------|
| Admin   | admin@city.go.ke    | admin123   |
| Citizen | Register a new account from the Register page |

Admin and citizens share one login page. Access is role-based, and every admin route is protected on the server.

---

## Forgot password (demo mode)

The reset system uses a random token that expires after 30 minutes and works only once. Because no email server is configured, `DEMO_MODE = True` in `app.py` shows the reset link on the screen instead of emailing it. For production, set `DEMO_MODE = False` and send the link by email (SMTP).

---

## Project structure

```
app.py              routes, database logic and access control
requirements.txt    Python dependencies
templates/          HTML pages (base.html is the shared layout)
static/style.css    styling and animations
static/images/      background image
static/uploads/     photos uploaded by citizens
```

---

## Security notes
- Passwords are hashed with Werkzeug
- Admin pages are protected with a server-side role check
- Citizens can only edit, cancel or open their own requests
- Uploaded files are limited to image types and given unique names
- Reset links are random, expire after 30 minutes and are single-use

---

## Possible future improvements
- Real email delivery for password resets and status updates
- Status history timeline and CSV export
- Pagination for large numbers of requests
- Two-factor authentication for admins
- CSRF protection on all forms