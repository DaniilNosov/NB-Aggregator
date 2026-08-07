# 🏀 NBA Stats Aggregator API

An asynchronous REST API service for automated collection, aggregation, and presentation of NBA match and player statistics.

The service operates in a fully autonomous mode: scheduled background tasks fetch up-to-date data, while the database handles the heavy lifting for calculating players' average stats (points, rebounds, assists) on the fly.

## 🛠 Tech Stack
* **Backend:** Python 3.11, FastAPI
* **Database:** PostgreSQL, SQLAlchemy 2.0 (asyncpg)
* **Background Tasks:** APScheduler
* **Infrastructure:** Docker, Docker Compose

## 🚀 Quick Start (Docker)

The project is fully containerized. You only need Docker installed on your machine to run it.

1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/nba-aggregator.git](https://github.com/YOUR_USERNAME/nba-aggregator.git)
   cd nba-aggregator
   Start the application and database containers:

Bash
docker-compose up --build
The API will be available at: http://127.0.0.1:8000

Interactive API documentation (Swagger UI): http://127.0.0.1:8000/docs

⚙️ Key Architectural Decisions
Asynchronous I/O: All HTTP requests (via httpx) and database sessions are strictly asynchronous, preventing event loop blocking.

Database-level Aggregation: Data aggregation (e.g., top scorers or season average calculations) is performed at the PostgreSQL level using aggregate functions (func.avg, JOIN, GROUP BY) rather than in Python, which significantly optimizes memory usage.

Autonomous Synchronization: Integrated APScheduler (tied to FastAPI lifespan events) runs daily background jobs to sync data, independently managing database transactions via async_sessionmaker.