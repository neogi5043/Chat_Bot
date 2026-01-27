# GenAI Chatbot for Demand Management System

A natural-language-to-SQL chatbot designed to query a PostgreSQL database, execute intelligent SQL queries, and provide data-driven insights. This system uses Groq (Meta Llama 3) for LLM capabilities.

##  Features

- **Natural Language to SQL**: Converts user questions into accurate PostgreSQL queries.
- **Intelligent Pipeline**:
  - **Intent Classification**: Distinguishes between general conversation and data queries.
  - **Schema Awareness**: Dynamically fetches database schema and relationships.
  - **Validation & Auto-Fix**: Validates generated SQL and attempts to auto-correct errors.
  - **Empty Result Analysis**: Automatically analyzes why a query returned no data and suggests fuzzy-match alternatives.
- **Caching**: Implements query caching to reduce latency and API costs.
- **Insights Generation**: Summarizes query results into concise, metric-focused insights.
- **Robust Error Handling**: Handles SQL execution errors and retry logic gracefully.

##  Architecture

The project is structured around a modular pipeline:

1.  **`chatbot.py`**: Main entry point and orchestration pipeline. Handles logging, retry logic, and result presentation.
2.  **`llm.py`**: Manages all interactions with the Groq API (Intent, SQL generation, Insights).
3.  **`db.py`**: Database layer for connection management, schema introspection, and query execution.
4.  **`validation.py`**: SQL validation rules to ensure safe and correct queries.
5.  **`post_execution_analyzer.py`**: Analyzes empty or null results to improve query accuracy.
6.  **`cache.py`**: Simple in-memory caching for generated queries.

##  Prerequisites

- **Python** 3.8 or higher
- **PostgreSQL** Database
- **Groq API Key** (for LLM access)

##  Installation

1.  **Clone the repository**
    ```bash
    git clone <repository_url>
    cd Genai_chatbot
    ```

2.  **Create and activate a virtual environment**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the root directory with your credentials:

    ```ini
    # Database Configuration
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=your_db_name
    DB_USER=your_username
    DB_PASSWORD=your_password

    # LLM API
    GROQ_API_KEY=gsk_...
    ```

##  Usage

To run the chatbot in CLI mode:

```bash
python chatbot.py
```

The script will execute a predefined set of test queries (configured in `main()` function) and display:
1.  Generated SQL
2.  Query Results (DataFrame)
3.  AI-Generated Insights
4.  Execution Statistics

### Example Output

```text
QUERY: list all open demands of digital engineering

generated SQL:
SELECT * FROM demands WHERE status = 'Open' AND department = 'Digital Engineering'

Results:
   id       title          status         department
0  101  Cloud Migration     Open      Digital Engineering
...

Insights:
There are currently 5 open demands in Digital Engineering, with the majority focused on Cloud Migration projects.
```

##  Project Structure

```text
.
├── chatbot.py                 # Main pipeline and CLI entry point
├── llm.py                     # LLM integration (Groq) & prompt management
├── db.py                      # Database connection & provided schema fetching
├── prompt.py                  # System prompts for insights
├── sql_prompts.py             # System prompts for SQL generation
├── input_prompts.py           # Example inputs
├── cache.py                   # Caching utility
├── validation.py              # SQL validation logic
├── few_shot.py                # Few-shot example retrieval
├── post_execution_analyzer.py # Logic for analyzing empty results
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (not committed)
└── IMPROVEMENT_PLAN.md        # Technical debt and authorized improvements
```

##  Troubleshooting

- **Database Connection Error**: Verify your `.env` credentials and ensure the PostgreSQL service is running.
- **Empty Results**: The system will attempt to find "close matches" if exact string matches fail (e.g., "DevOps" vs "Dev Ops"). Check the logs for `[RETRY]` messages.
- **LLM Errors**: Ensure your `GROQ_API_KEY` is valid and you haven't exceeded rate limits.
