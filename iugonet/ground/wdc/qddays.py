


from .load.load_qddays import load_qddays

def qddays(trange=['2010-1-1', '2010-1-2']):
    return load_qddays(trange)

