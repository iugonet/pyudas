
import numpy as np 
import calendar
from datetime import datetime
from pyspedas.utilities.time_double import time_double  
from pyspedas.utilities.time_string import time_string  
from pyspedas.utilities.dailynames  import dailynames  
from pytplot import store_data, options
from .iug_load_gmag_wdc_acknowledgement import iug_wdc_ack as ack
from .download.download_wp_index import download_wp_index
 


def load_wp_index(trange):
    #
    local_files =download_wp_index(trange)
    if len(local_files)==0:
            print("Could not find file!")
            return
    i = 0
    dtype = { 
              'names':['hour', 'minute', 'wp_index', 'kak', 'lrm', 'wmq', 'izn', 
                       'fur', 'ebr', 'tdc', 'sjg', 'tuc', 'hon', 'cnb', 'n'], 
              'formats':['<i8', '<i8', '<f8', '<f8', '<f8', '<f8', '<f8', '<f8', 
                         '<f8', '<f8', '<f8', '<f8', '<f8', '<f8', '<i8']
	    }


    for lf in local_files:
        buff = np.genfromtxt(lf, dtype=dtype, skip_header=2, missing_values='999.00', 
                             filling_values=np.nan, unpack=True)
        if i == 0 :
            data = buff
            i += 1
        else :
            data = np.concatenate([data, buff], 1)


    ## convert to tplot variables
    # time
    t0 = time_double(trange[0])
    t0 = t0 - np.mod(t0, 86400.)
    t1 = time_double(trange[1])
    if np.mod(t1, 86400) != 0 :
        t1 = t1 - np.mod(t1, 86400.) + 86400.

    t  = np.arange(t0, t1, 1)
    t  = t[np.mod(t, 60) == 0]

    # data
    tname = "wdc_mag_Wp_index"
    store_data(tname, data={'x':t, 'y':data[2]},attr_dict={'acknowledgement':ack("wp")})
    options(tname, 'ytitle', 'WDC_Wp')
    options(tname, 'ysubtitle', '[nT]')
    #
    # station
    tname = "wdc_mag_Wp_nstn"
    store_data(tname, data={'x':t, 'y':data[-1]},attr_dict={'acknowledgement':ack("wp")})
    options(tname, 'ytitle', 'WDC_Wp_nstn')
    options(tname, 'ysubtitle', '')

    return True
