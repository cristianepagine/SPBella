"""Telefones: aceitamos como a pessoa digita e guardamos no formato internacional (E.164)."""

import phonenumbers


class InvalidPhoneError(ValueError):
    pass


def normalize_phone(raw: str, country: str) -> str:
    """'(11) 98888-7777' num salão BR → '+5511988887777'. Número com +DDI vale de qualquer país."""
    try:
        number = phonenumbers.parse(raw, country)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneError(raw) from exc
    if not phonenumbers.is_valid_number(number):
        raise InvalidPhoneError(raw)
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def display_phone(e164: str) -> str:
    """'+5511988887777' → '+55 11 98888-7777'."""
    number = phonenumbers.parse(e164, None)
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
