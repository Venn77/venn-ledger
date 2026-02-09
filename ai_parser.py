import re, json, ollama


def get_structured_data(combined_text, categories, payment_methods, default_currency):
    system_prompt = f"""
    <role>You are a literal text-to-JSON transcriber.</role>

    <constraints>
    1. DEFAULT_CURRENCY: {default_currency}.
    2. ENTITY_DETECTION:
       - CATEGORY: Usually 1-2 words at the very start (e.g., 'Groceries', 'Household Supplies', 'Internet & Mobile').
       - VENDOR: The proper name immediately following the category (e.g., 'Mercadona', 'PrimaPrix', 'Spotify').
       - AMOUNT: The first float value encountered (e.g., '13.90', '2.47').
       - PAYMENT_HINT: The word immediately following the amount (e.g., 'santander', 'mp', 'cash').
       - DESCRIPTION: A verbatim capture of EVERYTHING else on the line. If it's in brackets, it goes here. If it's after the payment hint, it goes here. Zero data loss permitted.
    3. BRACKET_HANDLING:
       - Text in brackets () is "metadata." 
       - If brackets are next to the Amount, they belong in the 'description'.
       - Do NOT let bracketed text count as a new column.
       - Bracketed text MUST be included in the 'description'.
    4. PAYMENT_MAPPING:
       - 'santander' -> 'Santander Debit'
       - 'mp' -> 'Mercado Pago'
       - 'cash' -> 'Cash (EUR)'
       - 'laliga' -> 'Santander LaLiga'
       - 'lacaixa' -> 'LaCaixa IKEA'
       - 'wise' -> 'Wise (USD)' if currency is USD or 'Wise (JPY)' if currency is JPY, etc. 
       - 'wizink' -> 'Wizink' 
       - 'revolut' -> 'Revolut (EUR)' if currency is EUR or 'Revolut (JPY)' if currency is JPY, etc.
    5. DATE: Every object MUST have a "date" field (DD/MM) extracted from the closest preceding Header.
    6. ATOMICITY: One line in = One JSON object out. NEVER combine lines.
    7. DATE_CLEANING: Extract ONLY "DD/MM". If the header is "16/01 (Trieste):", the date is "16/01".
    8. DELIMITER_LOGIC: Use the Amount as the separator. Everything before is Category/Vendor. Everything after is Payment/Description.
    9. DATA_PRESERVATION: 
       - The 'description' MUST contain ALL text found after the payment hint and ALL text found in brackets.
       - NEVER summarize or omit bracketed metadata like '(20800.04 TC 1318)'.
       - If a line has both brackets and trailing text, combine them: "(brackets) trailing text".
       - Ensure exchange rates in brackets are never omitted.
    10. VERBATIM_INTEGRITY: 
    - You are a pass-through pipe for metadata. 
    - If the input says "(78750.00 ARS TC 1677)", the output MUST say "(78750.00 ARS TC 1677)". 
    - You are strictly forbidden from "cleaning" or "simplifying" the description.
    - You MUST preserve all Spanish accents (á, é, í, ó, ú, ñ). 
    - NEVER replace 'á' with '¡' or any other symbol. 
    - If the input says 'mamá', the JSON MUST say 'mamá'.
    11. REFERENCE_STRICTNESS:
    - The 'payment_method' field MUST match one of the exact strings provided in <reference_data>.
    - NEVER use generic names like 'Revolut' or 'Wise'. 
    - You MUST use the mapped versions: 'Revolut (EUR)', 'Wise (USD)', etc.
    - If a mapping depends on the currency, cross-reference the detected currency with the 'PAYMENT_MAPPING' rules.
    </constraints>

    <example>
    Input: 
    Header: 31/01 (Home):
    Data:
    Groceries SuperVerd 0.51 santander
    Groceries Mercadona 8.80 santander
    Dates Tinder 7.26 (9971.30 ARS) mp Platinum Mayo
    Subscription Amazon 4.99 santander Prime
    Videogames Steam 29.90 (39405 TC 1318 - this time it charged me 21% VAT! In EU it costs 27.99 😡) mp Like A Dragon Infinite Wealth
    Subscription Spotify 2.45 (3133.47 TC 1280 -incluye 21% IVA) mp
    Lunch Five Guys 33.90 santander w/Celes
    Medical Pharmacy 8.99 santander Nasal spray
    Gifts Agustina Rojas 46.96 (78750.00 TC 1677) mp Birthday boots f/Agustina
    
    Output:
    [
      {{"date": "31/01", "amount": 0.51, "currency": "{default_currency}", "category": "Groceries", "vendor": "SuperVerd", "payment_method": "Santander Debit", "description": ""}},
      {{"date": "31/01", "amount": 8.80, "currency": "{default_currency}", "category": "Groceries", "vendor": "Mercadona", "payment_method": "Santander Debit", "description": ""}},
      {{"date": "31/01", "amount": 7.26, "currency": "{default_currency}", "category": "Dates", "vendor": "Tinder", "payment_method": "Mercado Pago", "description": "(9971.30 ARS) Platinum Mayo"}},
      {{"date": "31/01", "amount": 4.99, "currency": "{default_currency}", "category": "Subscription", "vendor": "Amazon", "payment_method": "Santander Debit", "description": "Prime"}},
      {{"date": "31/01", "amount": 29.90, "currency": "{default_currency}", "category": "Videogames", "vendor": "Steam", "payment_method": "Mercado Pago", "description": "(39405 TC 1318 - this time it charged me 21% VAT! In EU it costs 27.99 😡) Like A Dragon Infinite Wealth"}},
      {{"date": "31/01", "amount": 2.45, "currency": "{default_currency}", "category": "Subscription", "vendor": "Spotify", "payment_method": "Mercado Pago", "description": "(3133.47 TC 1280 -incluye 21% IVA)"}},
      {{"date": "31/01", "amount": 33.90, "currency": "{default_currency}", "category": "Lunch", "vendor": "Five Guys", "payment_method": "Santander Debit", "description": "w/Celes"}},
      {{"date": "31/01", "amount": 8.99, "currency": "{default_currency}", "category": "Medical", "vendor": "Pharmacy", "payment_method": "Santander Debit", "description": "Nasal spray"}},
      {{"date": "31/01", "amount": 46.96, "currency": "{default_currency}", "category": "Gifts", "vendor": "Agustina Rojas", "payment_method": "Mercado Pago", "description": "(78750.00 TC 1677) Birthday boots f/Agustina"}}
    ]
    </example>

    <reference_data>
    Categories (comma-separated): {categories}
    Payment Methods (comma-separated): {payment_methods}
    </reference_data>

    <output_format>
    Return ONLY ONE JSON list of objects. No preamble.
    Each object MUST contain these exact keys:
    "date" (date), "amount" (float), "currency" (string), "category" (string), "vendor" (string), "payment_method" (string), "description" (string).
    Do NOT use "payment_hint" or any other variation.
    Return EXACTLY ONE JSON list.
    STRICT PROHIBITIONS:
    - NO preamble like "Here is the JSON..."
    - NO postamble or explanations.
    - NO splitting the list into multiple blocks or headers.
    - NO markdown formatting (no bold text, no ```json).
    - ONLY the raw [ ... ] content.
    </output_format>
    """

    response = ollama.chat(model='llama3.1', messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': combined_text},
    ], options={'temperature': 0}
    )
    # Clean the response
    content = response['message']['content']

    try:
        # 1. Use a robust regex to find all JSON-like objects { ... }
        # This ignores any "Here is the JSON" text or multiple arrays
        obj_matches = re.findall(r'\{.*?}', content, re.DOTALL)

        refined_results = []
        for obj_str in obj_matches:
            try:
                # Fix the AI's common "empty string without key" typo: , "" }
                fixed_str = re.sub(r',\s*""\s*}', ', "description": ""}', obj_str)

                item = json.loads(fixed_str)

                # If the AI forgot a key, add it here with a blank value
                expected_keys = ["date", "amount", "currency", "category", "vendor", "payment_method", "description"]
                for key in expected_keys:
                    if key not in item:
                        item[key] = ""

                refined_results.append(item)
            except json.JSONDecodeError:
                continue

        if not refined_results:
            raise ValueError("AI output contained no valid JSON objects.")

        return refined_results

    except Exception as e:
        print(f"DEBUG: Raw AI Output was: {content}")
        print(f"Error in AI Parser: {e}")
        return None

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
                                                             "MP TC")
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


