

from .load.load_sym import load_sym


def sym(trange=['2011-1-1', '2011-2-1']):
    return load_sym(trange)


#sym()
