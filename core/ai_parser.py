import re, json, ollama, difflib, os
from config import USER_CONFIG_DIR
from utils.fs_utils import ensure_file_has_content


DEFAULT_SKIP_TERMS_TEXT = """->
Extraction
Transfer
Withdrawal
"""

DEFAULT_PROMPT_TEMPLATE = """<role>You are a literal data extraction pipe. ZERO reasoning. ZERO spelling correction.</role>

<mapping_table>
- 'cash'      -> 'Cash ({default_currency})'
- 'debit'     -> 'Debit Card ({default_currency})'
- 'credit'    -> If currency is USD: 'Credit Card (USD)'; if JPY: 'Credit Card (JPY)'; etc; else: 'Credit Card ({default_currency})'
- 'bank'      -> If currency is EUR: 'Bank Transfer (EUR)'; if JPY: 'Bank Transfer (JPY)'; etc; else: 'Bank Transfer ({default_currency})'
</mapping_table>

<rules>
1. EXTRACTION ORDER: [Vendor] [Amount] [Currency (optional)] [Hint] [Description]
    - You are provided with a FIXED CATEGORY (for your JSON) and a LINE (for extraction).
    - VENDOR: The first entity/name in the LINE.
    - AMOUNT: The numerical value.
    - HINT: Follow <mapping_table>.
    - DESCRIPTION: Everything else, except HINT, and everything AFTER the HINT.
2. DESCRIPTION: Verbatim capture EVERYTHING after the HINT and ALL bracketed text.
3. JSON ONLY: Output exactly one JSON object. No preamble.
</rules>

<examples>
Input:
FIXED CATEGORY: Utilities
LINE: Water Service 34.97 debit

Output:
{"amount": 34.97, "currency": "{default_currency}", "category": "Utilities", "vendor": "Water Service", "payment_method": "Debit Card ({default_currency})", "description": ""}

Input:
FIXED CATEGORY: Transport
LINE: Taxi 72.73 debit from Airport to Hotel

Output:
{"amount": 72.73, "currency": "{default_currency}", "category": "Transport", "vendor": "Uber", "payment_method": "Debit Card ({default_currency})", "description": "from Airport to Hotel"}

Input:
FIXED CATEGORY: Utilities
LINE: PowerCo 73.79 debit

Output:
{"amount": 73.79, "currency": "{default_currency}", "category": "Utilities", "vendor": "PowerCo", "payment_method": "Debit Card ({default_currency})", "description": ""}

Input:
FIXED CATEGORY: Groceries
LINE: Supermarket 100.00 cash Monthly purchase

Output:
{"amount": 100.0, "currency": "{default_currency}", "category": "Groceries", "vendor": "Supermarket", "payment_method": "Cash ({default_currency})", "description": "Monthly purchase"}

Input:
FIXED CATEGORY: Entertainment
LINE: Streaming Service 14.99 USD bank HD Plan

Output:
{"amount": 14.99, "currency": "USD", "category": "Entertainment", "vendor": "Streaming Service", "payment_method": "Bank Transfer (USD)", "description": "HD Plan"}

Input:
FIXED CATEGORY: Housing
LINE: Hotel 1500.75 USD (1316.45 FX 1.14 -including tax) credit

Output:
{"amount": 1500.75, "currency": "USD", "category": "Housing", "vendor": "Hotel", "payment_method": "Credit Card (USD)", "description": "(1316.45 FX 1.14 -including tax)"}

Input:
FIXED CATEGORY: Dining Out
LINE: Burger Joint 33.90 debit With friends

Output:
{"amount": 33.90, "currency": "{default_currency}", "category": "Dining Out", "vendor": "Burger Joint", "payment_method": "Debit Card ({default_currency})", "description": "With friends"}

Input:
FIXED CATEGORY: Health
LINE: Pharmacy 8.99 debit Nasal spray

Output:
{"amount": 8.99, "currency": "{default_currency}", "category": "Health", "vendor": "Pharmacy", "payment_method": "Debit Card ({default_currency})", "description": "Nasal spray"}

Input:
FIXED CATEGORY: Shopping
LINE: Clothing Store 9000 JPY debit Birthday present

Output:
{"amount": 9000, "currency": "JPY", "category": "Shopping", "vendor": "Clothing Store", "payment_method": "Debit Card (JPY)", "description": "Birthday present"}

Input:
FIXED CATEGORY: Dining Out
LINE: Diner 1430 bank Lunch meeting

Output:
{"amount": 1430, "currency": "{default_currency}", "category": "Dining Out", "vendor": "Diner", "payment_method": "Bank Transfer ({default_currency})", "description": "Lunch meeting"}
</examples>

<verification_protocol>
Before finalizing the JSON:
1. QUANTITY CHECK: Is the 'Amount' actually a price? (e.g., Is it 40.00 or is it part of a vendor name like 'Castellana 200'?) 
2. CURRENCY VALIDITY: If the Amount is not followed by a currency code (e.g., USD, JPY, ARS) does the currency match {default_currency}?
3. REMAINDER CHECK: Did the input line have words after the HINT? If yes, and your 'description' is empty, you have failed. Re-extract and include all words.
</verification_protocol>"""


