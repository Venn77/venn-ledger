import sys
from pprint import pprint
from core.ai_sql_parser import generate_and_execute_trend_query
from utils.ollama_manager import start_ollama_daemon, stop_ollama_daemon


def main():
    """
    Interactive CLI loop to test the Text-to-SQL Mistral pipeline.
    Ensures the Ollama daemon is running before starting.
    """
    print("Initializing VennLedger AI Engine...")
    start_ollama_daemon()

    print("\n" + "=" * 50)
    print(" VennLedger Text-to-SQL CLI Tester")
    print(" Type 'exit' or 'quit' to terminate.")
    print("=" * 50 + "\n")

    try:
        while True:
            user_input = input("Ask a question about your finances:\n> ").strip()

            if user_input.lower() in ('exit', 'quit'):
                print("Shutting down AI Engine...")
                break
            if not user_input:
                continue

            print("\n[Thinking...]")
            result = generate_and_execute_trend_query(user_input)

            if result.get("status") == "success":
                sql = result.get("generated_sql")
                if isinstance(sql, str):
                    print(f"\n[Generated SQL]:\n{sql}")

                print("\n[Data Results]:")
                data = result.get("data")
                if data:
                    pprint(data, indent=2)
                else:
                    print("[] (Query executed successfully, but returned no records.)")

            else:
                error_msg = result.get("error_message")
                if isinstance(error_msg, str):
                    print(f"\n[Error]: {error_msg}")
                else:
                    print("\n[Error]: An unknown error occurred.")

                attempted_sql = result.get("generated_sql")
                if isinstance(attempted_sql, str):
                    print(f"[Attempted SQL]:\n{attempted_sql}")

            print("\n" + "-" * 50 + "\n")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Shutting down...")
    finally:
        stop_ollama_daemon()
        sys.exit(0)


if __name__ == "__main__":
    main()