from .load.load_dst import load_dst

def dst(trange=['2011-01-01', '2011-01-02'], level='final'):
    load_dst(trange=trange,level=level)
    return True
