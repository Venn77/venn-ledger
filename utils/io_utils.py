from database.models import Currency, Project, Account, Stream, Payer
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import datetime, difflib, re


def clean_date(date_str):
    """
    Makes sure the date is a valid format.
    Ex: YYYY-MM-DD HH:MM.
    """
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
    Finds the pattern 'FX' (or legacy 'TC') followed by a number in the description.
    Returns the float value or None.
    """
    if not description:
        return None

    # Pattern: 'FX 1.14', 'fx 1.14', 'TC 1.14', 'tc1.14'
    match = re.search(r'(?:FX|TC)\s*([\d.]+)', description, re.IGNORECASE)

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def extract_valid_time(datetime_str: str) -> Optional[str]:
    """
    Safely extracts the HH:MM:SS portion from a datetime string.
    Returns the time string if valid, otherwise returns None.
    """
    if not datetime_str or " " not in datetime_str.strip():
        return None

    candidate_time = datetime_str.strip().split(" ")[-1]

    try:
        datetime.datetime.strptime(candidate_time, "%H:%M:%S")
        return candidate_time
    except ValueError:
        return None

def get_relative_datetime_str(current_datetime_str: str, fallback_time: str, days_ago: int) -> str:
    """
    Calculates a relative date (e.g. 0 for today, 1 for yesterday)
    while safely preserving the time portion from the existing string.
    """
    valid_time = extract_valid_time(current_datetime_str)
    active_time = valid_time if valid_time else fallback_time

    target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
    return f"{target_date.strftime('%Y-%m-%d')} {active_time}"

def format_input_float(raw_val, decimals=2):
    """Formats a raw value into a string with exact decimal precision WITHOUT commas."""
    if raw_val is None or str(raw_val).strip() == "":
        return None

    try:
        if isinstance(raw_val, str):
            val = float(raw_val.replace(",", "."))
        else:
            val = float(raw_val)

        return f"{val:.{decimals}f}"
    except ValueError:
        return None

def get_active_account(prompt, db_session):
    """Returns a selected active account."""
    active_accounts = db_session.query(Account).filter_by(active_bool=True).order_by(Account.name.asc()).all()
    print("\nAvailable Accounts:\n")
    print(f"     {'Account Name':<20} | {'Currency':>12} | {'Balance':>12}")
    print("-" * 60)
    for idx, acc in enumerate(active_accounts):
        bal = Decimal(str(acc.balance)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        bal = float(bal)
        print(f" [{idx}] {acc.name:<{20 if len(str(idx)) == 1 else 19}} | {acc.currency_code:>12} | {bal:>12.{acc.currency.decimals}f}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_accounts):
            account = active_accounts[int(choice)]
            return account
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid account.
                  \rPlease choose from 0 to {len(active_accounts)-1}.
                  \r**********************""")

def get_active_currency(prompt, db_session):
    """Returns a selected active currency."""
    # Must ensure currency is selected from available ones.
    active_curs = db_session.query(Currency).filter_by(active_bool=True).order_by(Currency.name.asc()).all()
    print("\nAvailable Currencies:\n")
    for idx, c in enumerate(active_curs):
        print(f" [{idx}] {c.code}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_curs):
            currency_str = active_curs[int(choice)].code
            return currency_str
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid currency.
                  \rPlease choose from the 0 to {len(active_curs)-1}.
                  \r**********************""")

def get_active_payer(prompt, db_session):
    """Returns a selected active payer."""
    active_payers = db_session.query(Payer).filter_by(active_bool=True).order_by(Payer.name.asc()).all()
    print("\nAvailable Payers:\n")
    for idx, p in enumerate(active_payers):
        print(f" [{idx}] {p.name}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_payers):
            payer_str = active_payers[int(choice)].id
            return payer_str
        elif choice == 's':
            return None
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid payer.
                  \rPlease choose from 0 to {len(active_payers)-1}.
                  \r**********************""")

def get_active_project(prompt, db_session):
    """Returns a selected active project."""
    active_projects = db_session.query(Project).filter_by(active_bool=True).order_by(Project.name.asc()).all()
    print("\nAvailable Projects:\n")
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

def get_active_stream(prompt, db_session):
    """Returns a selected active stream."""
    active_streams = db_session.query(Stream).filter_by(active_bool=True).order_by(Stream.name.asc()).all()
    print("\nAvailable Streams:\n")
    for idx, s in enumerate(active_streams):
        print(f" [{idx}] {s.name}")
    while True:
        choice = input(prompt).strip().lower()
        if choice.isdigit() and int(choice) < len(active_streams):
            stream_str = active_streams[int(choice)].id
            return stream_str
        elif choice == 's':
            return None
        print(f"""\n***** ERROR *****
                  \r'{choice}' is not a valid stream.
                  \rPlease choose from 0 to {len(active_streams)-1}.
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

def validate_parsed_record(data, manager, year, pm_currency_map, cat_names, ven_names, curr_names=None):
    """
    Checks DB integrity, updates status flags, and returns (errors, warnings).
    """
    errors, warnings = [], []
    data['is_duplicate'] = False

    try:
        amt = float(data.get('amount', 0))
    except ValueError:
        errors.append("Invalid Amount.")
        amt = 0.0

    base_curr = getattr(manager, 'base_currency', 'EUR')
    curr = data.get('currency', base_curr)

    if curr_names is not None and curr not in curr_names:
        errors.append(f"Unregistered Currency '{curr}'.")

    valid_pms = [name for name, c_code in pm_currency_map.items() if c_code == curr]
    if not valid_pms:
        errors.append(f"No Payment Methods registered for {curr}.")
    elif data.get('payment_method') not in valid_pms:
        errors.append("Select a matching Payment Method.")

    if curr != base_curr:
        raw_fx = data.get('fx_rate')
        if raw_fx is None:
            if not extract_exchange_rate(data.get('description', '')):
                # noinspection PyBroadException
                try:
                    d, m = data['date'].split('/')
                    dt = datetime.datetime(int(year), int(m), int(d), 12, 0, 0)
                    if not manager.get_historical_fx_rate(curr, dt):
                        errors.append("Missing/Invalid FX Rate.")
                except Exception:
                    errors.append("Missing/Invalid FX Rate.")
        else:
            try:
                if float(raw_fx) <= 0: raise ValueError
            except ValueError:
                errors.append("Missing/Invalid FX Rate.")

    ven_val = data.get('vendor', '').strip()
    if not ven_val:
        warnings.append("Will be imported with no Vendor.")
    elif ven_val not in ven_names:
        warnings.append("New Vendor will be created.")

    cat_val = data.get('category', '').strip()
    if not cat_val:
        warnings.append("Will be imported with no Category.")
    elif cat_val not in cat_names:
        warnings.append("New Category will be created.")

    if not errors:
        # noinspection PyBroadException
        try:
            d, m = data['date'].split('/')
            db_date = f"{year}-{int(m):02d}-{int(d):02d}"
            if manager.check_for_duplicate(amt, ven_val, db_date, "expense"):
                data['is_duplicate'] = True
                warnings.append("Potential Duplicate in DB")
        except Exception:
            pass

    raw_line = f"\n\nRaw Line: {data.get('line', '')}"
    if errors:
        data['is_valid'], data['status_type'] = False, "red"
        data['tooltip'] = "\n".join(errors) + raw_line
    elif warnings:
        data['is_valid'], data['status_type'] = True, "yellow"
        data['tooltip'] = "\n".join(warnings) + raw_line
    else:
        data['is_valid'], data['status_type'] = True, "green"
        data['tooltip'] = "Ready to import." + raw_line

    return errors, warnings


