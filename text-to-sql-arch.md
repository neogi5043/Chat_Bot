# Text-to-SQL System: Comprehensive Technical Architecture

## Executive Summary

This document outlines a production-grade, multi-agent Text-to-SQL architecture designed to achieve >95% accuracy through semantic enrichment, dynamic schema linking, agentic decomposition, and iterative refinement. The system combines LangChain/LlamaIndex frameworks with custom agents and semantic layers to bridge natural language intent with precise SQL execution.

---

## 1. System Overview & Core Principles

### 1.1 High-Level Data Flow

```
User Query
    ↓
[INPUT PROCESSOR]
    ↓
[SEMANTIC LAYER] ← (Business Metadata)
    ↓
[SCHEMA SELECTOR AGENT] ← (Vector DB: Table Embeddings)
    ↓
[ENTITY RESOLVER] ← (Vector DB: Value Mappings)
    ↓
[DECOMPOSER AGENT] ← (Few-shot examples)
    ↓
[SQL GENERATOR AGENT] ← (LLM: Claude/GPT-4)
    ↓
[VALIDATOR AGENT]
    ↓
[EXECUTION ENGINE] → [DATABASE]
    ↓
[RESULTS PROCESSOR] → [USER RESPONSE]
```

### 1.2 Key Architecture Principles

1. **Separation of Concerns**: Each agent has a single, well-defined responsibility
2. **RAG Integration**: Dynamic context retrieval at each stage prevents token overflow
3. **Semantic Foundation**: Business logic lives in the semantic layer, not in LLM prompts
4. **Iterative Refinement**: Validation → Error Detection → Correction loop
5. **Observability**: Complete logging for evaluation and active learning

---

## 2. Component Architecture

### 2.1 Semantic Layer (Foundation)

**Purpose**: Single source of truth for business definitions, metrics, and entity mappings.

**Implementation**:
```
semantic_layer/
├── business_metrics.json
├── data_dictionary.json
├── entity_mappings.json
├── join_paths.json
└── access_policies.json
```

**Content Structure**:

```json
{
  "business_metrics": {
    "attrition_rate": {
      "name": "Employee Attrition Rate",
      "formula": "(COUNT(DISTINCT terminated_id) / COUNT(DISTINCT total_employees)) * 100",
      "required_tables": ["employees", "terminations"],
      "required_columns": ["employees.emp_id", "terminations.emp_id", "terminations.end_date"],
      "definition": "Percentage of workforce that left during fiscal year",
      "owner": "HR Analytics",
      "last_updated": "2026-01-28"
    }
  },
  "data_dictionary": {
    "projects": {
      "table_id": "t_projects",
      "business_name": "Projects",
      "description": "All company projects with budgets and status",
      "columns": {
        "amount": {
          "type": "DECIMAL(10,2)",
          "business_term": "Project Budget",
          "description": "Total approved project budget in USD currency, not quantity",
          "sample_values": [50000.00, 125000.50, 250000.75],
          "constraints": "Non-negative, max 10000000, required",
          "pii_flag": false
        },
        "project_name": {
          "type": "VARCHAR(255)",
          "business_term": "Project Name",
          "description": "Official project name as registered in system",
          "sample_values": ["Phoenix Implementation Phase 1", "Digital Transformation Q2"],
          "unique_flag": true
        }
      }
    }
  },
  "entity_mappings": {
    "project_names": {
      "type": "categorical_values",
      "source_table": "projects",
      "source_column": "project_name",
      "vector_embeddings": true,
      "refresh_frequency": "daily",
      "values": [
        {
          "id": "proj_001",
          "canonical_value": "Phoenix Implementation Phase 1",
          "aliases": ["Project Phoenix", "Phoenix Phase 1", "Phoenix P1"],
          "embedding": [0.234, 0.445, ...]
        }
      ]
    },
    "department_codes": {
      "type": "categorical_values",
      "source_table": "departments",
      "source_column": "dept_code",
      "values": [
        {
          "id": "dept_001",
          "canonical_value": "ENGG",
          "aliases": ["Engineering", "ENG", "Tech"],
          "embedding": [0.123, 0.456, ...]
        }
      ]
    }
  },
  "join_paths": {
    "projects_to_employees": {
      "path": "projects.id → project_assignments.project_id → project_assignments.emp_id → employees.emp_id",
      "description": "Path to find employees assigned to projects",
      "join_conditions": [
        "projects.id = project_assignments.project_id",
        "project_assignments.emp_id = employees.emp_id"
      ]
    }
  }
}
```

---

### 2.2 Schema Selector Agent

**Purpose**: Reduce large schemas to top-K relevant tables for LLM processing.

**Implementation Approach**: 

