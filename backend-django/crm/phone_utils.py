"""Phone normalization: detect country and prepend the correct dialing code.

Uses Google's libphonenumber (python `phonenumbers`). Important limitation:
a bare local number (e.g. "8502002002") carries no country information, so it
cannot be geo-detected. Detection only works when the number already includes
its country code or a leading "+". For bare numbers we fall back to a default
region (DEFAULT_REGION) and prepend that country's code.
"""

import phonenumbers

DEFAULT_REGION = "IN"  # bare numbers assumed Indian (+91) for this CRM


def normalize_phone(raw: str, default_region: str = DEFAULT_REGION) -> str:
    """Return the number in E.164 form (e.g. +918502002002).

    - If `raw` starts with "+" (or otherwise carries a country code), the
      country is taken from the number itself.
    - Otherwise the number is parsed as a `default_region` local number.
    - If parsing fails or the number is invalid, the original string is
      returned unchanged so we never destroy user input.
    """
    if not raw or not raw.strip():
        return raw

    text = raw.strip()
    # Treat a leading "00" as the international prefix "+".
    if text.startswith("00"):
        text = "+" + text[2:]

    region = None if text.startswith("+") else default_region
    try:
        parsed = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return raw

    if not phonenumbers.is_valid_number(parsed):
        return raw

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
