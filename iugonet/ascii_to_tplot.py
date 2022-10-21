import pandas as pd
import numpy as np
import datetime
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, zlim

def ascii2tplot(remote_data_dir,
               pathformat,
               prefix,
               sitename,
               parameter,
               timeshift,
               file_format
               ):
    if file_format == 'csv':
        fpath = remote_data_dir + pathformat
        df = pd.read_csv(fpath, encoding='shiftJIS',dtype=str)
        v=np.zeros(len(df.columns)-1)
        for i in range(1,len(df.columns)):
            v[i-1]= float(df.columns[i])
        df1=df.iloc[:,0]
        time=np.zeros(len(df1))
        y=df.iloc[0:len(time),1:len(v)+1].to_numpy()
        for i in range(len(df1)):
            time[i]=datetime.datetime.strptime(df1[i],'%Y/%m/%d %H:%M').timestamp()+timeshift#jst補正
        ydata=np.zeros([len(y[:,0]),len(y[0,:])])
        for i in range(len(y[:,0])):
            for j in range(len(y[0,:])):
                ydata[i,j]=float(y[i,j])
        var_name=prefix+'_'+sitename+'_'+parameter+'norm'
        var_data=store_data(var_name, {'x': time,'y':ydata,'v':v})
        return var_name
    elif file_format == 'txt':
        print('seisakutyuu')
    else:
        print('wrong file format')
    