```python
class SchemaSelectorAgent:
    """
    Selects top-K relevant tables from large databases
    using semantic similarity + keyword matching.
    """
    
    def __init__(self, vector_db, metadata_store):
        self.vector_db = vector_db  # FAISS or Chroma
        self.metadata_store = metadata_store
        self.top_k = 5
    
    def select_schema(self, user_query: str) -> List[TableSchema]:
        """
        1. Embed user query
        2. Search vector DB for similar table names/descriptions
        3. Add tables via foreign key relationships
        4. Return condensed schema
        """
        # Step 1: Semantic search
        query_embedding = embed(user_query)
        candidates = self.vector_db.search(
            query_embedding, 
            top_k=self.top_k
        )
        
        # Step 2: Expand with join paths
        selected_tables = candidates.copy()
        for table in candidates:
            connected = self.get_join_neighbors(table)
            selected_tables.extend(connected)
        
        # Step 3: Deduplicate and return
        return list({t.id: t for t in selected_tables}.values())
    
    def get_join_neighbors(self, table: Table) -> List[Table]:
        """Fetch tables directly connected via foreign keys"""
        join_paths = self.metadata_store.query(
            f"SELECT * FROM join_paths WHERE source_table = '{table.id}'"
        )
        return [self.metadata_store.get_table(path.target) 
                for path in join_paths]
```

**Output**: Condensed schema with only relevant tables.

---

### 2.3 Entity Resolver Agent

**Purpose**: Map fuzzy user inputs to canonical database values.

**Implementation Approach**:

```python
class EntityResolverAgent:
    """
    Resolves user-provided values to actual database values
    using vector similarity + edit distance.
    """
    
    def __init__(self, semantic_layer, vector_db):
        self.semantic_layer = semantic_layer
        self.vector_db = vector_db
        self.threshold = 0.85  # Cosine similarity threshold
    
    def resolve_entities(self, user_query: str, selected_tables: List[Table]):
        """
        For each table, extract entity references from query
        and map to canonical values.
        
        Example: "Project Phoenix" → "Phoenix Implementation Phase 1"
        """
        resolutions = {}
        
        for table in selected_tables:
            # Get categorical columns with mappings
            categorical_cols = self.semantic_layer.get_categorical_columns(
                table.id
            )
            
            for col in categorical_cols:
                mappings = self.semantic_layer.get_entity_mappings(
                    table.id, col.name
                )
                
                # Extract potential values from query
                potential_values = self._extract_from_query(
                    user_query, col.business_term
                )
                
                # Resolve each to canonical value
                for value in potential_values:
                    canonical = self._resolve_value(
                        value, mappings
                    )
                    resolutions[f"{table.id}.{col.name}"] = canonical
        
        return resolutions
    
    def _resolve_value(self, user_value: str, mappings: List[Mapping]):
        """
        Match user value to canonical value using:
        1. Vector similarity
        2. Edit distance
        3. Exact match in aliases
        """
        best_match = None
        best_score = 0
        
        user_embedding = embed(user_value)
        
        for mapping in mappings:
            # Vector similarity score
            sim_score = cosine_similarity(
                user_embedding, 
                mapping.embedding
            )
            
            # Edit distance bonus
            for alias in mapping.aliases:
                edit_score = 1.0 - (
                    editdistance(user_value.lower(), alias.lower()) / 
                    max(len(user_value), len(alias))
                )
                sim_score = max(sim_score, edit_score)
            
            if sim_score > best_score:
                best_score = sim_score
                best_match = mapping
        
        if best_score > self.threshold:
            return {
                "user_input": user_value,
                "canonical_value": best_match.canonical_value,
                "confidence": best_score,
                "table": best_match.source_table,
                "column": best_match.source_column
            }
        else:
            return None  # No confident match
```

**Output**: Mapping of user values to canonical database values with confidence scores.

---

### 2.4 Decomposer Agent

**Purpose**: Break complex queries into manageable sub-problems using Chain-of-Thought.

**Implementation Approach**:

```python
class DecomposerAgent:
    """
    Uses LLM to decompose complex natural language queries
    into logical steps and sub-queries.
    """
    
    def __init__(self, llm, few_shot_examples):
        self.llm = llm  # Claude or GPT-4
        self.few_shot_examples = few_shot_examples
    
    def decompose(self, user_query: str, semantic_layer) -> QueryPlan:
        """
        Decompose complex query into logical steps.
        
        Example:
        Input: "Compare Q1 sales with Q2 and show growth %"
        Output:
        {
            "steps": [
                {"id": 1, "type": "aggregation", "description": "Get Q1 Sales"},
                {"id": 2, "type": "aggregation", "description": "Get Q2 Sales"},
                {"id": 3, "type": "calculation", "description": "Calculate growth %"}
            ]
        }
        """
        
        prompt = self._build_decomposition_prompt(
            user_query=user_query,
            semantic_layer=semantic_layer,
            few_shot_examples=self.few_shot_examples
        )
        
        response = self.llm.generate(prompt)
        
        # Parse structured output
        query_plan = self._parse_query_plan(response)
        
        return query_plan
    
    def _build_decomposition_prompt(self, user_query, semantic_layer, few_shot_examples):
        """
        Construct prompt with:
        1. Task definition
        2. Few-shot examples of decompositions
        3. Semantic layer context (business metrics)
        4. User query
        """
        prompt = f"""
You are a SQL query planner. Your task is to decompose natural language 
business questions into logical steps.

## Business Context
Business Metrics Available:
{json.dumps(semantic_layer.business_metrics, indent=2)}

## Few-Shot Examples

Example 1:
Q: "Show me monthly revenue trends"
A: {{
  "steps": [
    {{"id": 1, "description": "Group sales by month"}},
    {{"id": 2, "description": "Sum revenue by month"}},
    {{"id": 3, "description": "Order chronologically"}}
  ]
}}

Example 2:
Q: "Compare Q1 sales with Q2 and show growth percentage"
A: {{
  "steps": [
    {{"id": 1, "description": "Calculate Q1 total sales"}},
    {{"id": 2, "description": "Calculate Q2 total sales"}},
    {{"id": 3, "description": "Calculate (Q2-Q1)/Q1 * 100"}},
    {{"id": 4, "description": "Return comparison as single row"}}
  ]
}}

## Your Task
Decompose this query: "{user_query}"

Return a JSON object with "steps" array following the format above.
"""
        return prompt
```

