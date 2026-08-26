# InvestIQ

AI-Based Portfolio Management System for PSX Investors

A bilingual (English/Urdu) AI advisor that turns raw PSX data into a personalized, fully-costed, jargon-free investment portfolio for novice Pakistani retail investors — advisory only, no trade execution.

## Local Setup Instructions

This project uses a monorepo structure with npm workspaces for the frontends/packages, and Python for the backend services.

### 1. Infrastructure (Database & Cache)
Ensure you have Docker installed.
```bash
cd infra
docker-compose up -d
```
*Note: Postgres is exposed on port 5435 to avoid conflicts with local installations.*

### 2. Backend API
```bash
cd services/api
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```
The API will be available at `http://127.0.0.1:8000`. Test the health endpoint at `http://127.0.0.1:8000/health`.

### 3. Web & Mobile Apps (Frontends)
From the root directory, install the npm workspaces:
```bash
npm install
```

**To run the Web App:**
```bash
cd apps/web
npm run dev
```
Open `http://localhost:5173`.

**To run the Mobile App:**
```bash
cd apps/mobile
npx expo start
```
Use the Expo Go app or press `a`/`i` to launch an emulator.

### Code Quality (CI / CD)
Run the following commands from the project root to check linting and formatting:
```bash
npm run format
npm run lint
```
For the Python backend (from `services/api` inside the venv):
```bash
ruff check .
black --check .
python -m pytest
```
