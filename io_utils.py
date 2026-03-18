from models import session, Currency, Project, Account
from decimal import Decimal, ROUND_HALF_UP
import datetime, difflib, re


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

def extract_exchange_rate(description):
    """
    Finds the pattern 'TC' followed by a number in the description.
    Returns the float value or None.
    """
    if not description:
        return None

    # Pattern: 'TC' + any spaces + digits/dots
    match = re.search(r'TC\s*([\d.]+)', description, re.IGNORECASE)

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def get_active_account(prompt):
    """Returns a selected active account."""
    active_accounts = session.query(Account).filter_by(active_bool=True).order_by(Account.name.asc()).all()
    print("\nAvailable Accounts:\n")
    for idx, acc in enumerate(active_accounts):
        bal = Decimal(str(acc.balance)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        bal = float(bal)
        print(f" [{idx}] {acc.name} ({acc.currency_code}) | {bal}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_accounts):
            account = active_accounts[int(choice)]
            return account
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid account.
                  \rPlease choose from 0 to {len(active_accounts)-1}.
                  \r**********************""")

def get_active_currency(prompt):
    """Returns a selected active currency."""
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
    """Returns a selected active project."""
    active_projects = session.query(Project).filter_by(active_bool=True).all()
    print("\nAvailable Projects:")
    for idx, p in enumerate(active_projects):
        print(f" [{idx}] {p.name}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_projects):
            project_str = active_projects[int(choice)].id
            return project_str
        elif choice == 's':
            return None
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid project.
                  \rPlease choose from 0 to {len(active_projects)-1}.
                  \r**********************""")

def get_best_match(name, choices, threshold=0.6):
    """Returns the best match from choices if above threshold."""
    matches = difflib.get_close_matches(name, choices, n=1, cutoff=threshold)
    return matches[0] if matches else None

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