**Output**: Structured query plan with logical steps and dependencies.

---

### 2.5 SQL Generator Agent

**Purpose**: Generate syntactically correct SQL from decomposed query plan.

**Implementation Approach**:

```python
class SQLGeneratorAgent:
    """
    Generates SQL queries step-by-step using:
    1. Decomposed query plan
    2. Selected schema
    3. Resolved entities
    4. Few-shot examples from feedback loop
    """
    
    def __init__(self, llm, few_shot_db, semantic_layer):
        self.llm = llm
        self.few_shot_db = few_shot_db  # Historical successful SQLs
        self.semantic_layer = semantic_layer
    
    def generate_sql(
        self, 
        query_plan: QueryPlan,
        selected_schema: List[Table],
        entity_resolutions: dict,
        user_query: str
    ) -> str:
        """
        Generate complete SQL query.
        """
        
        # Select most similar few-shot examples
        similar_examples = self._retrieve_few_shots(user_query, top_k=3)
        
        # Build comprehensive prompt
        prompt = self._build_generation_prompt(
            user_query=user_query,
            query_plan=query_plan,
            selected_schema=selected_schema,
            entity_resolutions=entity_resolutions,
            business_metrics=self.semantic_layer.business_metrics,
            few_shot_examples=similar_examples,
            sql_dialect="PostgreSQL"  # or Snowflake, BigQuery, etc.
        )
        
        # Generate SQL
        generated_sql = self.llm.generate(prompt)
        
        # Extract SQL from response (strip markdown, comments, etc.)
        sql = self._extract_sql(generated_sql)
        
        return sql
    
    def _build_generation_prompt(
        self, 
        user_query, 
        query_plan, 
        selected_schema,
        entity_resolutions,
        business_metrics,
        few_shot_examples,
        sql_dialect
    ):
        """
        Multi-part prompt:
        1. Instructions & context
        2. Business metrics definitions
        3. Schema definitions
        4. Entity resolution mappings
        5. Few-shot examples
        6. Query plan & user question
        """
        
        prompt = f"""
# Task: Generate SQL Query

## Database Dialect
{sql_dialect}

## Business Metrics & Definitions
{json.dumps(business_metrics, indent=2)}

## Schema Information
{self._format_schema(selected_schema)}

## Entity Resolutions
The following user inputs map to database values:
{json.dumps(entity_resolutions, indent=2)}

## Few-Shot Examples (Similar Previous Queries)
"""
        
        for example in few_shot_examples:
            prompt += f"""
### Example {example.id}
Question: {example.user_question}
SQL: 
```sql
{example.sql}
```
"""
        
        prompt += f"""

## Query Decomposition Plan
{json.dumps(query_plan.steps, indent=2)}

## Your Task
Generate SQL for this question: "{user_query}"

Requirements:
- Use ONLY tables present in the schema above
- Apply entity resolutions where provided
- Match the SQL dialect ({sql_dialect})
- Include column aliases for clarity
- Add comments explaining complex logic

Output only the SQL query without markdown or explanation.
"""
        
        return prompt
    
    def _retrieve_few_shots(self, user_query: str, top_k: int = 3):
        """
        Retrieve similar examples from corrected feedback loop.
        Uses vector similarity on question text.
        """
        query_embedding = embed(user_query)
        
        similar = self.few_shot_db.search(
            query_embedding,
            top_k=top_k,
            filters={"execution_success": True}  # Only correct examples
        )
        
        return similar
    
    def _format_schema(self, selected_schema: List[Table]) -> str:
        """Format selected schema for prompt inclusion"""
        schema_str = ""
        
        for table in selected_schema:
            schema_str += f"\nTable: {table.name} (ID: {table.id})\n"
            schema_str += f"Description: {table.description}\n"
            schema_str += "Columns:\n"
            
            for col in table.columns:
                schema_str += f"  - {col.name} ({col.type}): {col.description}\n"
            
            if table.primary_key:
                schema_str += f"Primary Key: {table.primary_key}\n"
            
            if table.foreign_keys:
                schema_str += "Foreign Keys:\n"
                for fk in table.foreign_keys:
                    schema_str += f"  - {fk.column} → {fk.ref_table}.{fk.ref_column}\n"
        
        return schema_str
    
    def _extract_sql(self, llm_response: str) -> str:
        """Extract SQL from LLM response (handles markdown, etc.)"""
        # Remove markdown code blocks
        import re
        sql_match = re.search(r'```(?:sql)?\n(.*?)\n```', llm_response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        return llm_response.strip()
```

**Output**: Complete, executable SQL query.

---

### 2.6 Validator Agent

**Purpose**: Check SQL syntax, verify schema compliance, and detect potential errors before execution.

**Implementation Approach**:

