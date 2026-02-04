from models import session, Category, PaymentMethod, Currency
from tests import get_active_currency
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
       - DESCRIPTION: Everything remaining after the payment hint.
    
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
       - 'wise' -> 'Wise (USD)' or 'Wise (JPY)' (depends on the currency)
       - 'wizink' -> 'Wizink' 
       - 'revolut' -> 'Revolut (EUR)' or 'Revolut (JPY)' (depends on the currency)
    5. DATE: Every object MUST have a "date" field (DD/MM) extracted from the closest preceding Header.
    6. ATOMICITY: One line in = One JSON object out. NEVER combine lines.
    7. DATE_CLEANING: Extract ONLY "DD/MM". If the header is "16/01 (Trieste):", the date is "16/01".
    8. DELIMITER_LOGIC: Use the Amount as the separator. Everything before is Category/Vendor. Everything after is Payment/Description.
    </constraints>

    <example>
    Input: 
    Header: 31/01 (Home):
    Data:
    Groceries SuperVerd 0.51 santander
    Groceries Mercadona 8.80 santander
    Dates Tinder 7.26 (9971.30 ARS) mp Platinum Mayo
    Subscription Amazon 4.99 santander Prime
    Videogames Steam 29.90 (39405 ARS TC 1318 - this time it charged me 21% VAT! In EU it costs 27.99 😡) mp Like A Dragon Infinite Wealth
    Subscription Spotify 2.45 (3133.47 TC 1280 -incluye 21% IVA) mp
    Lunch Five Guys 33.90 santander w/Celes
    Medical Pharmacy 8.99 santander Nasal spray
    Gifts Agustina Rojas 46.96 (78750.00 ARS TC 1677) mp Birthday boots f/Agustina
    
    Output:
    [
      {{"date": "31/01", "amount": 0.51, "currency": "{default_currency}", "category": "Groceries", "vendor": "SuperVerd", "payment_method": "Santander Debit", "description": ""}},
      {{"date": "31/01", "amount": 8.80, "currency": "{default_currency}", "category": "Groceries", "vendor": "Mercadona", "payment_method": "Santander Debit", "description": ""}},
      {{"date": "31/01", "amount": 7.26, "currency": "{default_currency}", "category": "Dates", "vendor": "Tinder", "payment_method": "Mercado Pago", "description": "(9971.30 ARS) Platinum Mayo"}},
      {{"date": "31/01", "amount": 4.99, "currency": "{default_currency}", "category": "Subscription", "vendor": "Amazon", "payment_method": "Santander Debit", "description": "Prime"}},
      {{"date": "31/01", "amount": 29.90, "currency": "{default_currency}", "category": "Videogames", "vendor": "Steam", "payment_method": "Mercado Pago", "description": "(39405 ARS TC 1318 - this time it charged me 21% VAT! In EU it costs 27.99 😡) Like A Dragon Infinite Wealth"}},
      {{"date": "31/01", "amount": 2.45, "currency": "{default_currency}", "category": "Subscription", "vendor": "Spotify", "payment_method": "Mercado Pago", "description": "(3133.47 TC 1280 -incluye 21% IVA)"}},
      {{"date": "31/01", "amount": 33.90, "currency": "{default_currency}", "category": "Lunch", "vendor": "Five Guys", "payment_method": "Santander Debit", "description": "w/Celes"}},
      {{"date": "31/01", "amount": 8.99, "currency": "{default_currency}", "category": "Medical", "vendor": "Pharmacy", "payment_method": "Santander Debit", "description": "Nasal spray"}},
      {{"date": "31/01", "amount": 46.96, "currency": "{default_currency}", "category": "Gifts", "vendor": "Agustina Rojas", "payment_method": "Mercado Pago", "description": "(78750.00 ARS TC 1677) Birthday boots f/Agustina"}}
    ]
    </example>

    <reference_data>
    Categories (comma-separated): {categories}
    Payment Methods (comma-separated): {payment_methods}
    </reference_data>

    <output_format>
    Return ONLY a JSON list of objects. No preamble.
    Each object MUST contain these exact keys:
    "date" (date), "amount" (float), "currency" (string), "category" (string), "vendor" (string), "payment_method" (string), "description" (string).
    
    Do NOT use "payment_hint" or any other variation.
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
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON list found in response")

        clean_json = content[start_idx:end_idx]
        return json.loads(clean_json)
    except Exception as e:
        print(f"DEBUG: Raw AI Output was: {content}")
        print(f"Error parsing AI response: {e}")
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


if __name__ == "__main__":
    filename = "my_expenses_2025.txt"

    try:
        daily_chunks = chunk_file_by_day(filename)

        print(f"Successfully identified {len(daily_chunks)} days of transactions.")

        currency_str = get_active_currency("\nEnter currency code (e.g., ARS): ")

        print(currency_str)

        active_categories = session.query(Category).filter_by(active_bool=True).all()

        categories_str = ", ".join([str(category.name) for category in active_categories])

        print(categories_str)

        active_payment_methods = session.query(PaymentMethod).filter_by(active_bool=True).all()

        payment_methods_str = ", ".join([str(payment_method.name) for payment_method in active_payment_methods])

        print(payment_methods_str)

        batch_size = 10

        for idx in range(0, len(daily_chunks), batch_size):
            batch = daily_chunks[idx: idx + batch_size]
            combined_str = ""
            for day in batch:
                combined_str += f"Header: {day['header']}\nData:\n{day['data']}\n\n"

            print(f"\n--- Processing Batch (Days {idx+1} to {idx + len(batch)}) ---")

            parsed_results = get_structured_data(combined_str, categories_str, payment_methods_str, currency_str)

            if parsed_results:
                for res in parsed_results:
                    print(f"[{res.get('date')}] {res.get('vendor')}: {res.get('amount')} {res.get('currency')} [{res.get('category')}] [{res.get('payment_method')}] [{res.get('description')}]")

            cmd = input("\nPress Enter for next batch, or 'q' to quit: ").lower()
            if cmd == 'q':
                break

    except FileNotFoundError:
        print(f"File not found: {filename}. Check the path!")



