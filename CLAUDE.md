# ARPSC Manager

Management platform for St. Clair County ARPSC (Amateur Radio Public Service Corps). Handles weather siren testing, member profiles, event/attendance tracking, ICS-309 comm logs, training records, task book progress, and monthly state reporting.

## Stack
- Python Flask + SQLite + Bootstrap 5
- Gunicorn (2 workers, port 8100) behind Nginx with SSL
- Google Workspace OAuth for admin login
- Email magic link auth for member login
- Gmail API for email notifications (sends as noreply@sccarpsc.org)
- ReportLab for ICS-309 PDF generation
- Deployed at sirens.sccarpsc.org on Ubuntu (DigitalOcean 512MB droplet)

## Project Structure
- `app/` — Flask application (factory pattern via `create_app()`)
  - `public/` — Siren dashboard, siren detail, volunteer signup (no auth)
  - `admin/` — Siren/test/assignment/event/member/commlog/taskbook management (Google OAuth required)
  - `auth/` — Google Workspace OAuth login (admin)
  - `members/` — Member self-service: magic link login, profile, equipment, training, task books, activity
  - `models.py` — Siren, SirenMaintenanceLog, Test, Assignment, AdminUser, TestSchedule, Member, EquipmentType, MemberEquipmentItem, TrainingType, MemberTraining, TaskBookLevel, TaskBookTask, MemberTaskBookProgress, Event, EventAttendance, CommLog, CommLogEntry
  - `gmail.py` — Gmail API send (OAuth token in `instance/gmail_token.json`)
  - `utils.py` — Status computation, photo processing, email notifications, inactivity detection
  - `reports.py` — Monthly state report generation with ARES category mapping
  - `pdf.py` — ICS-309 Communications Log PDF generation via ReportLab
- `media/photos/` — Test photos on disk (not in git)
- `instance/` — SQLite DB and Gmail token (not in git)
- `deploy/` — systemd service and nginx config
- `scripts/` — Auth, backup, import utilities

## Key Commands
```bash
# Local dev
flask run

# Database migrations
flask db migrate -m "description"
flask db upgrade

# Gmail auth (run locally, copy token to server)
python scripts/gmail_auth.py

# Backup (runs via cron on server)
/opt/sirentracker/scripts/backup.sh
```

## Server Deployment
```bash
cd /opt/sirentracker && git pull
.venv/bin/pip install -r requirements.txt  # if deps changed
sudo -u www-data .venv/bin/flask db upgrade  # if migrations
sudo systemctl restart sirentracker
```

## Authentication
- **Admin**: Google Workspace OAuth (domain-restricted). AdminUser model.
- **Member**: Email magic link (6-digit code + clickable link via Gmail API). Member model.
- Flask-Login `user_loader` handles both via `get_id()` prefix: `admin:N` or `member:N`.

## Siren Statuses (priority order)
1. **Failed** — tested this year and failed
2. **Flagged** — manually marked for recheck (needs_retest); overrides Passed
3. **Passed** — tested this year and passed
4. **Overdue** — no test in over 12 months or never tested
5. **Assigned** — volunteer claimed for upcoming test
6. **Untested** — not yet tested this year (but tested within 12 months)

## Event Types → State Report Mapping
| Event Type | State Category |
|---|---|
| Meeting, Net, Info Net, Simplex Net, Training, Exercise | Drills |
| Public Service Event, Siren Test | Public Service Events |
| Public Safety Incident, Deployment | Public Safety Incidents |
| SKYWARN Activation | SKYWARN Activations |
| General/Misc | Not reported |

## Notes
- Static CSS has cache-busting `?v=N` in base.html — bump when changing styles
- Photos auto-resized to max 1200px, thumbnails at 200px, JPEG format
- `instance/` and `media/photos/` must be writable by www-data on server
- reCAPTCHA on volunteer signup (optional, needs keys in .env)
- Backups run weekly via cron: SQLite + CSV exports + photos to Google Drive
- Dollar value per volunteer hour: $34.79 (configurable in config.py)
- SKYWARN training expires every 2 years (auto-computed)
- Task books: configurable levels with tasks, require two officer sign-offs