```python
class ValidatorAgent:
    """
    Validates generated SQL before execution.
    Catches syntax errors, schema violations, and logical issues.
    """
    
    def __init__(self, database_connection, semantic_layer):
        self.db = database_connection
        self.semantic_layer = semantic_layer
    
    def validate(self, sql: str, selected_schema: List[Table]) -> ValidationResult:
        """
        Run multiple validation checks.
        """
        
        errors = []
        warnings = []
        
        # Check 1: SQL Syntax
        syntax_ok, syntax_errors = self._validate_syntax(sql)
        if not syntax_ok:
            errors.extend(syntax_errors)
        
        # Check 2: Schema Compliance
        schema_ok, schema_issues = self._validate_schema_usage(sql, selected_schema)
        if not schema_ok:
            errors.extend(schema_issues)
        
        # Check 3: Logical Issues
        logic_ok, logic_issues = self._validate_logic(sql)
        if not logic_ok:
            warnings.extend(logic_issues)
        
        # Check 4: Performance Hints
        perf_hints = self._check_performance_hints(sql)
        if perf_hints:
            warnings.extend(perf_hints)
        
        return ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            can_execute=(len(errors) == 0)
        )
    
    def _validate_syntax(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Test query syntax using dry-run or EXPLAIN.
        """
        try:
            # Approach 1: Use EXPLAIN (non-destructive)
            explain_sql = f"EXPLAIN {sql}"
            self.db.execute(explain_sql)
            return True, []
        except Exception as e:
            return False, [str(e)]
    
    def _validate_schema_usage(self, sql: str, selected_schema) -> Tuple[bool, List[str]]:
        """
        Check that:
        1. All referenced tables exist in selected schema
        2. All referenced columns exist in their tables
        3. Join conditions are valid
        """
        
        errors = []
        
        # Parse SQL to extract table and column references
        from sqlparse import parse, sql as sql_obj
        
        parsed = parse(sql)[0]
        
        # Extract identifiers (table/column names)
        identifiers = self._extract_identifiers(parsed)
        
        allowed_tables = {t.id: t for t in selected_schema}
        
        for identifier in identifiers:
            if '.' in identifier:
                table_name, col_name = identifier.split('.')
                
                if table_name not in allowed_tables:
                    errors.append(f"Table '{table_name}' not in selected schema")
                else:
                    table = allowed_tables[table_name]
                    if not any(c.name == col_name for c in table.columns):
                        errors.append(
                            f"Column '{col_name}' not found in table '{table_name}'"
                        )
        
        return len(errors) == 0, errors
    
    def _validate_logic(self, sql: str) -> Tuple[bool, List[str]]:
        """
        Detect potential logical issues:
        - Missing GROUP BY when using aggregates
        - Cartesian products (joins without ON clauses)
        - Unbounded result sets
        """
        warnings = []
        
        # Check for suspicious patterns
        if 'COUNT(' in sql and 'GROUP BY' not in sql:
            warnings.append(
                "Query uses COUNT() but no GROUP BY - may return single row"
            )
        
        if 'SELECT *' in sql:
            warnings.append(
                "SELECT * used - consider specifying columns explicitly"
            )
        
        return True, warnings
    
    def _check_performance_hints(self, sql: str) -> List[str]:
        """Suggest performance improvements"""
        hints = []
        
        if 'LIKE' in sql and '%' in sql:
            hints.append(
                "Query uses LIKE with leading wildcard - consider full-text search"
            )
        
        if 'OR' in sql and len(sql.split('OR')) > 5:
            hints.append(
                "Many OR conditions detected - consider IN clause or JOIN"
            )
        
        return hints
    
    def _extract_identifiers(self, parsed_sql) -> List[str]:
        """Extract all table.column references from parsed SQL"""
        identifiers = []
        
        def visit(token):
            if hasattr(token, 'tokens'):
                for t in token.tokens:
                    visit(t)
            elif isinstance(token, sqlparse.sql.Identifier):
                identifiers.append(str(token).strip())
        
        visit(parsed_sql)
        return identifiers
```

**Output**: Validation result with errors, warnings, and execution feasibility.

---

### 2.7 Execution Engine

**Purpose**: Execute validated SQL and return results safely.

**Implementation Approach**:

```python
class ExecutionEngine:
    """
    Safely executes SQL and handles errors.
    """
    
    def __init__(self, database_connection, timeout_seconds=30):
        self.db = database_connection
        self.timeout = timeout_seconds
    
    def execute(self, sql: str) -> ExecutionResult:
        """
        Execute SQL with timeout and error handling.
        """
        
        try:
            # Execute with timeout
            results = self.db.execute(
                sql,
                timeout=self.timeout
            )
            
            # Convert to safe format
            formatted_results = self._format_results(results)
            
            return ExecutionResult(
                success=True,
                data=formatted_results,
                rows_affected=len(results),
                execution_time_ms=results.execution_time,
                errors=[]
            )
        
        except TimeoutError:
            return ExecutionResult(
                success=False,
                error="Query execution exceeded timeout",
                suggestion="Query may be too expensive. Consider filtering or limiting results."
            )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                suggestion=self._suggest_fix(str(e), sql)
            )
    
    def _format_results(self, raw_results):
        """Format database results for presentation"""
        return {
            "columns": [col.name for col in raw_results.description],
            "rows": [dict(zip([col.name for col in raw_results.description], row)) 
                     for row in raw_results.fetchall()],
            "summary": f"Returned {len(raw_results)} rows"
        }
    
    def _suggest_fix(self, error_message: str, sql: str) -> str:
        """Suggest corrections based on error type"""
        if "column does not exist" in error_message.lower():
            return "Check column names in schema - typo in column reference?"
        elif "syntax error" in error_message.lower():
            return "Review SQL syntax - dialect-specific issue?"
        else:
            return "Try breaking query into smaller steps"
```

