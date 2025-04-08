import pyspedas
import pytplot
from pytplot.MPLPlotter.tplot import tplot

# gmag_nipr
from iugonet import gmag_nipr

gmag_nipr( site=['syo', 'hus'], trange=[ '2017-03-27', '2017-03-28' ] )

pytplot.tplot_names()

tplot( [ 'nipr_mag_syo_1sec', 'nipr_mag_hus_02hz' ] )


# ask_nipr
from iugonet import ask_nipr

ask_nipr( site='tro', trange=[ '2018-02-18', '2018-02-19' ] )

tplot( [ 'nipr_keo_tro_5577_ns', 'nipr_keo_tro_5577_ew' ] )


# eiscat
from iugonet import eiscat

eiscat( site='tro_uhf', trange=[ '2018-02-16 18:00:00', '2018-02-17 04:00:00' ], time_clip=True )

pytplot.ylim( 'eiscat_trouhf_ne', 70, 150 )
pytplot.ylim( 'eiscat_trouhf_te', 70, 150 )
pytplot.ylim( 'eiscat_trouhf_ti', 70, 150 )
pytplot.ylim( 'eiscat_trouhf_vi', 70, 150 )

tplot( [ 'eiscat_trouhf_ne', 'eiscat_trouhf_te', 'eiscat_trouhf_ti', 'eiscat_trouhf_vi' ] )


# gmag_wdc
from iugonet import gmag_wdc

gmag_wdc(trange=['2011-01-01', '2011-02-01'],level="final",site="kak asy sym dst",res="min")
gmag_wdc(trange=['2011-01-01', '2011-02-01'],level="provisional",site="ae",res="min")

tplot(['wdc_mag_dst_final','wdc_mag_ae_1min_provisional','wdc_mag_sym','wdc_mag_asy','wdc_mag_kak_1min'])

# gmag_wdc AE realtime
gmag_wdc(trange=['2024-12-01', '2024-12-03'],level="real_time",site="ae",res="min")

tplot('wdc_mag_??_1min_real_time')

# gmag_nipr_induction
from iugonet import gmag_nipr_induction

gmag_nipr_induction(site='syo', trange=['2018-01-01', '2018-01-02'])

tplot( ['nipr_imag_syo_20hz'] )


# elf_hokudai
from iugonet import elf_hokudai

elf_hokudai(site='syo', trange=['2010-01-01 00:00:00', '2010-01-01 01:00:00'])

tplot( ['hokudai_elf_syo'] )
