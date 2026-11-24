# SpendWise — Multi-Bank Expense Tracker & Financial Analytics Web Application

A fully functional, responsive financial management web application built with **Django**, **SQLite database**, **HTML5/CSS3**, **JavaScript (ES6+)**, **Bootstrap 5**, and **Chart.js 4.4**.

---

## 🌟 Overview & Architecture

SpendWise is converted from the frontend prototype into a production-ready, full-stack Django application with full relational database persistence via SQLite (`db.sqlite3`).

### Tech Stack
- **Backend**: Python 3, Django (Models, ORM, Admin, CSRF Protection, REST Endpoints, Management Commands)
- **Database**: SQLite 3 (`db.sqlite3`)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js 4.4
- **Security**: Django User Authentication, Session-based security, CSRF Token validation, atomic database transactions

---

## 🚀 Quick Start Guide

### 1. Requirements
Ensure Python 3.10+ and pip are installed.
```bash
pip install -r requirements.txt
```

### 2. Apply Database Migrations (Pre-configured)
```bash
python manage.py migrate
```

### 3. Seed Demo Data & Categories (Optional)
```bash
python manage.py seed_demo
```
*This seeds preset expense categories, 3 realistic bank accounts (Checking, High Yield Savings, Credit Card), and multi-month expense records spanning the entire year.*

### 4. Start the Django Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your web browser.

---

## 🔐 Credentials & Access

### 1. One-Click Demo User
- **Email**: `demo@spendwise.com`
- **Password**: `password123`
- *(Alternatively, click the **"One-Click Demo Login"** button on the sign-in page for instant one-click access)*

### 2. Django Admin Dashboard (Superuser)
- **URL**: `http://127.0.0.1:8000/admin/`
- **Username**: `admin`
- **Password**: `admin123`
- *Access the Django Admin to view and edit raw database tables for Users, BankAccounts, Expenses, and Categories.*

---

## 💼 Core Features

### 1. User Authentication & Profile
- **Account Registration**: Register with Full Name, Email, Password (min 6 chars), and preferred Currency (`$`, `€`, `£`, `₹`, `¥`, `C$`, `A$`, `AED`).
- **Session Authentication**: Secure Django session login and logout.
- **Theme Preference**: Toggle between Dark Mode and Light Mode with persistence in `UserProfile`.
- **Permanent Account Deletion**: Self-service user profile removal with cascading cleanup of bank accounts and expense history.

### 2. Multi-Bank Account Management
- **Add Bank Accounts**: Add checking, savings, credit cards, investment, or digital wallets with custom mask numbers, initial balances, and card themes (`Royal Blue`, `Cool Indigo`, `Ocean Teal`, `Cool Slate`, `Pacific Cyan`).
- **Aggregated vs. Individual Balances**:
  - **Combined Liquid Balance**: Aggregated total across all configured accounts.
  - **Individual Cards**: Card widgets displaying balance, mask, account type, and total spent.
- **Top-Up / Add Funds**: Deposit funds into any bank account with instant balance updates in SQLite.
- **Edit & Delete Bank Accounts**: Update details or remove accounts with confirmation and cascading expense management.

### 3. Expense Logging & Automatic Balance Adjustments
- **Detailed Entry**:
  - Amount
  - Deducted Bank Account
  - Merchant / Place
  - Category (12 preset categories with custom icons and badge colors)
  - Purpose & Description
  - Date & Time
  - Payment Method (Debit Card, Credit Card, UPI / Online, NetBanking, Auto-Debit, Cash)
  - Notes & References
- **Automatic Balance Deductions & Refunds**:
  - Adding an expense automatically deducts the funds from the selected bank account in SQLite.
  - Editing an expense calculates the delta and updates both accounts if swapped.
  - Deleting an expense automatically refunds the full amount back to the bank account balance.
- **Search & Filters**: Real-time filtering by merchant search query, bank account, category, and date range (`from` - `to`).
- **CSV Export**: Direct download of verified expense history formatted as a CSV spreadsheet.

### 4. Advanced Expense Analytics & Reporting
- **Multi-Period Filtering**:
  - **Monthly**: Spending breakdown, daily timeline, month-over-month (MoM) percentage comparisons.
  - **Quarterly**: Q1 (Jan–Mar), Q2 (Apr–Jun), Q3 (Jul–Sep), Q4 (Oct–Dec) comparisons.
  - **Half-Yearly**: H1 (Jan–Jun) vs. H2 (Jul–Dec) comparative breakdown.
  - **Yearly**: Full 12-month annual expenditures with peak spending detection.