**Output**: Query results or error information.

---

### 2.8 Correction Agent (Iterative Refinement)

**Purpose**: Automatically attempt to fix errors and learn from failures.

**Implementation Approach**:

```python
class CorrectionAgent:
    """
    Detects execution failures and attempts automatic correction.
    Feeds failures to active learning loop.
    """
    
    def __init__(self, llm, semantic_layer, feedback_db):
        self.llm = llm
        self.semantic_layer = semantic_layer
        self.feedback_db = feedback_db
    
    def attempt_correction(
        self,
        original_sql: str,
        error_message: str,
        user_query: str,
        validation_result: ValidationResult
    ) -> CorrectionResult:
        """
        Try to fix SQL based on error.
        """
        
        # Categorize error
        error_category = self._categorize_error(error_message)
        
        if error_category == "COLUMN_NOT_FOUND":
            corrected_sql = self._fix_column_reference(original_sql, error_message)
        
        elif error_category == "TABLE_NOT_FOUND":
            corrected_sql = self._fix_table_reference(original_sql, error_message)
        
        elif error_category == "SYNTAX_ERROR":
            corrected_sql = self._fix_syntax(original_sql, error_message)
        
        else:
            # For unknown errors, ask LLM
            corrected_sql = self._ask_llm_to_fix(
                original_sql, 
                error_message, 
                user_query
            )
        
        if corrected_sql:
            return CorrectionResult(
                corrected_sql=corrected_sql,
                correction_type=error_category,
                confidence=0.7
            )
        else:
            # Log for active learning
            self.feedback_db.log_failure(
                user_query=user_query,
                generated_sql=original_sql,
                error=error_message,
                error_category=error_category
            )
            
            return CorrectionResult(
                success=False,
                message="Could not auto-correct. Logged for review."
            )
    
    def _ask_llm_to_fix(self, original_sql: str, error: str, user_query: str):
        """Use LLM to suggest fix"""
        
        prompt = f"""
The following SQL generated an error. Please fix it.

User Question: {user_query}

Original SQL:
{original_sql}

Error Message:
{error}

Provide only the corrected SQL query.
"""
        
        return self.llm.generate(prompt)
    
    def _categorize_error(self, error_message: str) -> str:
        """Map error to category"""
        error_lower = error_message.lower()
        
        if "column" in error_lower and "does not exist" in error_lower:
            return "COLUMN_NOT_FOUND"
        elif "table" in error_lower and "does not exist" in error_lower:
            return "TABLE_NOT_FOUND"
        elif "syntax" in error_lower:
            return "SYNTAX_ERROR"
        else:
            return "UNKNOWN"
```

**Output**: Corrected SQL or failure logged for active learning.

---

## 3. Data Stores & Indices

### 3.1 Vector Database (Schema & Entity Embeddings)

**Purpose**: Fast semantic search for tables and entity values.

**Technology**: FAISS, ChromaDB, or Pinecone

**Data Structure**:

```python
# Table Embeddings Index
table_embeddings = {
    "table_id": "t_projects",
    "table_name": "projects",
    "table_description": "All company projects with budgets and status",
    "embedding": [0.234, 0.445, ...],  # 1536-dim for OpenAI embeddings
    "metadata": {
        "num_columns": 12,
        "row_count": 5000,
        "last_refreshed": "2026-01-28"
    }
}

# Entity Value Embeddings Index
entity_embeddings = {
    "entity_id": "ent_proj_001",
    "table_id": "t_projects",
    "column": "project_name",
    "canonical_value": "Phoenix Implementation Phase 1",
    "aliases": ["Project Phoenix", "Phoenix Phase 1"],
    "embedding": [0.123, 0.456, ...],
    "metadata": {
        "frequency": 145,  # Number of times referenced
        "last_updated": "2026-01-15"
    }
}
```

### 3.2 Few-Shot Example Database

**Purpose**: Store successful query patterns for in-context learning.

**Schema**:

```python
class FewShotExample:
    id: str
    user_question: str
    sql: str
    question_embedding: List[float]
    difficulty: str  # easy, medium, hard
    sql_type: str  # SELECT, JOIN, AGGREGATE, etc.
    tables_involved: List[str]
    execution_success: bool
    execution_time_ms: float
    created_at: datetime
    feedback_score: float  # User feedback: -1, 0, +1
```

### 3.3 Feedback & Error Log

**Purpose**: Track failed queries for active learning.

**Schema**:

```python
class FailureLog:
    id: str
    timestamp: datetime
    user_query: str
    generated_sql: str
    error_message: str
    error_category: str  # COLUMN_NOT_FOUND, SYNTAX_ERROR, etc.
    human_correction: Optional[str]  # If corrected by human
    root_cause: Optional[str]  # Root cause identified
    patch_applied: bool
    status: str  # pending, reviewed, fixed
```

