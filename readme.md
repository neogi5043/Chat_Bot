# GenAI Chatbot for Demand Management System

A natural-language-to-SQL chatbot designed to query a PostgreSQL database, execute intelligent SQL queries, and provide data-driven insights. This system uses Groq (Meta Llama 3) for LLM capabilities.

## 🚀 Features

- **Natural Language to SQL**: Converts user questions into accurate PostgreSQL queries.
- **Intelligent Pipeline**:
  - **Intent Classification**: Distinguishes between general conversation and data queries.
  - **Schema Awareness & Semantic Layer**: Dynamically fetches database schema and uses a **Semantic Layer** to map vague terms of exact database values (e.g., "dev ops" -> "Cloud & DevOps").
  - **Chain-of-Thought Reasoning**: The AI explains its logic before generating SQL, reducing errors.
  - **Validation & Auto-Fix**: Validates generated SQL and attempts to auto-correct errors.
  - **Empty Result Analysis**: Automatically analyzes why a query returned no data and suggests fuzzy-match alternatives.
- **Caching**: Implements query caching to reduce latency and API costs.
- **Insights Generation**: Summarizes query results into concise, metric-focused insights.
- **Robust Error Handling**: Handles SQL execution errors and retry logic gracefully.

## 🛠️ Architecture

The project is structured around a modular pipeline:

1.  **`chatbot.py`**: Main entry point and orchestration pipeline. Handles logging, retry logic, and result presentation.
2.  **`llm.py`**: Manages all interactions with the Groq API (Intent, SQL generation, Insights) and injects the Semantic Layer.
3.  **`db.py`**: Database layer for connection management, schema introspection, and query execution.
4.  **`semantic_builder.py`**: **[NEW]** Scans the database to build `semantic_schema.json`, enabling exact value matching.
5.  **`validation.py`**: SQL validation rules to ensure safe and correct queries.
6.  **`post_execution_analyzer.py`**: Analyzes empty or null results to improve query accuracy.
7.  **`sql_prompts.py`**: Contains the Chain-of-Thought system prompts.
8.  **`cache.py`**: Simple in-memory caching for generated queries.

## 📋 Prerequisites

- **Python** 3.8 or higher
- **PostgreSQL** Database
- **Groq API Key** (for LLM access)

## 📦 Installation

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

## 🚀 Usage

### 1. Build the Semantic Layer (Important!)
Before running the chatbot, scan your database to map valid values:

```bash
python semantic_builder.py
```
*Run this occasionally when your data changes (e.g., new departments or status types).*

### 2. Run the Chatbot
To run the chatbot in CLI mode:

```bash
python chatbot.py
```

The script will execute a predefined set of test queries (configured in `main()` function) and display:
1.  **Thinking Process** (Chain of Thought)
2.  Generated SQL
3.  Query Results (DataFrame)
4.  AI-Generated Insights
5.  Execution Statistics

### Example Output

```text
QUERY: No of demands created per month in last 6 months

[DEBUG] Schema Context Sent to LLM:
----------------------------------------
TABLE: demands
  - status -> Valid Values: ['Open', 'Cancelled', 'Pending', 'Fulfilled']
...

Generated SQL:
/* Reasoning: 
1. Group by month of created_at...
2. Filter for last 6 months...
*/
SELECT EXTRACT(MONTH FROM created_at) as month, COUNT(*) ...

Results:
   month  count
0    9.0     12
1   10.0      5
...
```

## 📂 Project Structure

```text
.
├── chatbot.py                 # Main pipeline and CLI entry point
├── llm.py                     # LLM integration (Groq) & prompt management
├── db.py                      # Database connection & provided schema fetching
├── semantic_builder.py        # [NEW] Builds the semantic value map
├── semantic_schema.json       # [Auto-Generated] Valid values for the LLM
├── sql_prompts.py             # [NEW] System prompts for SQL generation
├── prompt.py                  # System prompts for insights
├── input_prompts.py           # Example inputs
├── cache.py                   # Caching utility
├── validation.py              # SQL validation logic
├── few_shot.py                # Few-shot example retrieval
├── post_execution_analyzer.py # Logic for analyzing empty results
├── requirements.txt           # Python dependencies
└── .env                       # Environment variables (not committed)
```

## 🔧 Troubleshooting

- **Database Connection Error**: Verify your `.env` credentials and ensure the PostgreSQL service is running.
- **Empty Results**: 
  - Check if `semantic_schema.json` is generated. If not, run `python semantic_builder.py`.
  - The system attempts to explain empty results (e.g. "No fulfilled demands found").
- **LLM Errors**: Ensure your `GROQ_API_KEY` is valid.
