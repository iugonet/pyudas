import pyspedas
import pytplot
from pytplot.MPLPlotter.tplot import tplot

from iugonet import gmag_nipr

vars = gmag_nipr( trange=[ '2017-03-27', '2017-03-28' ] )

vars = pytplot.tplot_names()

tplot( [ 'nipr_mag_syo_1sec', 'nipr_mag_hus_02hz' ] )


from iugonet import ask_nipr

vars = ask_nipr( site='tro', trange=[ '2018-02-18', '2018-02-19' ] )

# pytplot.timespan( '2018-02-18 00:00:00', 3, keyword='hours' )

tplot( [ 'nipr_keo_tro_5577_ns', 'nipr_keo_tro_5577_ew' ] )


from iugonet import gmag_wdc

vars = gmag_wdc(trange=['2011-1-1', '2011-2-1'],level="final",site="kak asy sym dst ae",res="min")

tplot( ['SYM-H', 'site_min_kak_X'] )
