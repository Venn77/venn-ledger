import re, json, ollama, difflib


def chunk_file_by_day(filepath):
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
            if line.strip() and not line.strip().startswith(("->",
                                                             "TC",
                                                             "Extracción",
                                                             "Transfer",
                                                             "Mp TC",
                                                             "MP TC",
                                                             "Withdrawal",
                                                             "MP:")
                                                            )
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
    """Prepares a system prompt for LLM interpretation of expense items."""
    return f"""
<role>You are a literal data extraction pipe. ZERO reasoning. ZERO spelling correction.</role>

<mapping_table>
- 'santander' -> 'Santander Debit'
- 'bizum'     -> 'Santander Bizum'
- 'mp'        -> 'Mercado Pago'
- 'cash'      -> 'Cash (EUR)'
- 'laliga'    -> 'Santander LaLiga'
- 'lacaixa'   -> 'LaCaixa IKEA'
- 'wizink'    -> 'Wizink'
- 'master'    -> 'Ciudad Master'
- 'visa'      -> 'Ciudad Visa'
- 'wise'      -> If currency is USD: 'Wise (USD)'; if JPY: 'Wise (JPY)'; else: 'Wise ({default_currency})'
- 'revolut'   -> If currency is EUR: 'Revolut (EUR)'; if JPY: 'Revolut (JPY)'; else: 'Revolut ({default_currency})'
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
FIXED CATEGORY: Water Service
LINE: Aigues Sabadell 34.97 santander

Output:
{{"amount": 34.97, "currency": "{default_currency}", "category": "Water Service", "vendor": "Aigues Sabadell", "payment_method": "Santander Debit", "description": ""}}

Input:
FIXED CATEGORY: Vacation
LINE: Uber 72.73 santander from Shibuya to Haneda

Output:
{{"amount": 72.73, "currency": "{default_currency}", "category": "Vacation", "vendor": "Uber", "payment_method": "Santander Debit", "description": "from Shibuya to Haneda"}}

Input:
FIXED CATEGORY: Incidental
LINE: Castellana 200 40.00 santander corte del jamón

Output:
{{"amount": 40.0, "currency": "{default_currency}", "category": "Incidental", "vendor": "Castellana 200", "payment_method": "Santander Debit", "description": "corte del jamón"}}
 
Input:
FIXED CATEGORY: Vacation
LINE: Saily 7.00 santander 30 days eSIM 3GB

Output:
{{"amount": 7.0, "currency": "{default_currency}", "category": "Vacation", "vendor": "Saily", "payment_method": "Santander Debit", "description": "30 days eSIM 3GB"}}

Input:
FIXED CATEGORY: Gas
LINE: Naturgy 73.79 santander

Output:
{{"amount": 73.79, "currency": "{default_currency}", "category": "Gas", "vendor": "Naturgy", "payment_method": "Santander Debit", "description": ""}}

Input:
FIXED CATEGORY: Gifts
LINE: LEVEL 1292.25 laliga Eze-Bcn f/Celes

Output:
{{"amount": 1292.25, "currency": "{default_currency}", "category": "Gifts", "vendor": "LEVEL", "payment_method": "Santander LaLiga", "description": "Eze-Bcn f/Celes"}}

Input:
FIXED CATEGORY: 420
LINE: Planta Santa 100.00 cash 18.33g (5.46 each)

Output:
{{"amount": 100.0, "currency": "{default_currency}", "category": "420", "vendor": "Planta Santa", "payment_method": "Cash ({default_currency})", "description": "18.33g (5.46 each)"}}

Input:
FIXED CATEGORY: Subscription
LINE: DistroKid 24.99 USD (21.59 TC 1.17) wise Yearly fee

Output:
{{"amount": 24.99, "currency": "USD", "category": "Subscription", "vendor": "DistroKid", "payment_method": "Wise (USD)", "description": "(21.59 TC 1.17) Yearly fee"}}

Input:
FIXED CATEGORY: Incidental
LINE: TMB 20.65 wizink T Usual f/Celes (because 10€ cashback)

Output:
{{"amount": 20.65, "currency": "{default_currency}", "category": "Incidental", "vendor": "TMB", "payment_method": "Wizink", "description": "T Usual f/Celes (because 10€ cashback)"}}

Input:
FIXED CATEGORY: Subscription
LINE: Spotify 3133.47 ARS (2.45 TC 1280 -incluye 21% IVA) mp

Output:
{{"amount": 3133.47, "currency": "ARS", "category": "Subscription", "vendor": "Spotify", "payment_method": "Mercado Pago", "description": "(2.45 TC 1280 -incluye 21% IVA)"}}

Input:
FIXED CATEGORY: Lunch
LINE: Five Guys 33.90 santander w/Celes

Output:
{{"amount": 33.90, "currency": "{default_currency}", "category": "Lunch", "vendor": "Five Guys", "payment_method": "Santander Debit", "description": "w/Celes"}}

Input:
FIXED CATEGORY: Medical
LINE: Pharmacy 8.99 santander Nasal spray

Output:
{{"amount": 8.99, "currency": "{default_currency}", "category": "Medical", "vendor": "Pharmacy", "payment_method": "Santander Debit", "description": "Nasal spray"}}

Input:
FIXED CATEGORY: Gifts
LINE: Agustina Rojas 78750.00 ARS (46.96 TC 1677) mp Birthday boots f/Agustina

Output:
{{"amount": 78750.00, "currency": "ARS", "category": "Gifts", "vendor": "Agustina Rojas", "payment_method": "Mercado Pago", "description": "(46.96 TC 1677) Birthday boots f/Agustina"}}

Input:
FIXED CATEGORY: Household Supplies
LINE: Amazon 13.99 santander iAmoy replacement brush & filters f/Deebot Slim2 vaccuum cleaner

Output:
{{"amount": 13.99, "currency": "{default_currency}", "category": "Household Supplies", "vendor": "Amazon", "payment_method": "Santander Debit", "description": "iAmoy replacement brush & filters f/Deebot Slim2 vaccuum cleaner"}}

Input:
FIXED CATEGORY: Breakfast
LINE: Denny's 1430 wise w/Celes

Output:
{{"amount": 1430, "currency": "{default_currency}", "category": "Breakfast", "vendor": "Denny's", "payment_method": "Wise ({default_currency})", "description": "w/Celes"}}
</examples>

<verification_protocol>
Before finalizing the JSON:
1. QUANTITY CHECK: Is the 'Amount' actually a price? (e.g., Is it 40.00 or is it part of a vendor name like 'Castellana 200'?) 
2. CURRENCY VALIDITY: If the Amount is not followed by a currency code (e.g., USD, JPY, ARS) does the currency match {default_currency}?
3. REMAINDER CHECK: Did the input line have words after the HINT (e.g., '2TB Storage', 'May rent', 'Meeting + Negotiation with DOMO')? If yes, and your 'description' is empty, you have failed. Re-extract and include all words.
</verification_protocol>
"""

