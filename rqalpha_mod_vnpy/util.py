def make_underlying_symbol(id_or_symbol):
    return filter(lambda x: x not in '0123456789 ', id_or_symbol).upper()