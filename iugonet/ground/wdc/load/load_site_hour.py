
import numpy as np
from pyspedas.utilities.time_double import time_double
from pyspedas.utilities.time_string import time_string
from pytplot import store_data,tplot_names,get_data,options
from pytplot import tplot
import calendar
from .download.download_site import download_site

def load_site_hour(trange=['2011-1-1', '2011-1-2'],site='kak'):
    local_files =download_site(site=site,trange=trange,res="hour")
    #print(local_files)
    res="hour"
    site2=site.split(" ")
    for ss in range(len(site2)):
        local_files_2=[lfs for lfs in local_files if (site2[ss] in lfs)]
        if len(local_files_2)==0:
            print("Can't Find site_",site2[ss],"data")
            continue

        i=0
        dtype={'names':['OBS','ar','Mon','Com','day','blank','any','qdday','oldyear','standard','data','daily MEAN'],
                   'formats':['3U','f8','f8','1U','f8','2U','2U','1U','1U','f8','24f8','f8']}
        delimiter=[3,2,2,1,2,2,2,1,1,4]+24*[4]+[4]
        data=12*[0]
        for lf in local_files_2:
            buff=np.genfromtxt(lf,dtype=dtype,delimiter=delimiter,missing_values=9999,filling_values=np.nan,unpack=True)
            if i==0:
                for j in range(12):
                    data[j]=list(buff[j])
            else:
                #data=data+buff
                for j in range(12):
                    data[j]=data[j]+list(buff[j])
            i+=1

        #time
        t_1= trange[0][:4]+"-"+str(int(data[2][0]))+"-"+str(int(data[4][0]))
        #print(t_1)
        t_1= time_double(t_1)

        t0 = time_double(trange[0])
        t0 = t0 - np.mod(t0, 3600)#only hour values are used
        t1 = time_double(trange[1])
        t1 = t1 - np.mod(t1, 3600)
        t  = np.arange(t0, t1, 1)
        t  = t[np.mod(t, 3600) == 0]

        start_time=int((t0-t_1)/3600)
        end_time=start_time+len(t)

        #month
        du_mon=i
        #print(du_mon)#how many months u read
        start_year=int(trange[0][:4])
        start_mon=int(data[2][0])
        day_num=[]
        for j in range(du_mon):
            if(start_mon>12):
                start_year+=1
                start_mon=1
            day_num.append(calendar.monthrange(start_year,start_mon)[1])
            start_mon+=1


        #makeing data array
        D_data=np.zeros((sum(day_num),24))
        H_data=np.zeros((sum(day_num),24))
        X_data=np.zeros((sum(day_num),24))
        Y_data=np.zeros((sum(day_num),24))
        Z_data=np.zeros((sum(day_num),24))
        F_data=np.zeros((sum(day_num),24))
        I_data=np.zeros((sum(day_num),24))

        D_count=[0,0,-1]#day,mon,num
        H_count=[0,0,-1]
        X_count=[0,0,-1]
        Y_count=[0,0,-1]
        Z_count=[0,0,-1]
        I_count=[0,0,-1]
        F_count=[0,0,-1]

        #print(len(data[3]))
        for l in range(len(data[3])):
            if(data[3][l]=="D"):
                D_count[0]+=1
                if(D_count[0]>day_num[D_count[1]]):
                    D_count[0]=0
                    D_count[1]+=1
                D_count[2]+=1
                D_data[D_count[2]]=data[10][l]/600+data[9][l]
            if(data[3][l]=="H"):
                H_count[0]+=1
                if(H_count[0]>day_num[H_count[1]]):
                    H_count[0]=0
                    H_count[1]+=1
                H_count[2]+=1
                H_data[H_count[2]]=data[10][l]+100*data[9][l]
            if(data[3][l]=="I"):
                I_count[0]+=1
                if(I_count[0]>day_num[I_count[1]]):
                    I_count[0]=0
                    I_count[1]+=1
                I_count[2]+=1
                I_data[I_count[2]]=data[10][l]/600+data[9][l]
            if(data[3][l]=="X"):
                X_count[0]+=1
                if(X_count[0]>day_num[X_count[1]]):
                    X_count[0]=0
                    X_count[1]+=1
                X_count[2]+=1
                X_data[X_count[2]]=data[10][l]+100*data[9][l]
            if(data[3][l]=="Y"):
                Y_count[0]+=1
                if(Y_count[0]>day_num[Y_count[1]]):
                    Y_count[0]=0
                    Y_count[1]+=1
                Y_count[2]+=1
                Y_data[Y_count[2]]=data[10][l]+100*data[9][l]
            if(data[3][l]=="Z"):
                Z_count[0]+=1
                if(Z_count[0]>day_num[Z_count[1]]):
                    Z_count[0]=0
                    Z_count[1]+=1
                Z_count[2]+=1
                Z_data[Z_count[2]]=data[10][l]+100*data[9][l]
            if(data[3][l]=="F"):
                F_count[0]+=1
                if(F_count[0]>day_num[F_count[1]]):
                    F_count[0]=0
                    F_count[1]+=1
                F_count[2]+=1
                F_data[F_count[2]]=data[10][l]+100*data[9][l]

        #store data
        name=[]
        if(data[3].count("D")>1):
            cf=np.array(D_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_D")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
            options(name[-1], "ysubtitle", "(degree)")
        if(data[3].count("H")>1):
            cf=np.array(H_data)
            data_arr=cf.reshape(24*len(cf))
                #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_H")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
        if(data[3].count("I")>1):
            cf=np.array(I_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_I")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
            options(name[-1], "ysubtitle", "(degree)")
        if(data[3].count("X")>1):
            cf=np.array(X_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_X")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
        if(data[3].count("Y")>1):
            cf=np.array(Y_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_Y")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
        if(data[3].count("Z")>1):
            cf=np.array(Z_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_Z")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})
        if(data[3].count("F")>1):
            cf=np.array(F_data)
            data_arr=cf.reshape(24*len(cf))
            #print(data_arr)
            name.append("site_"+res+'_'+site2[ss]+"_F")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]})

        #tplot_names()
        #store_data("site_"+res+'_'+site2[ss], data=["site_hour_kak_D","site_hour_kak_H"])
        data1=[]
        for na in name:
            data1.append([])
            data1[-1].extend(get_data(na)[1])
        print(len(data1))
        data2=[e for e in zip (*data1)]
        store_data("site_"+res+'_'+site2[ss], data={'x':t, 'y':data2})
        options("site_"+res+'_'+site2[ss], "legend_names", name)
        #options("site_"+res+'_'+site2[ss], "Color", ['black', 'red'])
        options("site_"+res+'_'+site2[ss], "ytitle", "site_"+res+'_'+site2[ss])
        options("site_"+res+'_'+site2[ss], "ysubtitle", "(nT)")
        
    tplot_names()
