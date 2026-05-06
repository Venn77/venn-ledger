from database.models import Session, Category, PaymentMethod, Vendor, Project
from utils.io_utils import (get_active_currency, get_valid_year, get_valid_float, get_active_project,
                        get_best_match, extract_exchange_rate)
from core.ai_parser import chunk_file_by_day, get_structured_data, get_row_prompt, get_skip_terms
import datetime
from core import manager as finance_manager
from pathlib import Path


def validate_and_save_batch(results, default_currency, year, project, categories, payment_methods, vendors):
    """
    Validates currency, exchange rate, category, vendor and payment method.
    Saves to db after user confirmation.
    """
    for item in results:
        print(
            f"\n--- Reviewing: {item['date']} | {item['vendor']} | {item['amount']} {item['currency']} | {item['category']} | {item['payment_method']} | {item['description']} ---")

        # 1. Resolve date
        day_res, month_res = map(int, item['date'].split('/'))
        dt = datetime.datetime(year, month_res, day_res)

        # 2. Test currency and define payment method
        if item['currency'] != default_currency:
            print(f"   ! Notice: Item uses '{item['currency']}', not default currency '{default_currency}'.")

        pm_name = item['payment_method']
        # Find closest pm match
        if pm_name not in payment_methods:
            match = get_best_match(pm_name, payment_methods)
            if match:
                choice = input(f"   ? Suggestion: Map '{pm_name}' to '{match}'? (y/n): ").lower()
                pm_name = match if choice == 'y' else pm_name
            # Choose from existing pms
            if pm_name not in payment_methods:
                print(f"   ! '{pm_name}' is not in DB.")
                sorted_payment_methods = sorted(payment_methods)
                for i, name in enumerate(sorted_payment_methods):
                    print(f" [{i}] {name}")
                index = input("   Choose number to use (or 's' to skip item): ")
                if index.isdigit() and int(index) < len(sorted_payment_methods):
                    pm_name = sorted_payment_methods[int(index)]
                # Or skip the item
                else:
                    print("   Skipping item.")
                    continue

        pm_obj = db_session.query(PaymentMethod).filter_by(name=pm_name).first()

        if not pm_obj:
            print(f"   ! ERROR: Payment method '{pm_name}' is invalid. Skipping item.")
            continue

        account_currency = pm_obj.account.currency_code
        account_name = pm_obj.account.name
        item_currency = item['currency']
        # DEBUG
        print(f"Account currency: '{account_currency}'")
        print(f"Account name: '{account_name}'")
        print(f"Item currency: '{item_currency}'")

        if account_currency != item_currency:
            print(
                f"   ! CURRENCY MISMATCH: Item is {item_currency}, but {pm_name} is linked to {account_name} with {account_currency}.")
            print("   ! Skipping item to prevent balance corruption.")
            continue

        if item['currency'] != 'EUR':
            # Get exchange rate from description
            rate_source = None
            fx_rate = extract_exchange_rate(item['description'])
            if fx_rate:
                rate_source = 'description'
            if not fx_rate:
                fx_rate, fx_rate_ts = manager.get_historical_fx_rate(item['currency'], dt)
                if fx_rate:
                    rate_source = 'db'
                    print(f"   ! Auto-detected historical rate from DB: {fx_rate} ({fx_rate_ts})")
            # Ask for confirmation if rate extracted from description
            if fx_rate and rate_source == 'description':
                choice = input(f"   ? Use exchange rate '{fx_rate}'? (y/n): ").lower()
                if choice != 'y':
                    fx_rate = get_valid_float(f"Enter the exchange rate ('EUR' -> '{item['currency']}'): ")
            elif fx_rate and rate_source == 'db':
                # Auto accept rate if obtained from db
                fx_rate = fx_rate
            else:
                print(f"   ! No rate found in description or DB for {item['currency']}.")
                # Manual rate input if not found
                fx_rate = get_valid_float(f"Enter the exchange rate ('EUR' -> '{item['currency']}'): ")
        else:
            fx_rate = None

        # 3. Test category
        cat_name = item['category']
        if cat_name not in categories:
            match = get_best_match(cat_name, categories)
            if match:
                choice = input(f"   ? Category '{cat_name}' not found. Use '{match}'? (y/n): ").lower()
                if choice == 'y':
                    cat_name = match
            else:
                print(f"   ! '{cat_name}' is not in DB.")
                sorted_categories = sorted(categories)
                for i, name in enumerate(sorted_categories):
                    print(f" [{i}] {name}")
                index = input(f"   Choose number to use (or 's' to use '{cat_name}'): ")
                if index.isdigit() and int(index) < len(sorted_categories):
                    cat_name = sorted_categories[int(index)]
                else:
                    # TransactionManager class should be creating the category when it takes a non-existing choice.
                    print(f"   ! Category '{cat_name}' is new. It will be created.")

        # 4. Test vendor
        vendor_name = item['vendor']
        if vendor_name not in vendors:
            match = get_best_match(vendor_name, vendors, threshold=0.8)
            if match:
                choice = input(f"   ? Vendor '{vendor_name}' looks like '{match}'. Use existing? (y/n): ").lower()
                if choice == 'y':
                    vendor_name = match
                else:
                    print(f"   ! Vendor '{vendor_name}' is new. It will be created.")
            else:
                print(f"   ! Vendor '{vendor_name}' is not in DB.")
                sorted_vendors = sorted(vendors)
                for i, name in enumerate(sorted_vendors):
                    print(f" [{i}] {name}")
                index = input(f"   Choose number to use (or 's' to use '{vendor_name}'): ")
                if index.isdigit() and int(index) < len(sorted_vendors):
                    vendor_name = sorted_vendors[int(index)]
                else:
                    print(f"   ! Vendor '{vendor_name}' is new. It will be created.")

        # 5. Resolve project
        project_name = db_session.query(Project).filter_by(id=project).first()
        if project_name:
            project_name = project_name.name
        else:
            project_name = None

        # 6. Confirm and Save
        print(f"   ! LINE '{item['line']}'")
        confirm = input(
            f"   >> Save [{dt}] {vendor_name} ({item['amount']}) {item['currency']} (FX {fx_rate}) [{item['description']}] to DB? (y/n/skip): ").lower()
        if confirm == 'y':
            try:
                manager.add_expense(
                    amount=item['amount'],
                    currency_code=item['currency'],
                    exchange_rate=fx_rate,
                    category_name=cat_name,
                    vendor_name=vendor_name,
                    project_name=project_name,
                    payment_method_name=pm_name,
                    description=item['description'],
                    timestamp=dt
                )
                print("  ✓ Saved.")
                ac_categories = db_session.query(Category).filter_by(active_bool=True).order_by(Category.id.desc()).all()
                ac_vendors = db_session.query(Vendor).filter_by(active_bool=True).all()
                categories = [c.name for c in ac_categories]
                vendors = [v.name for v in ac_vendors]
            except Exception as e:
                print(f"  ✗ DB Error: {e}")
        elif confirm == 'q':
            return
        else:
            print("   Skipped.")