def chunk_file_by_day(filepath, skip_terms):
    """
    Identifies 'DD/MM (description):' or 'DD/MM:' and
    groups the lines following it until the next date.
    Skips days that contain no valid transactions after filtering.
    """
    with open(filepath, 'r', encoding="utf-8") as f:
        content = f.read()

    pattern = r'(\d{2}/\d{2}(?:\s\(.*?\))?:)'

    parts = re.split(pattern, content)

    days = []

    for i in range(1, len(parts), 2):
        header = parts[i]
        raw_transactions = parts[i + 1].strip().split('\n')
        # Only keep lines that don't start with unwanted terms
        filtered_lines = [
            line.strip() for line in raw_transactions
            if line.strip() and not line.strip().startswith(skip_terms)
        ]
        if filtered_lines:
            transactions = "\n".join(filtered_lines)
            days.append({
                "header": header,
                "data": transactions
            })
        else:
            pass

    return days

def get_row_prompt(default_currency):
    """
    Reads the AI prompt template from the user's config folder.
    Auto-heals the file if it is empty.
    """
    prompt_file_path = os.path.join(USER_CONFIG_DIR, "ai_prompt_template.txt")

    ensure_file_has_content(prompt_file_path, DEFAULT_PROMPT_TEMPLATE, allow_empty=False)

    with open(prompt_file_path, "r", encoding="utf-8-sig") as f:
        user_template = f.read()

    final_prompt = user_template.replace("{default_currency}", default_currency)

    return final_prompt

def get_skip_terms():
    """Reads skip terms from the config folder or creates the default file."""
    skip_file_path = os.path.join(USER_CONFIG_DIR, "ai_skip_terms.txt")

    ensure_file_has_content(skip_file_path, DEFAULT_SKIP_TERMS_TEXT, allow_empty=True)

    with open(skip_file_path, "r", encoding="utf-8-sig") as f:
        terms = [line.strip() for line in f.readlines() if line.strip()]

    return tuple(terms)

def get_structured_data(combined_text, categories, system_prompt, cancel_event=None, progress_callback=None):
    """
    Invokes a local LLM (e.g. Mistral) to convert
    text lines into JSON objects.
    Returns a list of objects which are meant
    to be validated and injected into a SQL db.
    """
    # 0. Check Ollama is running
    try:
        ollama.list()
    except Exception:
        raise ConnectionError("Cannot connect to Ollama. Is the local AI engine running?")
    # 1. Clean lines and count
    lines = [l.strip() for l in combined_text.split('\n') if l.strip()]
    total_lines = len(lines)
    total_tx = sum(1 for l in lines if not (re.match(r'(\d{2}/\d{2})', l) and l.endswith(':')))

    # 2. Initialize date and prepare categories
    current_date = "00/00"

    sorted_categories = sorted([str(c.name) for c in categories], key=len, reverse=True)

    # 3. Define the Schema (Forces the LLM to provide these keys)
    json_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "vendor": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string"},
            "payment_method": {"type": "string"},
            "description": {"type": "string"}
        },
        "required": ["category", "vendor", "amount", "currency", "payment_method", "description"]
    }

    final_results = []
    current_tx = 0

    for idx, line in enumerate(lines):
        # 0. Check for cancellation
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Parsing cancelled by user.")

        # 1. Update the date if the line is a header
        date_match = re.match(r'(\d{2}/\d{2})', line)
        if date_match and line.endswith(':'):
            current_date = date_match.group(1)
            # Initiate progress reporting
            if progress_callback:
                progress_callback(idx + 1, total_lines, current_tx, total_tx)
            continue

        # 2. Report back the progress
        current_tx += 1
        if progress_callback:
            progress_callback(idx + 1, total_lines, current_tx, total_tx)

        # 3. Extract the category
        expected_cat = None
        line_to_process = line
        first_word = line.split()[0]

        # Try Exact Start Match
        for cat in sorted_categories:
            if line.lower().startswith(cat.lower()):
                expected_cat = cat
                line_to_process = line[len(cat):].strip()
                break

        # Fuzzy Fallback (e.g., "Internet" matching "Internet & Mobile")
        if not expected_cat:
            matches = difflib.get_close_matches(first_word, sorted_categories, n=1, cutoff=0.3)
            if matches:
                expected_cat = matches[0]
                # Strip the word that triggered the fuzzy match (usually the first word)
                line_to_process = line[len(first_word):].strip()
                # print(f"Fuzzy Match: '{first_word}' -> '{expected_cat}'. Processing: '{line_to_process}'")
            else:
                expected_cat = ""
                line_to_process = line

        # 4. LLM loop
        try:
            user_content = f"FIXED CATEGORY: {expected_cat}\nLINE: {line_to_process}"

            response = ollama.chat(
                model='mistral:7b',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content}
                ],
                format=json_schema,
                options={'temperature': 0.0}
            )

            # Parse and inject the date
            item = json.loads(response['message']['content'])

            # Force the category and inject current date
            item['category'] = expected_cat
            item['date'] = current_date
            item['line'] = line
            final_results.append(item)
            # print(f"LLM sees: {line_to_process}")
            # print(f"✅ {line}")
            # print(f">>> [{item['date']}] {item['vendor']}: {item['amount']} {item['currency']} [{item['category']}] [{item['payment_method']}] [{item['description']}]\n")

        except json.JSONDecodeError as e:
            print(f"Skipping line due to JSON formatting error: {e}")
            continue
        except Exception as e:
            raise ConnectionError(f"Ollama execution failed: {str(e)}")

    return final_results


