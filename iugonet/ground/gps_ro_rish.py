import numpy as np

# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from iugonet import gps_champ_fsi_nc, gps_cosmic_fsi_nc
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def gps_ro_rish(
    trange=['2006-06-01', '2006-06-02'],
    site='',
    datatype='all',
    parameter='',
    no_update=False,
    downloadonly=False,
    uname=None,
    passwd=None,
    suffix='',
    get_support_data=False,
    varformat=None,
    varnames=[],
    notplot=False,
    time_clip=False,
    version=None,
    ror=True
):

    #===== Set parameters (1) =====#
    file_format = 'netcdf'
    remote_data_dir = ''
    local_path = ''
    prefix = ''
    file_res = 3600. * 24
    site_list = ['champ', 'cosmic']
    datatype_list = ['']
    parameter_list = ['']
    time_netcdf='time'
    #==============================#
    
    if site == 'champ':
        loaded_data = gps_champ_fsi_nc(trange, site ,datatype, parameter, no_update, downloadonly, uname,\
                                   passwd, suffix, get_support_data, varformat, varnames, notplot,\
                                    time_clip, version, ror)
    elif site == 'cosmic':
        loaded_data = gps_cosmic_fsi_nc(trange, site ,datatype, parameter, no_update, downloadonly, uname,\
                                   passwd, suffix, get_support_data, varformat, varnames, notplot,\
                                    time_clip, version, ror)
    return loaded_data