from database.models import Session, Account
from utils.io_utils import get_valid_float, clean_date
from core import manager as finance_manager
from decimal import Decimal, ROUND_HALF_UP
import datetime


def get_account_choice(prompt, accounts):
    """Prints indexed accounts and returns the selected Account ID."""
    print("\nAvailable Accounts:\n")
    print(f"     {'Account Name':<20} | {'Currency':>12} | {'Balance':>12}")
    print("-" * 60)
    for idx, acc in enumerate(accounts):
        bal = Decimal(str(acc.balance)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        bal = float(bal)
        print(f" [{idx}] {acc.name:<{20 if len(str(idx)) == 1 else 19}} | {acc.currency_code:>12} | {bal:>12.{acc.currency.decimals}f}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(accounts):
            return accounts[int(choice)]
        print(f"""\n***** ERROR *****
              \r'{choice}' is not a valid account.
              \rPlease choose from 0 to {len(accounts) - 1}.
              \r**********************""")

def run_transfer_ui():
    """Executes transfer UI for one operation."""
    active_accounts = db_session.query(Account).filter_by(active_bool=True).order_by(Account.name.asc()).all()

    if len(active_accounts) < 2:
        print("   ! Error: You need at least two accounts to perform a transfer.")
        return

    # START: Transfer funds
    # 1. Select Accounts
    origin = get_account_choice("\nSelect the Origin Account: ", active_accounts)
    # Filter out the origin account for the next selection
    dest_options = [a for a in active_accounts if a.id != origin.id]
    destination = get_account_choice("\nSelect the Destination Account: ", dest_options)
    # 2. Input Amounts
    amount_origin = get_valid_float(f"\nEnter amount to transfer out of '{origin.name}' ({origin.currency_code}): ")

    if origin.currency_code == destination.currency_code:
        amount_destination = amount_origin
        print(f"   ! Same currency detected. Destination amount set to {amount_destination:.{destination.currency.decimals}f}.")
    else:
        amount_destination = get_valid_float(f"\nEnter amount to transfer into '{destination.name}' ({destination.currency_code}): ")
    # 3. Metadata
    descr = input("\nEnter description (e.g., 'Funding trip': ").strip()
    while True:
        ts_input = input("\nEnter timestamp (YYYY-MM-DD HH:MM) or leave blank for Now: ").strip()
        if not ts_input:
            ts = None
            break
        ts = clean_date(ts_input)
        if isinstance(ts, datetime.datetime):
            break
        print("\nPlease try again or leave blank.")
    # 4. Review and confirmation
    print(f"\n--- TRANSFER SUMMARY ---")
    print(f" FROM: {origin.name} (-{amount_origin} {origin.currency_code})")
    print(f" TO:   {destination.name} (+{amount_destination} {destination.currency_code})")
    print(f" DESC: {origin.currency_code} -> {destination.currency_code}{' | ' + descr if descr else ''}")
    print(f" DATE: {ts if ts else datetime.datetime.now()}")

    confirm = input("\nExecute transfer? (y/n): ").lower()
    if confirm == "y":
        try:
            new_transfer = manager.transfer_funds(
                origin_id=origin.id,
                destination_id=destination.id,
                amount_orig=amount_origin,
                amount_dest=amount_destination,
                desc=descr,
                ts=ts
            )
            print("\n✓ Transfer executed and balances updated.")
            print(f"\nNew account balance for '{new_transfer.origin_account.name}' ({new_transfer.origin_account.currency_code}): {Decimal(new_transfer.origin_account.balance).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)}")
            print(f"New account balance for '{new_transfer.destination_account.name}' ({new_transfer.destination_account.currency_code}): {Decimal(new_transfer.destination_account.balance).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)}")
        except Exception as e:
            print(f"\n✗ Transfer failed: {e}")
    # END: Transfer funds


if __name__ == "__main__":
    db_session = Session()

    manager = finance_manager.TransactionManager(db_session)

    try:

        run_transfer_ui()

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


