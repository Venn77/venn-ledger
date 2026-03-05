from models import session, Currency, Project
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

