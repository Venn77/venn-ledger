from models import session, Category, PaymentMethod, Currency, Vendor
from tests import get_active_currency, get_valid_year
from ai_parser import chunk_file_by_day, get_structured_data
import expense_manager, datetime, difflib


def get_best_match(name, choices, threshold=0.6):
    """Returns the best match from choices if above threshold."""
    matches = difflib.get_close_matches(name, choices, n=1, cutoff=threshold)
    return matches[0] if matches else None


if __name__ == "__main__":
    filename = "my_expenses_2025.txt"

    manager = expense_manager.TransactionManager(session)

    def validate_and_save_batch(results, default_currency, year, categories, payment_methods, vendors):
        """
        Validates currency, exchange rate, category, vendor and payment method.
        Saves to db after user confirmation.
        """
        for item in results:
            print(f"\n--- Reviewing: {item['date']} | {item['vendor']} | {item['amount']} {item['currency']} | {item['category']} | {item['payment_method']} | {item['description']} ---")

            # 1. Test currency
            if item['currency'] != default_currency:
                # Skip - here we will handle exchange rate. It will ask for manual input if currency != 'EUR'
                print(f"   ! Notice: Item uses {item['currency']}, not default currency {default_currency}.")

            # 2. Test category
            cat_name = item['category']
            if cat_name not in categories:
                match = get_best_match(cat_name, categories)
                if match:
                    choice = input(f"   ? Category '{cat_name}' not found. Use '{match}'? (y/n): ").lower()
                    if choice == 'y':
                        cat_name = match
                else:
                    # TransactionManager class should be creating the category when it takes a non-existing choice.
                    print(f"   ! Category '{cat_name}' is new. It will be created.")

            # 3. Test vendor
            vendor_name = item['vendor']
            if vendor_name not in vendors:
                match = get_best_match(vendor_name, vendors, threshold=0.8)
                if match:
                    choice = input(f"   ? Vendor '{vendor_name}' looks like '{match}'. Use existing? (y/n): ").lower()
                    if choice == 'y':
                        vendor_name = match
                else:
                    # TransactionManager class should be creating the vendor when it takes a non-existing choice.
                    print(f"   ! Vendor '{vendor_name}' is new. It will be created.")

            # 4. Test payment method
            pm_name = item['payment_method']
            if pm_name not in payment_methods:
                match = get_best_match(pm_name, payment_methods)
                if match:
                    choice = input(f"   ? Suggestion: Map '{pm_name}' to '{match}'? (y/n): ").lower()
                    if choice == 'y':
                        pm_name = match
                else:
                    print(f"   ! ERROR: Payment method '{pm_name}' is invalid. Skipping item") # Verify it does this.
                    # Here we should select an existing method.
                    continue
            # Here we should check if pm_account's currency matches item['currency']. If not, skip.

            # 5. Resolve date
            day_res, month_res = map(int, item['date'].split('/'))
            dt = datetime.datetime(year, month_res, day_res)

            # 6. Confirm and Save
            confirm = input(f"   >> Save [{dt}] {vendor_name} ({item['amount']}) to DB? (y/n/skip): ").lower()
            if confirm == 'y':
                try:
                    manager.add_expense(
                        amount=item['amount'],
                        currency_code=item['currency'],
                        category_name=cat_name,
                        vendor_name=vendor_name,
                        payment_method_name=pm_name,
                        description=item['description'],
                        timestamp=dt
                    )
                    print("  ✓ Saved.")
                except Exception as e:
                    print(f"  ✗ DB Error: {e}")

    try:
        daily_chunks = chunk_file_by_day(filename)

        print(f"Successfully identified {len(daily_chunks)} days of transactions.")

        currency_str = get_active_currency("\nEnter currency code (e.g., ARS): ")

        print(currency_str)

        year_str = get_valid_year("\nEnter year (e.g., 2025): ")

        print(year_str)

        active_categories = session.query(Category).filter_by(active_bool=True).order_by(Category.id.desc()).all()

        active_payment_methods = session.query(PaymentMethod).filter_by(active_bool=True).all()

        payment_methods_str = ", ".join([str(payment_method.name) for payment_method in active_payment_methods])

        print(payment_methods_str)

        active_vendors = session.query(Vendor).filter_by(active_bool=True).all()

        batch_size = 250

        for idx in range(0, len(daily_chunks), batch_size):
            batch = daily_chunks[idx: idx + batch_size]
            combined_str = ""
            for day in batch:
                combined_str += f"{day['header']}\n{day['data']}\n"

            print(f"\n--- Processing Batch (Days {idx+1} to {idx + len(batch)}) ---")

            parsed_results = get_structured_data(combined_str, currency_str, active_categories)

            if parsed_results:
                # Show count
                print(f"Results parsed: {len(parsed_results)}")
                for res in parsed_results:
                    print(f"[{res.get('date')}] {res.get('vendor')}: {res.get('amount')} {res.get('currency')} [{res.get('category')}] [{res.get('payment_method')}] [{res.get('description')}]")
               # cat_names = [c.name for c in active_categories]
               # pm_names = [p.name for p in active_payment_methods]
               # ven_names = [v.name for v in active_vendors]
               #
               # validate_and_save_batch(parsed_results, currency_str, year_str, cat_names, pm_names, ven_names)

            cmd = input("\nPress Enter for next batch, or 'q' to quit: ").lower()
            if cmd == 'q':
                break

    except FileNotFoundError:
        print(f"File not found: {filename}. Check the path!")


