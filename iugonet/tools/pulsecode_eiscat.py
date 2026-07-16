"""EISCAT radar pulse-code id <-> pulse-code name conversion.

Port of ``iugonet/tools/get_pulsecode_eiscat.pro``.
"""
__all__ = ["get_pulsecode_eiscat"]

#: pulse_code_id -> pulse_code, transcribed from the ``case`` block in
#: ``get_pulsecode_eiscat.pro`` (102 entries, ids 0..117). The IDL source
#: spells both directions out separately; they were checked against each other
#: and agree exactly, so the reverse map below is derived rather than copied.
PULSE_CODES = {
    0: 'cp0', 1: 'cp1', 2: 'cp2', 3: 'cp3', 4: 'cp4', 5: 'cp5', 6: 'cp6',
    7: 'cp7', 8: 'cp8', 9: 'cp9', 10: 'tau0', 11: 'tau1', 12: 'tau2', 13:
    'tau3', 14: 'tau4', 15: 'tau5', 16: 'tau6', 17: 'tau7', 18: 'tau8',
    19: 'tau9', 20: 't2pl', 31: 'ipy0', 32: 'beat', 33: 'taro', 34:
    'folk', 35: 'arc1', 36: 'mand', 37: 'stef', 38: 'hild', 39: 'pia0',
    40: 'gup0', 41: 'gup1', 42: 'gup2', 43: 'gup3', 50: 'cp0e', 51:
    'cp0f', 52: 'cp0g', 53: 'cp0h', 54: 'cp1c', 55: 'cp1d', 56: 'cp1e',
    57: 'cp1f', 58: 'cp1h', 59: 'cp1i', 60: 'cp1j', 61: 'cp1k', 62:
    'cp1l', 63: 'cp2b', 64: 'cp2c', 65: 'cp2d', 66: 'cp2e', 67: 'cp2f',
    68: 'cp2h', 69: 'cp2i', 70: 'cp2j', 71: 'cp2k', 72: 'cp3b', 73:
    'cp3c', 74: 'cp3d', 75: 'cp3e', 76: 'cp3f', 77: 'cp3h', 78: 'cp3i',
    79: 'cp3j', 80: 'cp3k', 81: 'cp4a', 82: 'cp4b', 83: 'cp5a', 84:
    'cp5b', 85: 'cp5c', 86: 'cp6a', 87: 'cp6b', 88: 'cp6c', 89: 'cp7a',
    90: 'cp7b', 91: 'cp7c', 92: 'cp7d', 93: 'cp7e', 94: 'cp7f', 95:
    'cp7g', 96: 'cp7h', 97: 'sp00', 98: 'sp1c', 99: 'sp1d', 100: 'sp1e',
    101: 'sp1f', 102: 'sp1h', 103: 'sp1i', 104: 'sp1j', 105: 'sp1k', 106:
    'sp2b', 107: 'sp2c', 108: 'sp2d', 109: 'sp2e', 110: 'sp2f', 111:
    'sp2h', 112: 'sp2i', 113: 'CP1H', 114: 'CP1K', 115: 'CP3F', 116:
    'PULS', 117: 'CONV'
}

#: pulse_code -> pulse_code_id (the inverse of :data:`PULSE_CODES`).
PULSE_IDS = {v: k for k, v in PULSE_CODES.items()}


def get_pulsecode_eiscat(pulse_in, mode=0):
    """IDL ``get_pulsecode_eiscat(pulse_in, mode)``: convert a pulse code either way.

    Parameters
    ----------
    pulse_in : int or str
        A pulse_code_id (mode 0) or a pulse_code (mode != 0).
    mode : int
        0 (default) converts id -> pulse_code; anything else converts
        pulse_code -> id.

    Returns
    -------
    str or int
        The converted value; ``''`` (mode 0) or ``-1`` (mode != 0) when the
        input is not in the table -- IDL's ``else`` branches.

    Notes
    -----
    Two IDL behaviours are worth knowing about, both reproduced:

    - ``if ~keyword_set(mode)`` means **mode=0 and an unset mode are the same
      thing**, so there is no way to ask for id -> code explicitly other than
      by omitting it.
    - ``if ~keyword_set(pulse_in)`` treats **``pulse_in=0`` as "no input"**, so
      IDL prints 'No input data!' and executes ``stop``; ``cp0`` (id 0) can
      never be looked up by id. This port raises ``ValueError`` instead of
      dropping into a debugger, since ``stop`` has no useful Python analogue.
    """
    if not pulse_in and pulse_in != "":
        raise ValueError("No input data!")

    if not mode:
        # IDL additionally requires size(pulse_in,/type) eq 2 (a 2-byte INT),
        # so get_pulsecode_eiscat(5L) returns '' there. Python has one int
        # type, so that distinction cannot be reproduced and any int is
        # accepted.
        if not isinstance(pulse_in, (int,)) or isinstance(pulse_in, bool):
            print("The pulse_in must be an integer for this mode.")
            return ""
        return PULSE_CODES.get(int(pulse_in), "")

    if not isinstance(pulse_in, str):
        print("The pulse_in must be a string for this mode.")
        return -1
    return PULSE_IDS.get(pulse_in, -1)
