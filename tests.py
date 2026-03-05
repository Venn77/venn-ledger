from models import session, Currency, PaymentMethod, Project
import expense_manager, datetime


def get_active_currency(prompt):
    """
    Checks if the input is an active currency.
    """
    # Must ensure currency is selected from available ones.
    active_curs = session.query(Currency).filter_by(active_bool=True).all()
    cur_codes = [cur.code for cur in active_curs]
    print("\nAvailable Currencies:")
    for code in cur_codes:
        print(f"- {code}")
    while True:
        currency_str = input(prompt).upper().strip()
        if currency_str in cur_codes:
            return currency_str
        print(f"""\n***** ERROR *****
                  \r'{currency_str}' is not a valid currency.
                  \rPlease choose from the list above.
                  \r**********************""")

def get_active_project(prompt):
    """
    Checks if the input is an active project.
    """
    active_projects = session.query(Project).filter_by(active_bool=True).all()
    print("\nAvailable Projects:")
    for i, n in enumerate(active_projects):
        print(f" [{i}] {n.name}")
    while True:
        index = input(prompt).strip().lower()
        if index.isdigit() and int(index) < len(active_projects):
            project_str = active_projects[int(index)].id
            return project_str
        elif index == 's':
            return None
        print(f"""\n***** ERROR *****
                  \r'{index}' is not a valid project.
                  \rPlease choose from the list above.
                  \r**********************""")

def get_valid_float(prompt):
    """
    Checks if the input is a float.
    Converts comma to dot for decimals.
    """
    while True:
        value_str = input(prompt).strip()
        value_str = value_str.replace(",",".")
        try:
            return float(value_str)
        except ValueError:
            print(f"""\n***** INPUT ERROR *****
                    \r'{value_str}' is not a valid number. Please use digits (e.g., 15.50)
                    \r************************""")

def get_valid_year(prompt):
    """Checks if the input is a 4-digit year."""
    while True:
        try:
            return datetime.datetime.strptime(input(prompt).strip(),"%Y").year
        except ValueError:
            print(f"""\n***** DATE ERROR *****
                        \rFormat must be: YYYY.
                        \nEx: 2025
                        \r**********************""")

def clean_date(date_str):
    """
    Makes sure the date is a valid format.
    Ex: YYYY-MM-DD HH:MM.
    """
    # if not date_str or date_str.strip() == "":
    #     return None

    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        print("""\n***** DATE ERROR *****
                  \rFormat must be: YYYY-MM-DD HH:MM
                  \rEx: 2003-01-01 12:23
                  \r**********************""")
        return "ERROR"


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