from models import session, PaymentMethod
from io_utils import get_active_currency, get_valid_float, clean_date
import expense_manager, datetime


if __name__ == "__main__":

    manager = expense_manager.TransactionManager(session)

    amount = get_valid_float("Enter amount of the expense: ")

    currency = get_active_currency("\nEnter currency code (e.g., ARS): ")

    category = input("Enter category name: ").strip() or None

    vendor = input("Enter vendor name: ").strip() or None

    # Must ensure there is a valid payment method chosen.
    active_pms = session.query(PaymentMethod).filter_by(active_bool=True).all()
    pm_names = [pm.name for pm in active_pms]
    print("\nAvailable Payment Methods:")
    for name in pm_names:
        print(f"- {name}")
    while True:
        payment_method = input("\nEnter payment method name: ").strip()
        if payment_method in pm_names:
            break
        print(f"""\n***** ERROR *****
                  \r'{payment_method}' is not a valid method.
                  \rPlease choose from the list above.
                  \r**********************""")

    project = input("Enter project name: ").strip() or None

    descr = input("Enter description: ")

    while True:
        ts = input("Enter timestamp (YYYY-MM-DD HH:MM) or leave blank for Now: ")
        ts = clean_date(ts)
        if isinstance(ts, datetime.datetime) or ts is None:
            break

    try:
        new_expense = manager.add_expense(
            amount=amount,
            currency_code=currency,
            category_name=category,
            vendor_name=vendor,
            payment_method_name=payment_method,
            project_name=project,
            description=descr,
            timestamp=ts
        )
        print(f"New expense added: {new_expense.id}")
        print(f"New account balance: {new_expense.payment_method.account.balance}")

    except Exception as e:
        print(f"Error: {e}")