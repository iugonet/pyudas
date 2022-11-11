import os
import numpy as np
from pyspedas.utilities.time_double import time_double
from pyspedas.utilities.time_string import time_string
from pytplot import store_data,tplot_names, options
from .download.download_dst import download_dst
from .iug_load_gmag_wdc_acknowledgement import iug_wdc_ack as ack
def load_dst(trange=['2011-1-1', '2011-1-2'],level="final"):
    """


    """
    local_files =download_dst(trange,level)
    if len(local_files)==0:
            print("Can't Find file!")
            return
    i=0
    dtype = {'names':['dst','ar','mon','index1','day','RR','index','ver','ye','standard','data','ave'],
             'formats':['<3U','<i8','<i8','<1U','<i8','2U','<1U','<1U','<i8','<i8','24<i8','<i8']}
    delimiter=[3,2,2,1,2,2,1,1,2,4]+24*[4]+[4]
    for lf in local_files:
        buff=np.genfromtxt(lf,dtype=dtype,delimiter=delimiter,missing_values=9999,filling_values=np.nan,unpack=True)
        if i==0:
            data=buff
          #  print(i)
        else:
            for j in range(12):
                data[j]=list(data[j])+list(buff[j])
            #data=np.concatenate((buff,data),axis=0)
            #data=data+buff
        i+=1
        #print(data)
        #for i in range(12):
        #data[i]=data[i]+buff[i]
    # time
    t_1=str(data[8][0])+str(data[1][0])+"-"+str(data[2][0])+"-"+str(data[4][0])
    t_1=time_double(t_1)
    t0 = time_double(trange[0])
    t0 = t0 - np.mod(t0, 3600)#only hour values are used
    t1 = time_double(trange[1])
    t1 = t1 - np.mod(t1, 3600)
    t  = np.arange(t0, t1, 1)
    t  = t[np.mod(t, 3600) == 0]
    #tplot
    data_arr=np.array(data[10])
    data_arr=data_arr.reshape(24*len(data[10]))
    start_time=int((t0-t_1)/3600)
    end_time=start_time+len(t)
    if(int(data[7][0])==2 or data[7][0]==" "):
        name="dst"
    elif(int(data[7][0])==1):
        name="pvdst"
    elif(int(data[7][0])>2):
        name="moddst"
    else:
        name="dstRR"

    name = 'wdc_mag_dst' + '_' + level
    store_data(name, data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("dst")})
    options(name, "ytitle", "Dst" + os.linesep + level)
    options(name, "ysubtitle", "[nT]")


    if (level=='all'):
        lev_int=len(data[10])
        #print(lev_int)
        start_time=int((t0-t_1)/3600)+lev_int*12
        end_time=start_time+len(t)
        if(int(data[7][lev_int-1])==2 or data[7][lev_int-1]==" "):
            name="dst"
        elif(int(data[7][lev_int-1])==1):
            name="pvdst"
        elif(int(data[7][lev_int-1])>2):
            name="moddst"
        else:
            name="dstRR"
        #
        name = 'wdc_mag_dst' + '_' + level
        store_data(name, data={'x':t, 'y':data_arr[start_time:end_time]})
        #
        options(name, "ytitle", 'Dst' + os.linesep + level)
        options(name, "ysubtitle", '[nT]')
