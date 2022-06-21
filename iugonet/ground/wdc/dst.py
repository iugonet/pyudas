
from .load.load_dst import load_dst


def dst(trange=['2011-01-01', '2011-01-02'], level='final'):

    load_dst(trange=trange,level=level)

    return True
#dst(trange=['2011-1-1/00:00:00', '2012-1-2/12:00:00'],level='all')
