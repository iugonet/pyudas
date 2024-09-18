import pandas as pd
import numpy as np

def load_ascii_format2(data, time_datenum, time_datetime):
    data_new = []
    time_datenum_new = []
    time_datetime_new = []

    nfile = len(time_datenum)

    for i in range(nfile):
        # Pick up the same time data.
        # (Caution!) time data will be sorted.
        unique_time, ia, ic = np.unique(np.array(time_datenum[i]), return_index=True, return_inverse=True)
        data_tmp = data[i, :]
        sx = np.shape(np.array(data_tmp))[1]
        # Separate data per unique time
        unique_time_num = len(unique_time)
        for j in range(unique_time_num):
            for k in range(sx):
                idx = np.where(ic == j)
                tmp = data[i, k]
                data_tmp[j, k] = tmp[idx]
        # Connect data into matrix
        data_tmp_new = data_tmp[0, :]
        for k in range(sx):
            max_row = 0
            tmprow = np.zeros([unique_time_num, 1])
            for j in range(unique_time_num):
                tmprow[j] = len(data_tmp[j, k])
                if tmprow[j] > max_row:
                    max_row = tmprow[j]
            ydata_k = np.zeros([unique_time_num, max_row])
            ydata_k[:, :] = np.nan
            for j in range(unique_time_num):
                data_tmp0 = data_tmp[j, k]
                ydata_k[j, 0:tmprow[j]]
            data_tmp_new[0, k] = ydata_k
    
        data_new.append(data_tmp_new)
        try:
            time_datenum_new.extend(unique_time)
        except:
            time_datenum_new.append(unique_time)
        try:
            time_datetime_new.extend(time_datetime[i][ia]) 
        except:
            time_datetime_new.append(time_datetime[i][ia])
    
    return data_new, time_datenum_new, time_datetime_new