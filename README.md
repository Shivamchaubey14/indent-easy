# Indent Easy

A Django-based ERP / inventory & procurement portal built for **Shwetdhara Milk Producer Company Limited**. It manages the full material flow across MCC/BMC locations — indents, goods receipts, stock transfers, sales, reconciliation and a monthly-cycle **Sale & Stock Report** — with WhatsApp notifications to MPPs.

> ⚠️ This repository contains **application code only**. Secrets live in a gitignored `.env`, and real database dumps / media are excluded. Never commit credentials or member data.

---

## Features

- **Indents** — create purchase requisitions, HOD approval workflow, purchase-department processing.
- **GRN (Goods Receipt Note)** — receive goods against indents/POs, auto-updating inventory with full history.
- **STN (Stock Transfer Note)** — transfer stock between MCC/BMC locations (transfer-out / transfer-in).
- **POD** — proof-of-delivery upload and tracking.
- **Advance Sale** — dispatch stock to MPPs ahead of SAP billing, with unique codes and WhatsApp confirmations.
- **Reconciliation** — match advance sales against the SAP sale export.
- **Sale & Stock Report** — per monthly-cycle, per MCC/BMC × product statement:
  - `Closing = Opening + Received (NDS/Other Co.) + Received (MCC/BMC) + Stock Transfer − MPP Sale − Damage − Expire`
  - Opening carries forward from the previous cycle's closing (cycle chaining).
  - Admin uploads the SAP sale export; location users fill Damage/Expire (per-location lock/unlock).
  - Full per-location product grid, a company-wide **SMPCL Summary** sheet, Excel download, and an admin "upload corrected report" flow.
- **WhatsApp Cloud API** integration — templated reminders and delivery tracking, with an analytics dashboard.
- **Role-based dashboards** — Admin, HOD, Purchase, Finance, Logistics, and Location (MPP/BMC) users.
- **Idempotent POST** handling to prevent duplicate records on retries.

## Tech stack

- **Backend:** Django 5.1 (Python 3.13)
- **Database:** MySQL
- **Async / scheduling:** Celery + Redis (celery beat)
- **Messaging:** WhatsApp Cloud API (Meta Graph API)
- **Excel:** openpyxl
- **Config:** python-decouple (`.env`)
- **Env / deps:** Pipenv

## Getting started

### 1. Prerequisites
- Python 3.13
- MySQL 8+
- Redis (for Celery)
- Pipenv (`pip install pipenv`)

### 2. Clone & install
```bash
git clone https://github.com/Shivamchaubey14/indent-easy.git
cd indent-easy
pipenv install
```

### 3. Configure environment
```bash
cp .env.example .env
# then edit .env and fill in your database, WhatsApp, email and secret values
```
See `.env.example` for the full list of required variables.

### 4. Database
Create the MySQL database referenced by `DATABASE_NAME`, then:
```bash
pipenv run python manage.py migrate
pipenv run python manage.py createsuperuser
```
(`create_all_tables.sql` contains the raw schema for reference.)

### 5. Run
```bash
pipenv run python manage.py runserver
```
Optional background workers:
```bash
pipenv run celery -A shwetDhara_project worker -l info
pipenv run celery -A shwetDhara_project beat -l info
```

## Project structure

```
shwetDhara_project/         # Django project settings, celery, wsgi/asgi
main_app/                   # core app: models, views, urls, tasks
  ├─ stock_report.py        # Sale & Stock Report engine (statement, ingest, workbook)
  ├─ models.py              # all domain models
  ├─ views.py               # views (indents, GRN, STN, reports, WhatsApp, ...)
  └─ migrations/
templates/                  # HTML templates (per role / feature)
static/                     # static assets
create_all_tables.sql       # reference DB schema
```

## Security notes

- `.env`, `media/`, database dumps (`*_backup.sql`, `database_backup/`) and generated spreadsheets are **gitignored**.
- All credentials are read from `.env` via `python-decouple` — no secrets in source.
- If any credential is ever exposed, **rotate it** (WhatsApp token, DB password, email app password, Django `SECRET_KEY`).
