# Eos Chatbot Backend (Django + DRF)

Python backend for the **NU Hospitals** appointment chatbot, built with
**Django** and **Django REST Framework**. It mirrors every method used by the
Angular `ChatService` in `chatbot-frontend`, returning the same
`{ code, message, response }` envelope, and moves the OpenAI / Groq API keys off
the browser by proxying those calls server-side.

## Requirements

- Python 3.12 (a conda env named `chatbot` was created for this)
- MySQL 8.x running locally

## Setup

```powershell
conda activate chatbot
cd chatbotb
pip install -r requirements.txt
copy .env.example .env   # then set DB_* creds + OPENAI_API_KEY / GROQ_API_KEY

# Create the database (once). Adjust user/password to match your .env:
python -c "import pymysql; c=pymysql.connect(host='127.0.0.1',user='root',password='YOUR_PW'); c.cursor().execute('CREATE DATABASE IF NOT EXISTS chatbot CHARACTER SET utf8mb4'); c.close()"

python manage.py migrate
python manage.py seed_tenant          # creates the default 'nu-hospitals' tenant
python manage.py createsuperuser      # to log into /admin and upload logos
```

## Multi-tenant chatbot design (DB-driven)

Every visual/behavioural setting for a tenant's chatbot lives in MySQL tables and
is edited from the Django admin (`/admin/`). Manage tenants under **Tenants**, and
their look & feel under **Chatbot designs** (colors, fonts, logo/avatar/launcher
image uploads, header text, welcome messages, menu options, contact info,
privacy URL, and the AI system prompt).

The frontend loads a tenant's theme from:

```
GET /api/tenants/<slug>/design
```

which returns the full design payload (with absolute logo URLs). A default
`nu-hospitals` tenant is created by `seed_tenant`.

## Run

```powershell
python manage.py runserver 8000
```

- API root: http://localhost:8000/
- Browsable API (DRF): http://localhost:8000/api/
- Health check: http://localhost:8000/api/health
- Django admin: http://localhost:8000/admin/ (run `python manage.py createsuperuser` first)

> If port 8000 reports "You don't have permission to access that port" on
> Windows, use another port, e.g. `python manage.py runserver 8001`, and update
> `CORS_ORIGINS` / the frontend base URL accordingly.

## Endpoints

All endpoints return `{ code, message, response }`.

### Tenant design

| Method | Path                            | Notes                                            |
| ------ | ------------------------------- | ------------------------------------------------ |
| GET    | `/api/tenants/<slug>/design`    | Full DB-driven chatbot theme + menu + welcome    |
| GET    | `/api/flows`                    | Main menu flows, internal steps, intents, app flows |

### Catalog

| Method | Path                              | Notes                                  |
| ------ | --------------------------------- | -------------------------------------- |
| GET    | `/api/countries`                  | Supported countries                    |
| GET    | `/api/branches`                   | Hospital branches                      |
| GET    | `/api/departments?branch_id=1`    | Departments available at a branch      |
| GET    | `/api/doctors?department_id=101`  | Doctors in a department                |
| GET    | `/api/surgeries?department_id=101`| Surgeries in a department              |
| GET    | `/api/time-slots?doctor_id=&date=`| Available slots (morning/afternoon/eve)|

### Appointments

| Method | Path                          | Body / Query                                         |
| ------ | ----------------------------- | ---------------------------------------------------- |
| POST   | `/api/appointments/submit`    | patient payload; `?url=` for the flow type           |
| GET    | `/api/appointments?phone=`    | Booked appointments for a mobile number              |
| POST   | `/api/appointments/cancel`    | `{ "appointmentId": 5001 }`                          |
| POST   | `/api/appointments/reschedule`| `{ "appointmentId", "date", "slot_id", "from_time", "to_time" }` |

Demo phone numbers with existing appointments: `9876543210`, `9123456789`.

### AI

| Method | Path                    | Notes                                            |
| ------ | ----------------------- | ------------------------------------------------ |
| POST   | `/api/ai/detect-intent` | `{ "text": "book appointment" }` → menu option   |
| POST   | `/api/ai/chat`          | `{ "message", "history": [...], "tenant": "<slug>" }` (tenant optional; uses its AI prompt) |
| POST   | `/api/ai/transcribe`    | multipart `file=` audio → transcript (Groq Whisper) |

## Wiring the frontend to this backend

The frontend `ChatService` currently uses in-memory demo data and calls OpenAI /
Groq directly. To use this backend instead, point its HTTP calls at
`http://localhost:8000` (e.g. add an `apiBaseUrl` to `environment.ts`) and
replace the local `respond(...)` helpers with `this.http.get/post` calls to the
paths in the tables above. The response shapes are identical, so the component
logic does not need to change.

## Project layout

```
chatbotb/
  manage.py
  requirements.txt
  .env.example            # config template (.env is git-ignored)
  core/                   # Django project
    settings.py           # env-based settings, CORS, DRF, AI provider config
    urls.py               # root routes + /api include + admin
    wsgi.py / asgi.py
  api/                    # Django app
    views.py              # all endpoints (return { code, message, response })
    urls.py               # /api/* routes
    data.py               # demo catalog + appointments (swap for models later)
    flows.py              # main menu + internal step + intent definitions
    intents.py            # re-exports detect_intent from flows.py
    ai.py                 # OpenAI chat + Groq Whisper helpers
```

## Notes

- Data is in-memory demo data (`api/data.py`); swap it for Django models +
  SQLite/Postgres when you're ready for persistence.
- SQLite (`db.sqlite3`) is used only for Django's built-in apps (admin, auth,
  sessions).
