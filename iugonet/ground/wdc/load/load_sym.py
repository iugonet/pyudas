import calendar
import numpy as np
from pyspedas.utilities.time_double import time_double
from pyspedas.utilities.time_string import time_string
from pyspedas.utilities.dailynames  import dailynames
from pytplot import store_data, options, del_data,get_data
from pytplot import tplot, tplot_names
from .download.download_sym import download_sym
from .iug_load_gmag_wdc_acknowledgement import iug_wdc_ack as ack

def load_sym(trange) :


    ### read data
    local_files = download_sym(trange)
    if len(local_files)==0:
            print("Could not find file!")
            return
    #
    names    = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8']
    names    = names + ['s' + str(i+1) for i in range(61)]
    formats0 = ['U']*8
    formats1 = ['f8'] * 61
    formats  = formats0 + formats1
    dtype    = {'names':names, 'formats': formats}
    #
    delimiter = [12, 2, 2, 2, 1, 2, 3, 10] + [6]*61
    #
    sym_d = np.zeros(0, dtype='f8')
    sym_h = np.zeros(0, dtype='f8')


    for lf in local_files:

        buff = np.genfromtxt(lf, dtype=dtype, missing_values='99999', delimiter=delimiter,
		                     filling_values=np.nan, unpack=True)

        l     = len(buff[0])         # (hours of month) x 4
        size  = int( l/4*60 )        # minutes of month, 4:SYM-H, SYM-D, ASY-H, ASY-D
        sym_d_month = np.zeros(size)
        sym_h_month = np.zeros(size)

        for minute in range(60):
            buff_sym_d  = buff[minute + 8][ [i for i in range(l) if 48 <= (i % 96) < 72] ]
            buff_sym_h  = buff[minute + 8][ [i for i in range(l) if 72 <= (i % 96) < 96] ]
            #
            sym_d_month[ [i for i in range(size) if i % 60 == minute] ] = buff_sym_d
            sym_h_month[ [i for i in range(size) if i % 60 == minute] ] = buff_sym_h

        sym_d = np.append(sym_d, sym_d_month)
        sym_h = np.append(sym_h, sym_h_month)



    ### convert to tplot variables
    ## time
    fmt   = '%Y-%m-%d'
    date  = dailynames(trange=trange, file_format=fmt)
    # start date   'YYYY-MM-01'
    t0 = time_double( date[0][0:8] + '01' )
    # end date     'YYYY-MM-dd' -> 'YYYY-MM-31 23:59:59'
    days = calendar.monthrange(int(date[-1][0:4]), int(date[-1][5:7]))[1]
    t1   = time_double( date[-1][0:8] + str(days) + ' 23:59:59' )
    #
    t = np.arange(t0, t1, 60)


    ## store SYM-H and SYM-D
    name_sym_h = "wdc_mag_sym_h" 
    name_sym_d = "wdc_mag_sym_d" 
    store_data(name_sym_h, data={'x':t, 'y':sym_h},attr_dict={'acknowledgement':ack("sym")})
    store_data(name_sym_d, data={'x':t, 'y':sym_d},attr_dict={'acknowledgement':ack("sym")})
    #
    time1, data1 = get_data(name_sym_h)
    time2, data2 = get_data(name_sym_d)
    #
    #
    ## store SYM
    name_sym = "wdc_mag_sym"
    data3=[e for e in zip(data1,data2)]
    store_data(name_sym, data={'x':time1, 'y':data3},attr_dict={'acknowledgement':ack("sym")})
    #
    options(name_sym, "legend_names", ["SYM-H", "SYM-D"])
    options(name_sym, "Color", ['black', 'red'])
    options(name_sym, "ytitle", "SYM")
    options(name_sym, "ysubtitle", "[nT]")
    #
    del_data(name_sym_h)
    del_data(name_sym_d)

    return True
