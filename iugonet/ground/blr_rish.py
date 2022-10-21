import pyspedas
import pytplot
from pytplot.MPLPlotter.tplot import tplot
import numpy as np
import datetime
import sys
from pyspedas.utilities.time_double import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, zlim,xlim
from iugonet.load import load
from ascii_to_tplot import ascii2tplot
def blr_rish(site=['ktb'],trange=['2010-09-01','2020-09-02']):
    
    sgk_start=datetime.datetime.strptime('1992-04-13','%Y-%m-%d')
    sgk_end=datetime.datetime.strptime('1992-08-29','%Y-%m-%d')
    tstart=datetime.datetime.strptime(trange[0],'%Y-%m-%d')
    tend=datetime.datetime.strptime(trange[1],'%Y-%m-%d')
    days=int((datetime.datetime.strptime(trange[1],'%Y-%m-%d').timestamp()-datetime.datetime.strptime(trange[0],'%Y-%m-%d').timestamp())/24/60/60)
    file_format = 'csv'
    site_list = ['ktb','sgk','srp']
    parameter_list1 = ['uwnd','vwnd','wwnd','pwr1','pwr2','pwr3','pwr4','pwr5','wdt1','wdt2','wdt3','wdt4','wdt5']
    parameter_list2=['uwnd','vwnd','wwnd','pwr1','pwr2','pwr3','wdt1','wdt2','wdt3']
    if site==['ktb']:
        sitename='kototabang'
        timeshift=(9-7)*60*60
        parameter_list=parameter_list1
    elif site==['sgk'] and sgk_start <= tstart and sgk_end >= tend:
        sitename='shigaraki'
        timeshift=(9-9)*60*60
        parameter_list=parameter_list2
    elif site==['sgk'] and (sgk_start > tstart or sgk_end < tend):
        print('TIME RANGE IS WRONG')
        sys.exit()
    elif site==['srp']:
        sitename='serpong'
        timeshift=(9-7)*60*60
        parameter_list=parameter_list2
    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/blr/'+sitename+'/data/data/ver02.0212/'
    local_path = 'rish'
    prefix = 'blr'
    file_res = 3600. * 24
    datatype_list = ['']
    time_netcdf=''
    days=days+1 # timeshift > 0 のため
    for i in range(len(parameter_list)):
        parameter=parameter_list[i]
        current_tplot_name='iug'+'_'+prefix+'_'+site[0]+'_'+parameter
        var_name=prefix+'_'+sitename+'_'+parameter+'norm'
        for j in range(days):
            time=tstart+datetime.timedelta(days=j)
            pathformat = time.strftime('%Y%m')+'/'+time.strftime('%Y%m%d')+'/'+time.strftime('%Y%m%d')+'.'+parameter+'.'+file_format
            sample_tplot_name=ascii2tplot(remote_data_dir=remote_data_dir,timeshift=timeshift,\
                                           pathformat=pathformat,prefix=prefix,sitename=sitename,parameter=parameter,file_format=file_format)
            if j != 0:
                store_data(current_tplot_name,data={'x':np.concatenate([get_data(current_tplot_name)[0],get_data(sample_tplot_name)[0]],0),
                                                    'y':np.concatenate([get_data(current_tplot_name)[1],get_data(sample_tplot_name)[1]],0),
                                                    'v':get_data(current_tplot_name)[2]})
            else:
                store_data(sample_tplot_name, newname=current_tplot_name)
            pytplot.store_data(var_name,delete=True) #元データの削除(ログに表示される)
        arr=get_data(current_tplot_name)[1]
        arr[arr==999.]=np.nan
        store_data(current_tplot_name, data={'x':get_data(current_tplot_name)[0], 'y':arr, 'v':get_data(current_tplot_name)[2]})
        start=tstart.timestamp()+9*60*60
        end=tend.timestamp()+9*60*60
        xlim(start , end) #他のplotをする際にも適応されてしまう
        options(current_tplot_name, 'spec',1)
        options(current_tplot_name, 'ytitle','BLR-'+site[0] +'\n Height \n [km]')
        if parameter=='uwnd'or parameter=='vwnd'or parameter=='wwnd':
            unit='[m/s]'
        elif parameter=='pwr1'or parameter=='pwr2'or parameter=='pwr3'or parameter=='pwr4'or parameter=='pwr5':
            unit='[dB]'
        else:
            unit='[m/s]'
        options(current_tplot_name, 'ztitle',parameter +'\n'+ unit)
    #**************************
    #Print of acknowledgement:
    #**************************
    print ('****************************************************************')
    print ('Acknowledgement')
    print ('****************************************************************')
    print ('If you acquire BLR data, we ask that you acknowledge us in your use')
    print ('of the data. This may be done by including text such as BLR data' )
    print ('provided by Research Institute for Sustainable Humanosphere of' )
    print ('Kyoto University. We would also appreciate receiving a copy of the') 
    print ('relevant publications. The distribution of BLR data has been partly')
    print ('supported by the IUGONET (Inter-university Upper atmosphere Global')
    print ('Observation NETwork) project (http://www.iugonet.org/) funded by the')
    print ('Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.')
