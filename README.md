# Study Map

A personal learning tracker that uses local AI (Ollama) to classify your study sessions, discover connections between topics, and surface knowledge blindspots. Built with Streamlit and SQLite.

## Features

- **Log daily learning** — record topic, skills, and a summary of what you learnt
- **AI classification** — automatically tags entries with domain, complexity, sub-topics, and key concepts
- **Knowledge graph** — neo4j-style interactive visualisation showing how entries and skills connect
- **Blindspot detection** — AI identifies gaps in your knowledge and suggests what to explore next
- **Analytics dashboard** — charts for learning activity, skill distribution, complexity breakdown, and domains
- **Normalised database** — structured SQLite schema that is easy to query and extend

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/study-map.git
cd study-map

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install and start Ollama
brew install ollama      # macOS
ollama serve &           # start the server
ollama pull llama3.2     # download the model (~2GB)

# 5. (Optional) Copy env config to customise model
cp .env.example .env
```

## Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Project Structure

```
study-map/
├── app.py              # Streamlit application (UI + routing)
├── database.py         # SQLite database layer (schema + queries)
├── ai_service.py       # Ollama AI classification service
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .gitignore          # Excludes .env, .db, __pycache__
└── README.md
```

## Database Schema

The database uses a **normalised relational design** with 6 tables. The SQLite file (`study_map.db`) is created automatically on first run.

### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────────┐       ┌──────────────┐
│   topics     │       │       entries         │       │    skills    │
├──────────────┤       ├──────────────────────-┤       ├──────────────┤
│ id       PK  │◄──┐   │ id              PK    │   ┌──►│ id       PK  │
│ title        │   └───│ topic_id         FK   │   │   │ name         │
│ created_at   │       │ summary               │   │   │ created_at   │
└──────────────┘       │ ai_classification JSON│   │   └──────────────┘
                       │ created_at            │   │
                       └───────┬───────────────┘   │
                               │                   │
                    ┌──────────┼───────────────┐   │
                    │          │               │   │
                    ▼          ▼               ▼   │
          ┌─────────────┐  ┌──────────────┐  ┌────┴──────────┐
          │ connections  │  │  blindspots  │  │ entry_skills  │
          ├─────────────┤  ├──────────────┤  ├───────────────┤
          │ id       PK │  │ id       PK  │  │ entry_id  FK  │
          │ source_entry │  │ entry_id FK  │  │ skill_id  FK  │
          │   _id    FK │  │ suggestion   │  │ (composite PK)│
          │ target_entry │  │ category     │  └───────────────┘
          │   _id    FK │  │ created_at   │
          │ relationship │  └──────────────┘
          │ strength     │
          │ created_at   │
          └─────────────┘
```

### Table Definitions

#### `topics`
Stores unique topic/title names. Reused across entries.

| Column     | Type    | Constraints              |
|------------|---------|--------------------------|
| id         | INTEGER | PRIMARY KEY AUTOINCREMENT |
| title      | TEXT    | NOT NULL, UNIQUE          |
| created_at | TEXT    | DEFAULT datetime('now')   |

#### `skills`
Stores unique skill/course names.

| Column     | Type    | Constraints              |
|------------|---------|--------------------------|
| id         | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name       | TEXT    | NOT NULL, UNIQUE          |
| created_at | TEXT    | DEFAULT datetime('now')   |

#### `entries`
Each row is one learning session. Links to a topic and stores the AI classification as JSON.

| Column            | Type    | Constraints                       |
|-------------------|---------|-----------------------------------|
| id                | INTEGER | PRIMARY KEY AUTOINCREMENT          |
| topic_id          | INTEGER | NOT NULL, FK → topics(id)          |
| summary           | TEXT    | NOT NULL                           |
| ai_classification | TEXT    | JSON blob (nullable)               |
| created_at        | TEXT    | DEFAULT datetime('now')            |

#### `entry_skills`
Many-to-many bridge between entries and skills.

| Column   | Type    | Constraints               |
|----------|---------|---------------------------|
| entry_id | INTEGER | NOT NULL, FK → entries(id) |
| skill_id | INTEGER | NOT NULL, FK → skills(id)  |
|          |         | PRIMARY KEY (entry_id, skill_id) |

#### `connections`
AI-discovered relationships between two entries.

| Column          | Type    | Constraints                       |
|-----------------|---------|-----------------------------------|
| id              | INTEGER | PRIMARY KEY AUTOINCREMENT          |
| source_entry_id | INTEGER | NOT NULL, FK → entries(id)         |
| target_entry_id | INTEGER | NOT NULL, FK → entries(id)         |
| relationship    | TEXT    | NOT NULL (short description)       |
| strength        | REAL    | NOT NULL, DEFAULT 0.5 (0.0 – 1.0) |
| created_at      | TEXT    | DEFAULT datetime('now')            |

#### `blindspots`
AI-suggested knowledge gaps linked to the entry that triggered them.

| Column     | Type    | Constraints                       |
|------------|---------|-----------------------------------|
| id         | INTEGER | PRIMARY KEY AUTOINCREMENT          |
| entry_id   | INTEGER | NOT NULL, FK → entries(id)         |
| suggestion | TEXT    | NOT NULL                           |
| category   | TEXT    | nullable (e.g. prerequisite, adjacent, deeper-dive) |
| created_at | TEXT    | DEFAULT datetime('now')            |

### Example Queries

```sql
-- All entries with their topics and skills
SELECT e.id, t.title, e.summary, GROUP_CONCAT(s.name, ', ') AS skills
FROM entries e
JOIN topics t ON t.id = e.topic_id
LEFT JOIN entry_skills es ON es.entry_id = e.id
LEFT JOIN skills s ON s.id = es.skill_id
GROUP BY e.id;

-- Connections between entries
SELECT t1.title AS from_topic, t2.title AS to_topic,
       c.relationship, c.strength
FROM connections c
JOIN entries e1 ON e1.id = c.source_entry_id
JOIN entries e2 ON e2.id = c.target_entry_id
JOIN topics t1 ON t1.id = e1.topic_id
JOIN topics t2 ON t2.id = e2.topic_id;

-- All blindspots grouped by category
SELECT category, suggestion, t.title AS related_topic
FROM blindspots b
JOIN entries e ON e.id = b.entry_id
JOIN topics t ON t.id = e.topic_id
ORDER BY category, b.created_at DESC;
```

## Configuration

| Variable         | Default                  | Description                    |
|------------------|--------------------------|--------------------------------|
| `OLLAMA_BASE_URL`| `http://localhost:11434` | Ollama server address          |
| `OLLAMA_MODEL`   | `llama3.2`               | Model to use for classification |

Set these in a `.env` file or as environment variables.

## Tech Stack

| Component       | Technology              |
|-----------------|-------------------------|
| Frontend / BI   | Streamlit               |
| AI Engine       | Ollama (local LLM)      |
| Database        | SQLite                  |
| Graph Viz       | streamlit-agraph (vis.js)|
| Charts          | Plotly                  |
| Styling         | Custom CSS (glassmorphism, Inter font) |

## License

MIT
