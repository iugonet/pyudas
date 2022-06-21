
import numpy as np
from pyspedas.utilities.time_double import time_double
from pyspedas.utilities.time_string import time_string
from pyspedas.utilities.dailynames  import dailynames
from pytplot import store_data, options
from pytplot import tplot
from pytplot import tplot_names

from .download.download_ae_min import download_ae_min




def load_hour(local_file):


    ### format
    names = ['head', 'year', 'month', 'day', 'index0', 'hour', 'index1', 'version']
    names += [ 'sec' + str(sec).zfill(2) for sec in range(60) ]
    names += ['hourly']
    #
    formats = ['<U12', '<U2', '<U2', '<U2', '<U1', '<U2', '<U3', '<U10'] + ['f8']*61
    #
    delimiter = [12, 2, 2, 2, 1, 2, 3, 10] + [6]*61
    #
    dtype = {'names':names, 'formats':formats}



    ###
    data = np.zeros(0, dtype='i8')
    t    = np.zeros(0, dtype='i8')

    for lf in local_file :

        year  = lf[-11:-7]
        month = lf[-2:]
        buff = np.genfromtxt(lf, dtype=dtype, delimiter=delimiter, missing_values='99999',
                             filling_values=np.nan, unpack=True)
        #
        data   = np.append(data, buff[-1])
        #
        t_buff = [ year + '-' + month + '-' + day + ' ' + hr + ':29:30'   # 00:29:30
                   for (day, hr) in zip(buff[3], buff[5]) ]

        t = np.append(t, t_buff)


    t    = time_double(t)
    data = data[ np.argsort(t) ]
    t    = np.sort(t)

    return t, data




def load_ae_hour(trange, level='provisional') :

    """
    data format of 1 minute resolusion AE index is described in
    http://wdc.kugi.kyoto-u.ac.jp/aeasy/format/aeformat.html
    """

    ### download
    local_file    = download_ae_min(trange=trange, level=level)

    if len(local_file)==0:
        print("We could not download the data Please check your command")
        return 0
    ### AE
    local_file_ae = [ lf for lf in local_file if lf[-6:-4] == 'ae' ]   # aeYYMM
    t, data       = load_hour(local_file_ae)
    store_data("AE_min", data={'x':t, 'y':data})

    for i in range(24) :
        print( time_string(t[i]), data[i] )


    ### AL
    local_file_al = [ lf for lf in local_file if lf[-6:-4] == 'al' ]   # alYYMM
    t, data       = load_hour(local_file_al)
    store_data("AL_min", data={'x':t, 'y':data})



    ### AO
    local_file_ao = [ lf for lf in local_file if lf[-6:-4] == 'ao' ]   # aoYYMM
    t, data       = load_hour(local_file_ao)
    store_data("AO_min", data={'x':t, 'y':data})



    ### AU
    local_file_au = [ lf for lf in local_file if lf[-6:-4] == 'au' ]   # auYYMM
    t, data       = load_hour(local_file_au)
    store_data("AU_min", data={'x':t, 'y':data})

    tplot_names()
    return True
