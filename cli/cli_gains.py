from database.models import Session, Project, Stream, Payer
from utils.io_utils import (
            get_active_account, get_valid_float, clean_date,
            extract_exchange_rate, get_active_project, get_active_stream,
            get_active_payer
            )
from core import manager as finance_manager
from decimal import Decimal, ROUND_HALF_UP
import datetime


def run_gain_ui():
    """Executes gains UI for one operation."""
    # START: Add gain
    # 1. Select Account
    account = get_active_account("\nSelect the account: ", db_session)

    # 2. Select Stream
    stream_str = get_active_stream("\nChoose Stream to use (or 's' for None): ", db_session)
    stream = db_session.query(Stream).filter_by(id=stream_str).first()
    if stream:
        stream_name = stream.name
    else:
        stream_name = None

    # 3. Select Payer
    payer_str = get_active_payer("\nChoose Payer to use (or 's' for None): ", db_session)
    payer = db_session.query(Payer).filter_by(id=payer_str).first()
    if payer:
        payer_name = payer.name
    else:
        payer_name = None

    # 4. Input Amount
    amount = get_valid_float(f"\nEnter the income amount for '{account.name}' ({account.currency_code}): ")

    # 5. Currency Notice
    print(f"   ! Item currency will be '{account.currency_code}'")

    # 6. Metadata
    descr = input("\nEnter description (e.g., 'Monthly pay'): ").strip()
    while True:
        ts_input = input("\nEnter timestamp (YYYY-MM-DD HH:MM) or leave blank for Now: ").strip()
        if not ts_input:
            ts = None
            break
        ts = clean_date(ts_input)
        if isinstance(ts, datetime.datetime):
            break
        print("\nPlease try again or leave blank.")

    # 7. FX Logic
    fx_rate = None
    if account.currency_code != "EUR":
        # Get exchange rate from description
        rate_source = None
        fx_rate = extract_exchange_rate(descr)
        if fx_rate:
            rate_source = 'description'
        if not fx_rate:
            if not ts:
                ts = datetime.datetime.now()
            fx_rate, fx_rate_ts = manager.get_historical_fx_rate(account.currency_code, ts)
            if fx_rate:
                rate_source = 'db'
                print(f"   ! Auto-detected historical rate from DB: {fx_rate} ({fx_rate_ts})")
        # Ask for confirmation if rate extracted from description
        if fx_rate and rate_source == 'description':
            choice = input(f"   ? Use exchange rate '{fx_rate}'? (y/n): ").lower()
            if choice != 'y':
                fx_rate = get_valid_float(f"Enter the exchange rate ('EUR' -> '{account.currency_code}'): ")
        elif fx_rate and rate_source == 'db':
            # Auto accept rate if obtained from db
            fx_rate = fx_rate
            print(f"   ✓ Using verified DB rate: {fx_rate}")
        else:
            print(f"   ! No rate found in description or DB for {account.currency_code}.")
            # Manual rate input if not found
            fx_rate = get_valid_float(f"Enter the exchange rate ('EUR' -> '{account.currency_code}'): ")

    # 8. Resolve project
    project_str = get_active_project("\nChoose Project to use (or 's' for None): ", db_session)
    project = db_session.query(Project).filter_by(id=project_str).first()
    if project:
        project_name = project.name
    else:
        project_name = None

    # 9. Review and confirmation
    print(f"\n--- GAIN SUMMARY ---")
    print(f" FROM: {payer_name}")
    print(f" TO: {account.name}")
    print(f" STREAM: {stream_name}")
    print(f" AMOUNT: {amount}")
    print(f" DESC: {descr}")
    print(f" DATE: {ts if ts else datetime.datetime.now()}")

    confirm = input("\nExecute gain? (y/n): ").lower()
    if confirm == "y":
        try:
            new_gain = manager.add_gain(
                            amount=amount,
                            currency_code=account.currency_code,
                            account_id=account.id,
                            exchange_rate=fx_rate,
                            stream_name=stream_name,
                            payer_name=payer_name,
                            project_name=project_name,
                            description=descr,
                            timestamp=ts
                        )
            print("\n✓ Gain executed and balance updated.")
            print(f"\nNew account balance for '{new_gain.account.name}' ({new_gain.account.currency_code}): {Decimal(new_gain.account.balance).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)}")
        except Exception as e:
            print(f"\n✗ Transfer failed: {e}")

    # END: Add gain

if __name__ == "__main__":

    db_session = Session()

    manager = finance_manager.TransactionManager(db_session)

    try:

        run_gain_ui()

    except Exception as error:
        print(f"Error: {error}")

    finally:
        try:
            db_session.close()
            print("Database session closed successfully.")
            db_session.get_bind().dispose()
            print("Database connection fully severed.")
        except Exception as error:
            print(f"Error during shutdown: {error}")