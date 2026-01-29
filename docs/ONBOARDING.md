
# 🚢 Developers' Onboarding Guide

Welcome to the **Demand Management GenAI Chatbot** team! 

This guide is designed to take you from "I just cloned the repo" to "I understand how this thing thinks" as quickly as possible. We’ll start simple and dive deep.

---

## 🌎 1. The Big Picture (Start Here)

### What is this project?
At its core, this is a **Text-to-SQL system**. 
Users ask questions in plain English (e.g., *"Show me all projects over budget in Q1"*), and the system:
1.  Understands the business intent.
2.  Writes a SQL query against our PostgreSQL database.
3.  Executes it.
4.  Explains the results back to the user.

### Why not just use ChatGPT?
Standard LLMs don't know our database schema, our business logic (what "over budget" *actually* means), or our extensive list of project codes. We built a **Multi-Agent System** to bridge that gap.

### The Architecture: "The Assembly Line"
Think of our system as a factory assembly line. A user's query is the raw material, and it passes through several specialized stations (Agents) before becoming a finished answer.

*   **Station 1: The Librarian (Schema Selector)**
    *   *Problem*: We have 50+ tables. Sending all of them to the LLM is too expensive and confusing.
    *   *Action*: Finds the top 5 relevant tables for the specific question.
*   **Station 2: The Translator (Entity Resolver)**
    *   *Problem*: Users say "Project Phoenix", but the DB only knows `proj_id_501`.
    *   *Action*: Maps fuzzy names to exact IDs.
*   **Station 3: The Planner (Decomposer)**
    *   *Problem*: Complex questions overwhelm the LLM.
    *   *Action*: Breaks "Compare Q1 and Q2" into Step 1 (Get Q1) -> Step 2 (Get Q2) -> Step 3 (Compare).
*   **Station 4: The Coder (SQL Generator)**
    *   *Action*: Writes the actual SQL code using the filtered schema and planned steps.
*   **Station 5: The Reviewer (Validator)**
    *   *Action*: Checks the code for syntax errors and hallucinations before running it.
*   **Station 6: The Runner (Execution Engine)**
    *   *Action*: Runs the query safely.
*   **Station 7: The Fixer (Correction Agent)**
    *   *Action*: If the Runner says "Error", the Fixer looks at the error message and tries to rewrite the code.

---

## 📂 2. Folder Structure (Where things live)

We follow a modular `src/` layout. Here is where you will spend 90% of your time:

```text
src/
├── agents/             # <--- THE BRAINS. All the agents described above live here.
│   ├── orchestrator.py # The manager that coordinates the assembly line.
│   ├── semantic_layer.py # The interface to our business definitions.
│   └── ... (individual agent files)
├── semantic/           # <--- THE MEMORY. JSON files defining business logic.
│   ├── business_metrics.json (Formulas)
│   ├── data_dictionary.json (Table descriptions)
│   └── entity_mappings.json (Value mappings)
├── pipeline/           # <--- THE GLUE.
│   ├── chatbot.py      # Connects user input to the Orchestrator.
└── common/             # <--- THE TOOLS.
    ├── db.py           # Database connections.
    ├── llm.py          # LLM API wrappers.
    └── constants.py    # Shared constants (IntentType, etc).
```

---

## 🧩 3. Core Modules Deep Dive

### A. The Orchestrator (`src/agents/orchestrator.py`)
This is the entry point for the "Brain".
*   **Role**: It initializes all agents and passes the data from one to the next.
*   **Key Function**: `process_query(user_query)`
*   **Flow**: 
    `User Query` -> `Schema Selector` -> `Entity Resolver` -> `Decomposer` -> `SQL Generator` -> `Validator` -> `Executor`.
*   **Self-Correction**: It has a loop! If usage fails validation or execution, it calls the `CorrectionAgent` to try again *automatically*.

### B. The Semantic Layer (`src/agents/semantic_layer.py`)
This module reads the JSON files in `src/semantic/`.
*   **Why**: We don't want to hardcode business logic in Python.
*   **Example**: If the definition of "Attrition" changes, we update `business_metrics.json`, not the Python code.
*   **Best Practice**: Always fetch metric definitions through this layer, never import the JSON directly.

### C. Feedback Manager (`src/agents/feedback_manager.py`)
This is our "Active Learning" component.
*   **What it does**: Logs every successful and failed query to `feedback_history.json`.
*   **Why**: The `SQL Generator` looks at this history ("Few-Shot Learning") to see how it solved similar problems in the past. This means the system **gets smarter the more it is used**.

---

## 🚦 4. Control Flow & State

The system is primarily **stateless** between queries, but **stateful** regarding learning.

1.  **Request State**: Handled by `src/pipeline/chatbot.py`. It calls the Orchestrator and simply returns the result. It doesn't remember previous conversation turns (yet).
2.  **Long-term State**: Stored in `feedback_history.json`. This is persistent knowledge.

---

## ⚠️ 5. Common Pitfalls & Gotchas

*   **1. The "Ambiguous Column" Trap**
    *   *Issue*: Asking "Show me status" often fails if multiple tables have a `status` column.
    *   *Fix*: The `Schema Selector` usually handles this, but if you add new tables, ensure column names are distinct or well-described in `data_dictionary.json`.

*   **2. JSON format limits**
    *   *Issue*: `pandas` DataFrames can contain `NaN` (Not a Number) or `Infinity`. These crash standard JSON parsers when sending results to the frontend.
    *   *Fix*: We handle this in `app.py` by converting `NaN` to `None`. Always check for this if you modify result formatting.

*   **3. LLM Hallucinations**
    *   *Issue*: Sometimes the LLM invents a column that doesn't exist.
    *   *Defense*: This is why `ValidationAgent` exists. It checks the generated SQL against the actual schema before execution. If you see execution errors, check if the Validator missed something.

---

## 🚀 6. How to Get Started (First 30 Minutes)

Ready to write code? Follow these steps:

**Step 1: Environmental Setup**
Ensure you have Python 3.9+ and pip installed.
```bash
pip install -r requirements.txt
```

**Step 2: Configuration**
Create a `.env` file in the root directory (ask a lead for the API keys):
```ini
GROQ_API_KEY=...
DB_HOST=localhost
DB_NAME=demand_db
...
```

**Step 3: Run the CLI**
Talk to the bot to see it in action.
```bash
python app.py
```
*Try asking: "Show me all active projects."*

**Step 4: Check the Logs**
Open `chatbot.log`. You should see the entire thought process:
*   [INFO] Processing query...
*   [INFO] Selected tables: ...
*   [INFO] Generated SQL: ...

**Step 5: Make a small change**
*   Open `src/common/constants.py`.
*   Add a new IntentType.
*   See if you can trace where it's used in `chatbot.py`.

---

Welcome to the team! If you get stuck, check the `docs/` folder for architecture diagrams or ask the Orchestrator via `app.py`. Happy coding! 👩‍💻👨‍💻
