from .load.load_ae_min import load_ae_min
from .load.load_ae_hour import load_ae_hour


def ae(trange=['2011-01-01', '2011-01-02'], res='min', level='provisional'):

    ###
    if res == 'min' :
        load_ae_min(trange=trange, level=level)

    if res == 'hour' :
        load_ae_hour(trange=trange, level=level)

    return True