---

## 4. Orchestration & Workflow

### 4.1 Complete Query Processing Pipeline

```python
class TextToSQLOrchestrator:
    """
    Orchestrates the complete pipeline from natural language to results.
    """
    
    def __init__(
        self,
        semantic_layer: SemanticLayer,
        schema_selector: SchemaSelectorAgent,
        entity_resolver: EntityResolverAgent,
        decomposer: DecomposerAgent,
        sql_generator: SQLGeneratorAgent,
        validator: ValidatorAgent,
        executor: ExecutionEngine,
        corrector: CorrectionAgent,
        logger: Logger
    ):
        self.semantic_layer = semantic_layer
        self.schema_selector = schema_selector
        self.entity_resolver = entity_resolver
        self.decomposer = decomposer
        self.sql_generator = sql_generator
        self.validator = validator
        self.executor = executor
        self.corrector = corrector
        self.logger = logger
    
    def process_query(self, user_query: str) -> Response:
        """
        Complete end-to-end pipeline.
        """
        
        self.logger.info(f"Processing query: {user_query}")
        
        # Phase 1: Schema Selection
        selected_schema = self.schema_selector.select_schema(user_query)
        self.logger.info(f"Selected {len(selected_schema)} tables")
        
        # Phase 2: Entity Resolution
        entity_resolutions = self.entity_resolver.resolve_entities(
            user_query, 
            selected_schema
        )
        self.logger.info(f"Resolved {len(entity_resolutions)} entities")
        
        # Phase 3: Query Decomposition
        query_plan = self.decomposer.decompose(user_query, self.semantic_layer)
        self.logger.info(f"Decomposed into {len(query_plan.steps)} steps")
        
        # Phase 4: SQL Generation
        generated_sql = self.sql_generator.generate_sql(
            query_plan=query_plan,
            selected_schema=selected_schema,
            entity_resolutions=entity_resolutions,
            user_query=user_query
        )
        self.logger.info(f"Generated SQL: {generated_sql}")
        
        # Phase 5: Validation
        validation = self.validator.validate(generated_sql, selected_schema)
        self.logger.info(f"Validation result: {validation.is_valid}")
        
        if not validation.is_valid:
            self.logger.error(f"Validation errors: {validation.errors}")
            return Response(
                success=False,
                error="SQL validation failed",
                details=validation.errors
            )
        
        # Phase 6: Execution
        exec_result = self.executor.execute(generated_sql)
        self.logger.info(f"Execution success: {exec_result.success}")
        
        # Phase 7: Error Handling & Correction
        if not exec_result.success:
            correction = self.corrector.attempt_correction(
                original_sql=generated_sql,
                error_message=exec_result.error,
                user_query=user_query,
                validation_result=validation
            )
            
            if correction.success:
                # Retry with corrected SQL
                exec_result = self.executor.execute(correction.corrected_sql)
                self.logger.info(f"Correction successful")
            else:
                self.logger.warning("Correction failed - logged for review")
        
        # Phase 8: Response Formatting
        if exec_result.success:
            response = Response(
                success=True,
                data=exec_result.data,
                sql=generated_sql,
                execution_time_ms=exec_result.execution_time_ms,
                metadata={
                    "tables_used": [t.id for t in selected_schema],
                    "entities_resolved": len(entity_resolutions),
                    "query_plan_steps": len(query_plan.steps)
                }
            )
        else:
            response = Response(
                success=False,
                error=exec_result.error,
                suggestion=exec_result.suggestion
            )
        
        return response
```

### 4.2 Workflow Diagram (LlamaIndex Pattern)

```
User Query
    ↓
[Query Router] → Determine if table selection needed
    ↓
    ├─→ [NLSQLQueryEngine] (simple queries, pre-selected tables)
    │
    └─→ [Dynamic Table Selector] + [NLSQLRetriever] (complex queries)
           ↓
        [Semantic Search on Table Names/Descriptions]
           ↓
        [Retrieve Top-K Tables + Join Paths]
           ↓
        [NLSQLQueryEngine] with filtered schema
           ↓
        [Execute Query]
           ↓
        [Return Results]
```

---

## 5. Evaluation Framework

### 5.1 Benchmark Testing Pipeline