if __name__ == "__main__":

    script_dir = Path(__file__).parent

    project_root = script_dir.parent

    filename = project_root / "my_expenses.txt"

    db_session = Session()

    manager = finance_manager.TransactionManager(db_session)

    try:
        skip_terms = get_skip_terms()

        currency_str = get_active_currency("\nSelect the currency: ", db_session)

        print(currency_str)

        system_prompt = get_row_prompt(currency_str)

        year_str = get_valid_year("\nEnter year (e.g., 2025): ")

        print(year_str)

        project_str = get_active_project("\nChoose number to use (or 's' for None): ", db_session)

        print(project_str)

        daily_chunks = chunk_file_by_day(filename, skip_terms)

        print(f"Successfully identified {len(daily_chunks)} days of transactions.")

        active_categories = db_session.query(Category).filter_by(active_bool=True).order_by(Category.id.desc()).all()

        active_payment_methods = db_session.query(PaymentMethod).filter_by(active_bool=True).all()

        payment_methods_str = ", ".join([str(payment_method.name) for payment_method in active_payment_methods])

        print(payment_methods_str)

        batch_size = 10

        for idx in range(0, len(daily_chunks), batch_size):
            batch = daily_chunks[idx: idx + batch_size]
            combined_str = ""
            for day in batch:
                combined_str += f"{day['header']}\n{day['data']}\n"

            print(f"\n--- Processing Batch (Days {idx+1} to {idx + len(batch)}) ---")

            parsed_results = get_structured_data(combined_str, active_categories, system_prompt)

            if parsed_results:
                # Show count
                print(f"Results parsed: {len(parsed_results)}")
                for res in parsed_results:
                    print(f"[{res.get('date')}] {res.get('vendor')}: {res.get('amount')} {res.get('currency')} [{res.get('category')}] [{res.get('payment_method')}] [{res.get('description')}]")
                # Process and save to DB
                active_categories = db_session.query(Category).filter_by(active_bool=True).order_by(Category.id.desc()).all()
                active_vendors = db_session.query(Vendor).filter_by(active_bool=True).all()
                cat_names = [c.name for c in active_categories]
                pm_names = [p.name for p in active_payment_methods]
                ven_names = [v.name for v in active_vendors]
                validate_and_save_batch(parsed_results, currency_str, year_str, project_str, cat_names, pm_names, ven_names)

            cmd = input("\nPress Enter for next batch, or 'q' to quit: ").lower()
            if cmd == 'q':
                break

    except FileNotFoundError:
        print(f"File not found: {filename}. Check the path!")

    finally:
        try:
            db_session.close()
            print("Database session closed successfully.")
            db_session.get_bind().dispose()
            print("Database connection fully severed.")
        except Exception as error:
            print(f"Error during shutdown: {error}")


