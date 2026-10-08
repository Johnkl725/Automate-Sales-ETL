# 💳 Gastos ETL: Automated Data Engineering Pipeline

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![SQL Server](https://img.shields.io/badge/SQL_Server-Latest-CC292B?style=flat-square&logo=microsoft-sql-server&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-2.0%2B-017CEE?style=flat-square&logo=apache-airflow&logoColor=white)
![NestJS](https://img.shields.io/badge/NestJS-API-E0234E?style=flat-square&logo=nestjs&logoColor=white)
![React](https://img.shields.io/badge/React-Dashboard-61DAFB?style=flat-square&logo=react&logoColor=black)

**An automated Data Engineering pipeline that extracts unstructured financial notifications, transforms and categorizes the data, and persists it into a Star Schema Data Warehouse for real-time dashboard visualization.**

---

## 🚀 Architecture & Engineering Principles

This project is built with strict adherence to **Software Engineering Best Practices**, making it highly scalable and production-ready:

- **Hexagonal Architecture (Ports and Adapters):** The core domain logic is completely isolated from infrastructure (IMAP, SQL Server, APIs). If the data source changes (e.g., extracting from a CRM like HubSpot, Google Analytics, or AWS S3), only a new Adapter needs to be injected.
- **SOLID Principles:** Strongly relies on the **Open/Closed Principle (OCP)**. New banks, notification formats, or data sources can be added by simply creating new parsers without altering the core orchestration engine.
- **Data Quality & Idempotency:** The pipeline guarantees zero duplicate records. Every transaction is tracked via unique `message_id`s, ensuring safe retries and robust data integrity.

## 🏗️ Tech Stack

### 1. Data Engineering & Orchestration
- **Apache Airflow:** Schedules and orchestrates the daily ETL workflows.
- **Python 3.11:** Core ETL engine utilizing object-oriented programming, modern typing, and advanced regex/HTML parsing (BeautifulSoup) for data extraction.

### 2. Data Warehousing
- **Microsoft SQL Server:** Data is modeled using a dimensional **Star Schema** (`dim_tiempo`, `dim_tipo`, `dim_comercio`, `fact_gastos`) to optimize analytical queries and ensure fast retrieval for visualization tools.

### 3. API & Frontend Visualization
- **NestJS (TypeScript):** Provides a secure, read-only REST API to serve the data from the warehouse.
- **React + Vite:** A real-time analytics dashboard to visualize expenses, categorized by merchants and transaction types.

### 4. CI/CD & Testing
- **GitHub Actions:** Automated Continuous Integration pipeline.
- **Pytest:** Extensive unit testing with mocked dependencies and fake data fixtures to ensure reliability without exposing PII (Personally Identifiable Information).

---

## 🧠 Key Features

- **Multi-Source Extraction:** Dynamically scans IMAP mailboxes using highly configurable "Search Profiles", isolating unstructured data directly from automated emails.
- **Intelligent Categorization Engine:** A decoupled categorization port that automatically classifies merchants into business categories (e.g., Food, Transport, Services). Designed to easily integrate AI/ML APIs in the future.
- **Automated Schema Migrations:** The repository layer automatically handles idempotent database migrations, ensuring the Star Schema is always up-to-date.

---

## 🛠️ Local Setup & Execution

### Prerequisites
- Python 3.11+
- ODBC Driver 18 for SQL Server
- Node.js (for Dashboard and API)

### Running the ETL manually (Debug mode)
```bash
# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run pipeline
python scripts/run_local.py --since-days 30
```
