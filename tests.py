from models import session
import expense_manager

manager = expense_manager.TransactionManager(session)

amount_str=input("Enter amount of the expense: ")
currency=input("Enter currency code (e.g., ARS): ")
category=input("Enter category name: ")
vendor=input("Enter vendor name: ")
payment_method=input("Enter payment method name: ")
project=input("Enter project name: ") or None
descr=input("Enter description: ")
ts=input("Enter timestamp (YYYY-MM-DD HH:MM) or leave blank for Now: ")

try:
    new_expense = manager.add_expense(
        amount=float(amount_str),
        currency_code=currency,
        category_name=category,
        vendor_name=vendor,
        payment_method_name=payment_method,
        project_name=project,
        description=descr,
        timestamp=None
    )
    print(f"New expense added: {new_expense.id}")
    print(f"New account balance: {new_expense.payment_method.account.balance}")

except Exception as e:
    print(f"Error: {e}")