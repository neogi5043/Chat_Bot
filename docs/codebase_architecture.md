# Codebase Architecture

This document outlines the modular structure of the Demand Management Chatbot repository. The codebase has been organized to separate concerns between the Agentic Logic, Shared Infrastructure, Data Configuration, and Testing.

## Directory Tree

```text
root/
├── app.py                     # Application Entry Point (Streamlit/Console wrapper)
├── src/                       # Main Source Code Package
│   ├── agents/                # Agent Swarm (The Brain)
│   ├── semantic/              # Semantic Knowledge Base (The Memory)
│   ├── pipeline/              # Application Logic Flow
│   ├── common/                # Shared Infrastructure (DB, LLM, Utils)
│   └── prompts/               # LLM System Prompts
├── tests/                     # Test Suites
│   ├── e2e/                   # End-to-End Test Runners
│   └── fixtures/              # Test Data & Query Lists
├── data/                      # Data Artifacts (Schemas, Logs)
├── scripts/                   # Maintenance Scripts
└── docs/                      # Documentation
```

---

## Component Details

### 1. Source Code (`src/`)

#### `src/agents/`
Contains the core agents responsible for reasoning and execution.
*   **`orchestrator.py`**: The central brain. Receives queries, dispatches tasks to sub-agents, and compiles results.
*   **`semantic_layer.py`**: Python interface that loads and serves the JSON configurations from `src/semantic/`.
*   **`schema_selector.py`**: Agent responsible for finding relevant tables (`RECALL`).
*   **`entity_resolver.py`**: Maps natural language terms to DB values (e.g., "Sayan" -> `users.name`).
*   **`sql_generator.py`**: Consumes the plan and generates SQL.
*   **`validator.py`**: Static analysis of generated SQL.
*   **`correction_agent.py`**: Auto-corrects SQL based on error feedback.
*   **`feedback_manager.py`**: Manages active learning history and few-shot examples.

#### `src/semantic/`
Configuration files defining the business domain.
*   **`data_dictionary.json`**: Technical metadata + Business definitions for every table and column.
*   **`join_paths.json`**: Directed graph defining how tables link (JOIN logic).
*   **`business_metrics.json`**: Logic for complex named metrics (e.g., "Fill Rate").
*   **`entity_mappings.json`**: Low-cardinality values for entity resolution.

#### `src/pipeline/`
Higher-level flows that wrap the agents.
*   **`chatbot.py`**: Manages the conversation loop, intent classification, and formatting results for the UI.
*   **`post_execution_analyzer.py`**: Generates business insights/summaries from the raw SQL results.

#### `src/common/`
Shared utilities used across the system.
*   **`db.py`**: Database connection pooling and execution primitives.
*   **`llm.py`**: Wrapper for Groq API calls (Handling token limits, serialization).
*   **`feedback.py`**: Manages the `feedback_history.json` loop for active learning.
*   **`cache.py`**: Caches SQL results to reduce latency/costs.

#### `src/prompts/`
*   **`prompt.py`**: Templates for Insights generation.
*   **`sql_prompts.py`**: System instructions for the SQL Generator Agent.
*   **`few_shot.py`**: Dynamic example loader for in-context learning.

---

### 2. Tests (`tests/`)

*   **`e2e/run_test_suite.py`**: The main regression tester. Reads queries from `fixtures/`, executes them against the pipeline, and reports Pass/Fail.
*   **`fixtures/test.txt`**: List of "Golden" queries for regression testing.

### 3. Data (`data/`)

*   **`schema_full.json`**: Raw dump of the database schema (used for syncing).
*   **`feedback_history.json`**: Permanent store of (Query -> Correct SQL) pairs used for Few-Shot learning.

---

## Key Flows

### Text-to-SQL Flow
1.  **`app.py`** receives string.
2.  **`src.pipeline.chatbot`** determines intent.
3.  **`src.agents.orchestrator`** takes over:
    *   Calls **Schema Selector** -> Partial Schema.
    *   Calls **Entity Resolver** -> Mapped Values.
    *   Calls **SQL Generator** -> Candidate SQL.
    *   Calls **Validator** -> Checked SQL.
    *   Calls **Execution Engine** -> Results.
4.  **`src.pipeline.chatbot`** passes results to `llm.generate_insights`.
5.  Response returned to user.
