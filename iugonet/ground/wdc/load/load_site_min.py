import os
import numpy as np
from pyspedas.utilities.time_double import time_double
from pyspedas.utilities.time_string import time_string
from pytplot import store_data,tplot_names,options,get_data
import calendar
from .download.download_site import download_site
from .iug_load_gmag_wdc_acknowledgement import iug_wdc_ack as ack

def load_site_min(trange=['2011-1-1', '2011-1-2'],site='kak'):
    local_files =download_site(site=site,trange=trange,res="min")
    #print(local_files)
    site2=site.split(" ")
    res="min"
    for ss in range(len(site2)):
        local_files_2=[lfs for lfs in local_files if (site2[ss] == lfs[-11:-8])]
        if len(local_files_2)==0:
            print("ERROR:Can't Find site_",site2[ss],"data")
            continue
        #print(local_files_2)
        i=0
        dtype={'names':['npd','LONG','YR','MO','DA','E','HR','OBS','ORG','blank','data','HRly MEAN'],
                   'formats':['f8','f8','f8','f8','f8','1U','f8','3U','1U','9U','60f8','f8']}
        delimiter=[6,6,2,2,2,1,2,3,1,9]+60*[6]+[6]
        data=12*[0]
        for lf in local_files_2:
            buff=np.genfromtxt(lf,dtype=dtype,delimiter=delimiter,missing_values=9,filling_values=np.nan,unpack=True)
            if i==0:
                for j in range(12):
                    data[j]=list(buff[j])
            else:
                for j in range(12):
                    data[j]=data[j]+list(buff[j])
            i+=1
        #return data
        #time
        #print(data[3])
        t_1=trange[0][:4]+"-"+str(int(data[3][0]))+"-"+str(int(data[4][0]))
        #print(t_1)
        t_1=time_double(t_1)

        t0 = time_double(trange[0])
        t0 = t0 - np.mod(t0, 60)#only hour values are used
        t1 = time_double(trange[1])
        t1 = t1 - np.mod(t1, 60)
        t  = np.arange(t0, t1, 1)
        t  = t[np.mod(t, 60) == 0]

        start_time=int((t0-t_1)/60)
        end_time=start_time+len(t)

        #month
        du_mon=i
        #print(du_mon)
        #print(du_mon)#how many months u read
        start_year=int(trange[0][:4])
        start_mon=int(data[3][0])
        day_num=[]
        for j in range(du_mon):
            if(start_mon>12):
                start_year+=1
                start_mon=1
            day_num.append(calendar.monthrange(start_year,start_mon)[1])
            start_mon+=1
        #print(day_num)
        #print(sum(day_num))
        #makeing data array
        D_data=np.zeros((sum(day_num),24,60))#day,hour,min
        H_data=np.zeros((sum(day_num),24,60))
        X_data=np.zeros((sum(day_num),24,60))
        Y_data=np.zeros((sum(day_num),24,60))
        Z_data=np.zeros((sum(day_num),24,60))
        F_data=np.zeros((sum(day_num),24,60))
        I_data=np.zeros((sum(day_num),24,60))

        D_count=[0,1,0,0]#hour,day,mon,daynum
        H_count=[0,1,0,0]
        X_count=[0,1,0,0]
        Y_count=[0,1,0,0]
        Z_count=[0,1,0,0]
        I_count=[0,1,0,0]
        F_count=[0,1,0,0]
        #return data
        #print(len(data[3]))
        for l in range(len(data[5])):
            if(data[5][l]=="D"):
                D_count[0]+=1
                if(D_count[0]>24):
                    D_count[0]=1
                    D_count[1]+=1
                    D_count[3]+=1
                    if(D_count[1]>day_num[D_count[2]]):
                        D_count[1]=1
                        D_count[2]+=1
                D_data[D_count[3]][D_count[0]-1]=data[10][l]/600
            if(data[5][l]=="I"):
                I_count[0]+=1
                if(I_count[0]>24):
                    I_count[0]=1
                    I_count[1]+=1
                    I_count[3]+=1
                    if(I_count[1]>day_num[I_count[2]]):
                        I_count[1]=1
                        I_count[2]+=1
                I_data[I_count[3]][I_count[0]-1]=data[10][l]/600
            if(data[5][l]=="X"):
                X_count[0]+=1
                if(X_count[0]>24):
                    X_count[0]=1
                    X_count[1]+=1
                    X_count[3]+=1
                    if(X_count[1]>day_num[X_count[2]]):
                        X_count[1]=1
                        X_count[2]+=1
                X_data[X_count[3]][X_count[0]-1]=data[10][l]
            if(data[5][l]=="Y"):
                Y_count[0]+=1
                if(Y_count[0]>24):
                    Y_count[0]=1
                    Y_count[1]+=1
                    Y_count[3]+=1
                    if(Y_count[1]>day_num[Y_count[2]]):
                        Y_count[1]=1
                        Y_count[2]+=1
                Y_data[Y_count[3]][Y_count[0]-1]=data[10][l]
            if(data[5][l]=="Z"):
                Z_count[0]+=1
                if(Z_count[0]>24):
                    Z_count[0]=1
                    Z_count[1]+=1
                    Z_count[3]+=1
                    if(Z_count[1]>day_num[Z_count[2]]):
                        Z_count[1]=1
                        Z_count[2]+=1
                Z_data[Z_count[3]][Z_count[0]-1]=data[10][l]
            if(data[5][l]=="F"):
                F_count[0]+=1
                if(F_count[0]>24):
                    F_count[0]=1
                    F_count[1]+=1
                    F_count[3]+=1
                    if(F_count[1]>day_num[F_count[2]]):
                        F_count[1]=1
                        F_count[2]+=1
                F_data[F_count[3]][F_count[0]-1]=data[10][l]
            if(data[5][l]=="H"):
                H_count[0]+=1
                if(H_count[0]>24):
                    H_count[0]=1
                    H_count[1]+=1
                    H_count[3]+=1
                    if(H_count[1]>day_num[H_count[2]]):
                        H_count[1]=1
                        H_count[2]+=1
                H_data[H_count[3]][H_count[0]-1]=data[10][l]


        name=[]
        name2=[]
        clist=[]
        if(data[5].count("D")>1):
            cf=np.array(D_data)
            data_arr=cf.reshape(60*24*len(cf))
            #print(data_arr)
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_D")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
#            options(name[-1], "ysubtitle", "[degree]")
            options(name[-1], "legend_names","D[degree]")
            name2.append("D[degree]")
            options(name[-1], "Color", ['green'])
            clist.append("green")
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
        if(data[5].count("H")>1):
            cf=np.array(H_data)
            data_arr=cf.reshape(60*24*len(cf))
            #print(data_arr)
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_H")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            name2.append( "H[nT]")
            options(name[-1], "legend_names", "H[nT]")
            options(name[-1], "Color", ['blue'])
            clist.append('blue')
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
        if(data[5].count("I")>1):
            cf=np.array(I_data)
            data_arr=cf.reshape(60*24*len(cf))
            #print(data_arr)
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_I")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
            name2.append( "I[degree]")
            options(name[-1], "legend_names", "I[degree]")
            clist.append("magenta")
            options(name[-1], "Color", ['magenta'])
        if(data[5].count("X")>1):
            cf=np.array(X_data)
            data_arr=cf.reshape(60*24*len(cf))
            #print(data_arr)
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_X")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            options(name[-1], "legend_names", "X[nT]")
            name2.append("X[nT]")
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
            clist.append("cyan")
            options(name[-1], "Color", ["cyan"])
        if(data[5].count("Y")>1):
            cf=np.array(Y_data)
            data_arr=cf.reshape(60*24*len(cf))
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_Y")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            options(name[-1], "legend_names", "Y[nT]")
            name2.append("Y[nT]")
            options(name[-1], "Color", ["yellow"])
            clist.append("yellow")
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")   
        if(data[5].count("Z")>1):
            cf=np.array(Z_data)
            data_arr=cf.reshape(60*24*len(cf))
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_Z")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            options(name[-1], "legend_names","Z[nT]")
            name2.append("Z[nT]")
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
            options(name[-1], "Color", ["red"])
            clist.append("red")
        if(data[5].count("F")>1):
            cf=np.array(F_data)
            data_arr=cf.reshape(60*24*len(cf))
            name.append("wdc_mag_"+site2[ss]+"_1"+res+"_F")
            store_data(name[-1], data={'x':t, 'y':data_arr[start_time:end_time]},attr_dict={'acknowledgement':ack("site")})
            options(name[-1], "legend_names", "F[nT]")
            name2.append("F[nT]")
            options(name[-1], "ytitle", site2[ss] + os.linesep +"(1-min)")
            clist.append("black")
        data1=[]
        for na in name:
            data1.append([])
            data1[-1].extend(get_data(na)[1])
        data2=[e for e in zip (*data1)]
        name_site="wdc_mag_"+site2[ss]+"_1"+res
        store_data(name_site, data={'x':t, 'y':data2},attr_dict={'acknowledgement':ack("site")})
        options(name_site, "legend_names", name2)
        #options("site_"+res+'_'+site2[ss], "Color", ['black', 'red'])
        options(name_site, "ytitle", site2[ss]+os.linesep+"(1-min)")
        options(name_site, "Color", clist)
