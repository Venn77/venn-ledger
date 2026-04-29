import re


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