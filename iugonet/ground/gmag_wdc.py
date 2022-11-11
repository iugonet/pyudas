from .wdc.site import site as st


def gmag_wdc(trange=['2011-1-1', '2011-1-2'],level="final",site="dst kak ae asy sym",res="hour"):
    site2=site.split(" ")
    if ("dst" in site2):
        from .wdc.dst import dst
        dst(trange=trange,level=level)
    if("ae" in site2):
        from .wdc.ae import ae
        ae(trange=trange,level='provisional',res=res)
    if("asy" in site2):
        from .wdc.asy import asy
        asy(trange=trange)
    if("sym" in site2):
        from .wdc.sym import sym
        sym(trange=trange)
    site2=[s for s in site2 if not((s=="dst")or(s=="ae")or(s=="sym")or(s=="asy"))]
    for ss in site2:
        st(trange=trange,res=res,site=ss)
    return 0

def gmag_wdc_qddays(trange=['2011-1-1', '2011-1-2']):
    from .wdc.qddays import qddays
    result=qddays(trange=trange)
    return result

def gmag_wdc_wp_index(trange=['2010-1-1', '2010-1-2']):
    from .wdc.wp_index import wp_index
    wp_index(trange=trange)
    return 0

#(1)
#iug_load_gmag_wdc(trange=['2011-1-1', '2011-1-2'],level="provisional",site="ae",res="hour")

#(2)
#iug_load_gmag_wdc(trange=['2011-1-1', '2011-1-2'],level="all",site="dst")

#(3)
#iug_load_gmag_wdc(trange=['2011-1-1', '2011-1-2'],site="asy")

#(4)
#iug_load_gmag_wdc_qddays(trange=['2011-1-1', '2011-1-2'])

#(5)
#iug_load_gmag_wdc_wp_index(trange=['2010-1-1', '2010-1-2'])

#(6)
#iug_load_gmag_wdc(trange=['2011-1-1', '2011-1-2'],site="kak aaa",res="hour")