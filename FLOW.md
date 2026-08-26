# Chatbot Flow Definitions

Single source of truth: **`api/flows.py`**

Fetch the full catalog at runtime:

```
GET /api/flows
```

## Main menu flows (tenant DB: `MenuOption.option_id`)

| ID | Key | Label | Category |
|----|-----|-------|----------|
| 1 | book_appointment | Appointment with doctor | booking |
| 2 | find_doctor | Find doctor | booking |
| 3 | video_consultation | Book video consultation | booking |
| 4 | surgery_enquiry | Surgery enquiry | enquiry |
| 5 | international_patient | International patient query | enquiry |
| 6 | connect_with_us | Connect with us | info |
| 7 | customer_care | Connect with our Customercare | info |
| 20 | cancel_appointment | Cancel appointment | manage |
| 21 | reschedule_appointment | Reschedule appointment | manage |

New tenants get these via `seed_default_design()` → `default_menu_options()`.

## Internal steps (frontend only, `ChatbotComponent.chooseOptions`)

| ID | Key | Purpose |
|----|-----|---------|
| 8 | self | Booking for self |
| 9 | other | Booking for family/friend |
| 10–11 | privacy_agree / decline | Privacy policy |
| 12–13 | gender_male / female | Patient gender |
| 14–19 | confirm / additional info | Booking confirmation |
| 22–26 | cancel/reschedule confirm | Manage appointment |

## Application flows

### Auth
1. `POST /api/auth/signup` → User + Tenant + Design + TenantOwner + Token
2. `POST /api/auth/login` → Token (email or username)
3. `GET /api/auth/me` / `POST /api/auth/logout`

### Tenant design
1. `GET /api/tenants/{slug}/design` — public widget load
2. `PATCH /api/tenants/{slug}/design` — owner save
3. `POST /api/tenants/{slug}/design/upload` — logo/avatar/launcher

### Embed
1. Host loads `eos-embed.js` → native launcher (no Angular)
2. Click → iframe `/widget?embed=1&tenant={slug}&autoOpen=1`
3. `postMessage` `eos-open` / `eos-close`

### Chat conversation
1. **Menu click** → `option_id` → structured steps in Angular
2. **Free text** → `detect_intent()` in `flows.py` or `POST /api/ai/detect-intent`
3. **Voice** → `POST /api/ai/transcribe` → intent or `POST /api/ai/chat`
4. **Catalog** → `GET /api/branches`, `/departments`, `/doctors`, `/time-slots`
5. **Appointments** → `GET/POST /api/appointments/*`

## Keep in sync

When adding a menu option, update:
- `api/flows.py` → `MAIN_MENU_FLOWS` + `INTENTS`
- `chatbot-frontend/src/app/flows/chatbot-flows.ts` (mirror)
- `ChatbotComponent.chooseOptions()` switch case
