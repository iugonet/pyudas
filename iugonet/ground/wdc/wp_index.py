


from .load.load_wp_index import load_wp_index

def wp_index(trange=['2010-1-1', '2010-1-2']) :
    return load_wp_index(trange=trange)

