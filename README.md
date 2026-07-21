# ChariSmart

ChariSmart is a Flask and SQLite prototype for coordinating surplus-food donations. It connects donors such as restaurants, wedding halls and households with NGOs/orphanages and volunteer riders.

## Main features

- Role-based accounts for admin, donor, recipient and volunteer users
- Surplus-food donation and food-request submission
- Admin verification, approval and rejection workflows
- Automatic same-area matching with a match score
- Volunteer assignment, pickup and delivery tracking
- In-app, email and optional SMS notifications
- Delivery confirmation, rating and notes

## Repository structure

```text
ChariSmart/
|-- README.md
|-- report/
|   `-- Final_Report.pdf
|-- src/
|   `-- complete-source-code/
|-- database/
|   |-- schema.sql
|   `-- sample-data.sql
|-- diagrams/
|   |-- use-case-diagram.*
|   |-- class-diagram.*
|   |-- sequence-diagram.*
|   |-- activity-diagram.*
|   |-- ER-diagram.*
|   `-- DFD/
|-- prototype/
|   `-- prototype-source-files/
|-- screenshots/
`-- tests/
```

Diagram source files are supplied in Mermaid (`.mmd`) format, with rendered PNG/SVG files for convenient viewing.

## Technology

- Python 3.10+
- Flask
- Flask-SQLAlchemy
- SQLite
- HTML and CSS

## Run the complete source code

```bash
cd src/complete-source-code
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Install dependencies and start the application:

```bash
pip install -r requirements.txt

# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env

python app.py
```

Open `http://127.0.0.1:5000`.

The application creates its SQLite database automatically on first run.

## Default admin login

```text
Email: admin@example.com
Password: admin123
```

These credentials are only for local demonstration. Change them before any real deployment.

## Optional SQL setup

If the SQLite command-line tool is installed, the included SQL files can create a separate demonstration database from the repository root:

```bash
sqlite3 charismart_demo.db < database/schema.sql
sqlite3 charismart_demo.db < database/sample-data.sql
```

Demo accounts created by `sample-data.sql`:

| Role | Email | Password |
|---|---|---|
| Admin | admin@example.com | admin123 |
| Donor | demo.donor@example.com | donor123 |
| Recipient | demo.ngo@example.com | ngo123 |
| Volunteer | demo.rider@example.com | rider123 |

## Run the automated test

From the repository root:

```bash
python tests/test_notification_flow.py
```

The test uses an isolated temporary SQLite database and replaces real email/SMS delivery with safe local fakes.

## Notification configuration

Copy `.env.example` to `.env` inside the source-code folder. Add SMTP or Twilio credentials only to the local `.env` file. Never commit real credentials to GitHub.

If email credentials are not configured, notification messages are printed in the terminal so the workflow can still be demonstrated during the lab viva.

