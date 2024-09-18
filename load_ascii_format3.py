import pandas as pd
import numpy as np

def load_ascii_format3(data, time_datenum, time_datetime):
    data_new = []
    time_datenum_new = []
    time_datetime_new = []

    nfile = len(time_datenum)

    for i in range(nfile):
        data_tmp = data[i]
        # ydata = np.array(data_tmp)
        # data_new.append(ydata)
        data_new.append(list(data_tmp))

    time_datenum_new = time_datenum
    time_datetime_new = time_datetime

    return data_new, time_datenum_new, time_datetime_new