- **Top Spending Category Spotlight**: Identifies the #1 highest spending category in the active period with total spend, % share, and average transaction size.
- **Category Spending Leaderboard**: Ranked table with visual progress bars from highest to lowest spending category.
- **Interactive Visual Charts (Chart.js)**:
  - Spending Trend Chart (Bar Chart)
  - Category Distribution Chart (Doughnut Chart)
  - Cross-Account Comparison (Available Balance vs. Total Logged Expenses)
- **PDF Financial Reports Export**:
  - **Monthly Report (PDF)**: Detailed statement for any chosen month with daily/weekly insights, category rankings, and itemized receipts.
  - **Quarterly Report (PDF)**: 3-month financial breakdown (Q1, Q2, Q3, Q4) with comparisons and multi-bank statistics.
  - **Half-Yearly Report (PDF)**: Comprehensive 6-month analysis (H1 / H2) comparing performance against the previous semester.
  - **Yearly Report (PDF)**: Publication-quality annual statement including executive KPIs, cross-account balances, ranked leaderboard, and all expense logs.
  - **Custom Report Dialog**: Allows selecting timeframe, year, target period, and filtering by single bank account or consolidated multi-bank accounts.
  - **Direct Endpoints**: `/api/reports/pdf/`, `/api/reports/monthly/pdf/`, `/api/reports/quarterly/pdf/`, `/api/reports/halfyearly/pdf/`, `/api/reports/yearly/pdf/`.
- **SpendBot — AI Financial Assistant Chatbot**:
  - Floating chatbot launcher and interactive slide-up conversation window.
  - **Strict User Privacy**: Answers generated exclusively from the authenticated user's SQLite data (never other users' data).
  - **Natural Language Financial Intelligence**:
    - `total expense`: All-time and current year total spending, transaction count, average per transaction.
    - `total monthly expense`: Current month total, daily average, comparison vs previous month, top category.
    - `qtr expense`: Quarter spend (Q1, Q2, Q3, Q4), monthly sub-breakdown, top category.
    - `yearly expense`: Full annual expenditure, monthly average, peak and lowest months.
    - `<month> month expense` (e.g. `jan month expense`): Targeted month spending, transactions, top merchant, top category.
    - `category wise expense`: Complete ranked leaderboard across all categories with sums and percentages.
    - `max month expense`: Identifies the highest spending month in the year, peak totals, and daily averages.
    - `max category expense`: Highlights the user's #1 largest expense category, budget percentage, and runner-up.
    - Also supports bank balances, recent transaction logs, highest single purchases, and interactive quick-prompt suggestion chips.

---

## 🗄️ Database Schema (SQLite)

| Model | Table Name | Key Fields |
|---|---|---|
| **User** | `auth_user` | `id`, `username`, `email`, `password`, `first_name`, `last_name` |
| **UserProfile** | `tracker_userprofile` | `user_id` (OneToOne), `currency`, `theme`, `created_at` |
| **BankAccount** | `tracker_bankaccount` | `user_id` (ForeignKey), `bank_name`, `account_name`, `account_type`, `account_number`, `opening_balance`, `current_balance`, `currency`, `color_theme`, `created_at` |
| **Expense** | `tracker_expense` | `user_id` (ForeignKey), `account_id` (ForeignKey), `amount`, `place`, `purpose`, `category`, `date`, `time`, `payment_mode`, `notes`, `created_at` |
| **Category** | `tracker_category` | `code`, `name`, `icon`, `color` |

---

## 🧪 Testing

Run Django's built-in automated test suite:
```bash
python manage.py test
```
All unit tests verify:
1. User registration, authentication, and session handling
2. Bank account creation, updates, and balance top-ups
3. Expense logging, automatic balance deductions, and balance refunds on deletion
4. CSV export generation and streaming
5. Analytics computation and data aggregation
6. PDF reports generation and streaming (Monthly, Quarterly, Half-Yearly, Yearly)
7. SpendBot Chatbot API (Total expense, Monthly, Quarterly, Yearly, Month-specific, Category-wise, Max month, Max category, and multi-user data isolation)
