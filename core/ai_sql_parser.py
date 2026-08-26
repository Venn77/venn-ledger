import re, json
import ollama
from core.sql_prompts import DEFAULT_SQL_PROMPT_TEMPLATE
from database.ro_executor import execute_ro_query


def clean_sql_output(raw_response: str) -> str:
    """
    Strips markdown code blocks and preamble from LLM output.
    Ensures we have a raw, executable SQL string.
    """
    cleaned = re.sub(r"```sql|```", "", raw_response, flags=re.IGNORECASE)

    cleaned = cleaned.strip()
    if not cleaned.endswith(";"):
        cleaned += ";"

    return cleaned


def generate_and_execute_trend_query(user_query: str) -> dict:
    """
    Takes a natural language query, uses Mistral 7B to generate a JSON-wrapped
    SQLite string, and safely executes it against the read-only database.
    """
    try:
        ollama.list()
    except Exception:
        raise ConnectionError("Cannot connect to Ollama. Is the local AI engine running?")

    safe_sql = None

    json_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The raw, valid SQLite query."
            }
        },
        "required": ["query"]
    }

    try:
        user_content = f"Input: {user_query}"
        response = ollama.chat(
            model="mistral:7b",
            messages=[
                {"role": "system", "content": DEFAULT_SQL_PROMPT_TEMPLATE},
                {"role": "user", "content": user_content}
            ],
            format=json_schema,
            options={"temperature": 0.0}
        )

        result_dict = json.loads(response["message"]["content"])
        safe_sql = result_dict.get("query", "").strip()

        if safe_sql and not safe_sql.endswith(";"):
            safe_sql += ";"

        results = execute_ro_query(safe_sql)

        return {
            "status": "success",
            "query": user_query,
            "generated_sql": safe_sql,
            "data": results
        }

    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error_message": f"LLM returned invalid JSON structure: {str(e)}",
            "generated_sql": None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "generated_sql": safe_sql
        }