```python
class BenchmarkEvaluator:
    """
    Evaluates system accuracy against gold standard dataset.
    """
    
    def __init__(self, gold_test_file: str, database_connection):
        self.gold_tests = self._load_gold_tests(gold_test_file)
        self.db = database_connection
    
    def evaluate_all(self, orchestrator: TextToSQLOrchestrator) -> EvaluationReport:
        """
        Run all gold tests and compute accuracy metrics.
        """
        
        results = []
        
        for i, test in enumerate(self.gold_tests):
            print(f"Running test {i+1}/{len(self.gold_tests)}")
            
            # Generate SQL
            response = orchestrator.process_query(test.user_question)
            
            # Evaluate
            evaluation = self._evaluate_single(
                test=test,
                generated_sql=response.sql if response.success else None,
                generated_data=response.data if response.success else None
            )
            
            results.append(evaluation)
        
        # Aggregate metrics
        report = self._aggregate_results(results)
        
        return report
    
    def _evaluate_single(self, test, generated_sql, generated_data):
        """
        Evaluate one test using multiple metrics.
        """
        
        evaluation = EvaluationMetrics()
        
        # Metric 1: Execution Success (can SQL run?)
        evaluation.execution_success = (
            generated_sql is not None and 
            self._can_execute(generated_sql)
        )
        
        if not evaluation.execution_success:
            return evaluation
        
        # Metric 2: Exact Match (syntax identical?)
        evaluation.exact_match = (
            self._normalize_sql(generated_sql) == 
            self._normalize_sql(test.gold_sql)
        )
        
        # Metric 3: Data Match (results identical?)
        gold_data = self._execute_query(test.gold_sql)
        evaluation.data_match = (
            self._compare_results(generated_data, gold_data) == 100.0
        )
        
        # Metric 4: Semantic Equivalence (logically same?)
        evaluation.semantic_equivalent = (
            self._check_semantic_equivalence(generated_sql, test.gold_sql)
        )
        
        # Metric 5: Execution Efficiency (not too slow?)
        evaluation.execution_time_ok = (
            evaluation.execution_time_ms < test.acceptable_time_ms
        )
        
        return evaluation
    
    def _aggregate_results(self, results: List[EvaluationMetrics]) -> EvaluationReport:
        """Compute summary statistics"""
        
        total = len(results)
        
        execution_success_rate = sum(
            1 for r in results if r.execution_success
        ) / total * 100
        
        exact_match_rate = sum(
            1 for r in results if r.exact_match
        ) / total * 100
        
        data_match_rate = sum(
            1 for r in results if r.data_match
        ) / total * 100
        
        semantic_equiv_rate = sum(
            1 for r in results if r.semantic_equivalent
        ) / total * 100
        
        return EvaluationReport(
            total_tests=total,
            execution_success_rate=execution_success_rate,
            exact_match_rate=exact_match_rate,
            data_match_rate=data_match_rate,
            semantic_equivalence_rate=semantic_equiv_rate,
            by_difficulty={
                "easy": self._filter_and_aggregate(results, "easy"),
                "medium": self._filter_and_aggregate(results, "medium"),
                "hard": self._filter_and_aggregate(results, "hard"),
            }
        )
```

### 5.2 Gold Test Dataset Format

```json
[
  {
    "id": 1,
    "user_question": "What is the average project budget by department?",
    "gold_sql": "SELECT d.department_name, AVG(p.amount) as avg_budget FROM departments d LEFT JOIN projects p ON d.id = p.department_id GROUP BY d.id, d.department_name ORDER BY avg_budget DESC",
    "expected_result": [
      {"department_name": "Engineering", "avg_budget": 150000.00},
      {"department_name": "Sales", "avg_budget": 80000.00}
    ],
    "difficulty": "medium",
    "sql_type": "JOIN, AGGREGATE, GROUP_BY",
    "acceptable_time_ms": 500
  }
]
```

---

## 6. Active Learning Loop

### 6.1 Feedback Processing

```python
class ActiveLearningLoop:
    """
    Continuously improves system through feedback.
    """
    
    def __init__(self, failure_log_db, few_shot_db, feedback_db):
        self.failure_log = failure_log_db
        self.few_shot_db = few_shot_db
        self.feedback_db = feedback_db
    
    def weekly_review(self):
        """
        Weekly task: review failures, add corrections to few-shot DB.
        """
        
        # Get failed queries from past week
        failures = self.failure_log.get_recent_failures(days=7, limit=10)
        
        print(f"Reviewing {len(failures)} failures...")
        
        for failure in failures:
            if failure.human_correction:
                # Human has provided correction
                self._add_to_few_shots(
                    user_question=failure.user_query,
                    correct_sql=failure.human_correction,
                    difficulty=self._estimate_difficulty(failure),
                    feedback_score=1  # Positive feedback
                )
                
                # Mark as fixed
                failure.status = "fixed"
                self.failure_log.update(failure)
    
    def _add_to_few_shots(self, user_question, correct_sql, difficulty, feedback_score):
        """Add corrected example to few-shot database"""
        
        example = FewShotExample(
            id=str(uuid.uuid4()),
            user_question=user_question,
            sql=correct_sql,
            question_embedding=embed(user_question),
            difficulty=difficulty,
            sql_type=self._extract_sql_type(correct_sql),
            tables_involved=self._extract_tables(correct_sql),
            execution_success=True,
            feedback_score=feedback_score,
            created_at=datetime.now()
        )
        
        self.few_shot_db.insert(example)
        print(f"Added example: {user_question}")
    
    def _estimate_difficulty(self, failure: FailureLog) -> str:
        """Estimate query difficulty based on error type"""
        if failure.error_category == "SYNTAX_ERROR":
            return "hard"
        elif failure.error_category == "COLUMN_NOT_FOUND":
            return "medium"
        else:
            return "medium"
```

---

## 7. Monitoring & Observability

### 7.1 Logging Strategy

```python
class SystemLogger:
    """
    Comprehensive logging for debugging and monitoring.
    """
    
    def log_query_processing(
        self,
        user_query: str,
        pipeline_stage: str,
        data: dict,
        duration_ms: float
    ):
        """
        Log each stage of processing for troubleshooting.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_query": user_query,
            "stage": pipeline_stage,
            "data": data,
            "duration_ms": duration_ms
        }
        
        # Write to structured log
        self.logger.info(json.dumps(log_entry))
```