def get_structured_data(combined_text, default_currency, categories, cancel_event=None, progress_callback=None):
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
        raise ConnectionError("Cannot connect to Ollama. Is the desktop app running?")
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
                print(f"Fuzzy Match: '{first_word}' -> '{expected_cat}'. Processing: '{line_to_process}'")
            else:
                print(f"Skipping: No category match for {line}")
                continue

        # 4. LLM loop
        try:
            user_content = f"FIXED CATEGORY: {expected_cat}\nLINE: {line_to_process}"

            response = ollama.chat(
                model='mistral:7b',
                messages=[
                    {'role': 'system',
                     'content': get_row_prompt(default_currency)},
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
            print(f"LLM sees: {line_to_process}")
            print(f"✅ {line}")
            print(f">>> [{item['date']}] {item['vendor']}: {item['amount']} {item['currency']} [{item['category']}] [{item['payment_method']}] [{item['description']}]\n")

        except json.JSONDecodeError as e:
            print(f"Skipping line due to JSON formatting error: {e}")
            continue
        except Exception as e:
            raise ConnectionError(f"Ollama execution failed: {str(e)}")

    # Debug
    # print(f"--- DEBUG STATS ---")
    # print(f"Lines sent to AI: {len(lines)}")
    # print(f"Input lines:\n{lines}\n")
    # print(f"combined_text: {combined_text}")

    return final_results


