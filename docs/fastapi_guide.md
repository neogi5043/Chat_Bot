> [!WARNING]
> **DEPRECATED**: The `server.py` implementation described here is currently deprecated and not maintained. The primary interface is the CLI (`app.py`).

# How to Create a FastAPI Endpoint for the Chatbot

This guide demonstrates how to expose the Demand Management Chatbot as a REST API using FastAPI.

## Prerequisites

Install FastAPI and an ASGI server:
```bash
pip install fastapi uvicorn
```

## Implementation

Create a file named `server.py` in the root directory:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import pandas as pd
from typing import Optional, Dict, Any
import sys
import os

# Ensure root is in path to import src modules correctly
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import the core pipeline
from src.pipeline.chatbot import pipeline

app = FastAPI(title="Demand Management Bot API")

# Request Model
class ChatRequest(BaseModel):
    query: str
    user_email: Optional[str] = None

# Response Model
class ChatResponse(BaseModel):
    sql: Optional[str]
    data: Optional[Any] # Can be list of dicts or message string
    insights: Optional[str]
    type: str # 'sql', 'general', 'error'

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Process a natural language query and return SQL + Data + Insights.
    """
    try:
        # Call the existing pipeline
        # pipeline returns: (sql_query, df, insights, query_type)
        sql, df, insights, q_type = pipeline(request.query, verbose=False)
        
        # Serialize DataFrame to list of dicts (JSON)
        data_json = None
        if df is not None and not df.empty:
            # IMPORTANT: Handle NaN/Inf values which cause Pydantic serialization errors
            # Replace NaN with None (which becomes null in JSON)
            df_clean = df.where(pd.notnull(df), None)
            data_json = df_clean.to_dict(orient="records")
            
        elif isinstance(df, pd.DataFrame) and df.empty:
            data_json = []

        return ChatResponse(
            sql=sql,
            data=data_json,
            insights=insights,
            type=q_type
        )

    except Exception as e:
        # Log the error internally here if needed
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Running the API

1.  Start the server:
    ```bash
    python server.py
    ```

2.  Open the Swagger UI documentation:
    [http://localhost:8000/docs](http://localhost:8000/docs)

3.  Test with a request:
    ```json
    {
      "query": "Show me open demands"
    }
    ```