### 7.2 Metrics Collection

```python
# Key metrics to track:
metrics = {
    "daily_queries_processed": Counter,
    "accuracy_by_difficulty": Gauge,
    "average_execution_time_ms": Histogram,
    "error_rate_by_type": Counter,
    "schema_selector_accuracy": Gauge,  # % of queries where all needed tables selected
    "entity_resolver_accuracy": Gauge,  # % of entity mappings correct
    "llm_cost_per_query": Gauge,
}
```

---

## 8. Deployment Architecture

### 8.1 System Components & Tech Stack

```
┌─────────────────────────────────────────┐
│         User Interface Layer             │
│  (Web App, Chat Interface, API Endpoint) │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     API Server (FastAPI / Flask)        │
│  - Request routing                      │
│  - Response formatting                  │
│  - Authentication                       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│          Text-to-SQL Orchestrator                   │
│  (Main processing pipeline - Python)                │
└──────────────┬──────────────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
┌───▼──┐   ┌──▼──┐  ┌───▼──┐  ┌───▼──┐
│Schema│   │Entity│  │Query │  │SQL   │
│Select│   │Resol│  │Decomp│  │Gener │
└──┬───┘   └──┬───┘  └───┬──┘  └──┬───┘
   │          │          │        │
   └──────────┼──────────┼────────┘
              │          │
         ┌────▼──────────▼────┐
         │   LLM Provider      │
         │  (OpenAI, Anthropic)│
         └─────────────────────┘

    Vector DB (FAISS/Chroma)
    Few-Shot Examples DB
    Failure Log DB
    Semantic Layer Store (JSON/SQL)
    
    Production Database
    (PostgreSQL/Snowflake/BigQuery)
```

### 8.2 Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Expose API port
EXPOSE 8000

# Run orchestrator
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 9. Configuration Management

### 9.1 Configuration File Structure

```yaml
# config.yaml

system:
  mode: "production"  # development, staging, production
  log_level: "INFO"

llm:
  provider: "openai"  # openai, anthropic
  model: "gpt-4-turbo"
  temperature: 0.1
  max_tokens: 2000
  timeout_seconds: 30

vector_db:
  type: "faiss"  # faiss, chroma, pinecone
  embedding_model: "text-embedding-3-large"
  index_path: "./data/vectors/schema_index.faiss"

database:
  type: "postgresql"
  host: "${DB_HOST}"
  port: 5432
  database: "${DB_NAME}"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"
  timeout_seconds: 30

agents:
  schema_selector:
    top_k: 5
    include_join_neighbors: true
  
  entity_resolver:
    similarity_threshold: 0.85
    enable_fuzzy_matching: true
  
  sql_generator:
    dialect: "postgresql"
    few_shot_retrieval_k: 3

validator:
  enable_syntax_check: true
  enable_schema_validation: true
  enable_logic_check: true

corrector:
  max_retry_attempts: 2
  enable_auto_correction: true

evaluation:
  gold_test_file: "./data/gold_tests.json"
  run_weekly_benchmark: true
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
1. **Setup infrastructure** - Database connections, vector DB, API server
2. **Build semantic layer** - Data dictionary, business metrics, entity mappings
3. **Implement schema selector** - FAISS indexing, table retrieval
4. **Create evaluation framework** - Gold test dataset (50 questions), benchmark_tests.py

### Phase 2: Core Agents (Weeks 5-8)
5. **Entity resolver** - Fuzzy matching + vector search
6. **SQL generator** - LLM integration with few-shot examples
7. **Validator** - Syntax + schema + logic checks
8. **Execution engine** - Safe query execution with timeouts

### Phase 3: Advanced Features (Weeks 9-12)
9. **Decomposer agent** - Query plan generation
10. **Correction agent** - Error handling + auto-fix
11. **Active learning loop** - Feedback processing, few-shot updates
12. **Monitoring** - Metrics collection, logging, dashboards

### Phase 4: Optimization (Weeks 13-16)
13. **Performance tuning** - Query optimization, caching
14. **Advanced RAG** - Cross-domain generalization
15. **Fine-tuning** - Domain-specific model training
16. **Production hardening** - Security, scalability, reliability

---

## 11. Success Metrics

| Metric | Target | Phase |
|--------|--------|-------|
| Execution Success Rate | >95% | P2-P3 |
| Data Match Rate | >90% | P2-P3 |
| Exact SQL Match | >70% | P3-P4 |
| Average Query Time | <2s | P4 |
| Cost per Query | <$0.05 | P4 |
| System Availability | 99.9% | P4 |

---

## 12. References & Further Reading

- **LangChain Documentation**: https://python.langchain.com/
- **LlamaIndex Documentation**: https://docs.llamaindex.ai/
- **MAC-SQL Research**: Multi-agent collaborative framework
- **BIRD Benchmark**: https://bird-bench.github.io
- **Spider Benchmark**: https://yale-lily.github.io/spider
- **Semantic Layer Patterns**: dbt, LookML, Atlan

---

**Document Version**: 1.0  
**Last Updated**: January 28, 2026  
**Status**: Ready for Implementation
