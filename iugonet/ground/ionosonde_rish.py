import pyspedas
import pytplot
from pytplot.MPLPlotter.tplot import tplot
import numpy as np
import datetime
import sys
# from pyspedas.utilities.time_double import time_double
# from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, zlim,xlim
# from iugonet.load import load
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load
#from ascii_to_tplot import ascii2tplot
def ionosonde_rish(site=['sgk'],
                   trange=['2001-01-18','2023-01-14'],
                   datatype='',
                   parameter='',
                   notplot=False,
                   no_update=False):
    #===== Set parameters (1) =====#
    file_format = 'txt'
    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/mudb/data/ionosonde/text/'
    local_path = 'rish/'
    prefix = 'rish_'
    file_res = 900.
    site_list = ['sgk']
    datatype_list = ['']
    parameter_list = ['']
    #==============================#
    
    # Check input parameters
    # site
    if isinstance(site, str):
        st_list = site.lower()
        st_list = st_list.split(' ')
    elif isinstance(site, list):
        st_list = []
        for i in range(len(site)):
            st_list.append(site[i].lower())
    if 'all' in st_list:
        st_list = site_list
    st_list = list(set(st_list).intersection(site_list))

    # datatype
    if isinstance(datatype, str):
        dt_list = datatype.lower()
        dt_list = dt_list.split(' ')
    elif isinstance(datatype, list):
        dt_list = []
        for i in range(len(datatype)):
            dt_list.append(datatype[i].lower())
    if 'all' in dt_list:
        dt_list = datatype_list
    dt_list = list(set(dt_list).intersection(datatype_list))

    # parameter
    if isinstance(parameter, str):
        pr_list = parameter.lower()
        pr_list = pr_list.split(' ')
    elif isinstance(parameter, list):
        pr_list = []
        for i in range(len(parameter)):
            pr_list.append(parameter[i].lower())
    if 'all' in pr_list:
        pr_list = parameter_list
    pr_list = list(set(pr_list).intersection(parameter_list))
    
    if notplot:
        loaded_data = {}
    else:
        loaded_data = []

#     for st in st_list:
#         print(st)		
#         if len(st) < 1:
#             varname_st = ''
#         else:
#             varname_st = st 

#         for dt in dt_list:
#             if len(dt) < 1:
#                 varname_st_dt = varname_st
#             else:
#                 varname_st_dt = varname_st+'_'+dt
                
#             for pr in pr_list:
#                 print(pr)
#                 if len(pr) < 1:
#                     varname_st_dt_pr = varname_st_dt
#                 else:
#                     varname_st_dt_pr = varname_st_dt+'_'+pr
				
#                 if len(varname_st_dt_pr) > 0:
#                     suffix = '_'+varname_st_dt_pr

#                 #===== Set parameters (2) =====#
#                 pathformat = '/%Y/&Y&m/%Y%m%d/%Y%m%d_ionogram.txt'
#                 #==============================#

#                 loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
#                     pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
#                     local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
#                     uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
#                     get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
#                     notplot=notplot, time_clip=time_clip, version=version, \
#                     file_format=file_format, time_netcdf=time_netcdf)
            
#                 if notplot:
#                     loaded_data.update(loaded_data_temp)
#                 else:
#                     loaded_data += loaded_data_temp
					
#                 if (len(loaded_data_temp) > 0) and ror:
#                     try:
#                         if isinstance(loaded_data_temp, list):
#                             if downloadonly:
#                                 cdf_file = cdflib.CDF(loaded_data_temp[-1])
#                                 gatt = cdf_file.globalattsget()
#                             else:
#                                 gatt = get_data(loaded_data_temp[-1], metadata=True)['CDF']['GATT']
#                         elif isinstance(loaded_data_temp, dict):
#                             gatt = loaded_data_temp[list(loaded_data_temp.keys())[-1]]['CDF']['GATT']
#                         print('**************************************************************************')
#                         print(gatt["Logical_source_description"])
#                         print('')
#                         print(f'Information about {gatt["Station_code"]}')
#                         print(f'PI :{gatt["PI_name"]}')
#                         print('')
#                         print(f'Affiliations: {gatt["PI_affiliation"]}')
#                         print('')
#                         print('Rules of the Road for NIPR Fluxgate Magnetometer Data:')
#                         print('')
#                         print(gatt["TEXT"])
#                         print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
#                         print('**************************************************************************')
#                     except:
#                         print('printing PI info and rules of the road was failed')
                
#                 if (not downloadonly) and (not notplot):
#                     '''
#                     #===== Remove tplot variables =====#
#                     current_tplot_name = prefix+'epoch'
#                     if current_tplot_name in loaded_data:
#                         store_data(current_tplot_name, delete=True)
#                         loaded_data.remove(current_tplot_name)
#                     #===== Rename tplot variables and set options =====#
#                     current_tplot_name = prefix+'db_dt'
#                     if current_tplot_name in loaded_data:
#                         get_data_vars = get_data(current_tplot_name)
#                         if get_data_vars is None:
#                             store_data(current_tplot_name, delete=True)
#                         else:
#                             #;--- Rename
#                             new_tplot_name = prefix+'imag'+suffix
#                             store_data(current_tplot_name, newname=new_tplot_name)
#                             loaded_data.remove(current_tplot_name)
#                             loaded_data.append(new_tplot_name)
#                             #;--- Missing data -1.e+31 --> NaN
#                             clip(new_tplot_name, -1e+5, 1e+5)
#                             get_data_vars = get_data(new_tplot_name)
#                             ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
#                             #;--- Labels
#                             options(new_tplot_name, 'legend_names', ['X','Y','Z'])
#                             options(new_tplot_name, 'Color', ['b', 'g', 'r'])
#                             options(new_tplot_name, 'ytitle', st.upper())
#                             options(new_tplot_name, 'ysubtitle', '[V]')
#                     '''

#     return loaded_data
# #     tstart=datetime.datetime.strptime(trange[0],'%Y-%m-%d')
# #     tend=datetime.datetime.strptime(trange[1],'%Y-%m-%d')
# #     days=int((datetime.datetime.strptime(trange[1],'%Y-%m-%d').timestamp()-datetime.datetime.strptime(trange[0],'%Y-%m-%d').timestamp())/24/60/60)
# #     file_format = 'csv'
# #     site_list = ['ktb','sgk','srp']
# #     parameter_list1 = ['uwnd','vwnd','wwnd','pwr1','pwr2','pwr3','pwr4','pwr5','wdt1','wdt2','wdt3','wdt4','wdt5']
# #     parameter_list2=['uwnd','vwnd','wwnd','pwr1','pwr2','pwr3','wdt1','wdt2','wdt3']
# #     if site==['ktb']:
# #         sitename='kototabang'
# #         timeshift=(9-7)*60*60
# #         parameter_list=parameter_list1
# #     elif site==['sgk'] and sgk_start <= tstart and sgk_end >= tend:
# #         sitename='shigaraki'
# #         timeshift=(9-9)*60*60
# #         parameter_list=parameter_list2
# #     elif site==['sgk'] and (sgk_start > tstart or sgk_end < tend):
# #         print('TIME RANGE IS WRONG')
# #         sys.exit()
# #     elif site==['srp']:
# #         sitename='serpong'
# #         timeshift=(9-7)*60*60
# #         parameter_list=parameter_list2
# #     remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/blr/'+sitename+'/data/data/ver02.0212/'
# #     local_path = 'rish'
# #     prefix = 'blr'
# #     file_res = 3600. * 24
# #     datatype_list = ['']
# #     time_netcdf=''
# #     days=days+1 # timeshift > 0 のため
# #     for i in range(len(parameter_list)):
# #         parameter=parameter_list[i]
# #         current_tplot_name='iug'+'_'+prefix+'_'+site[0]+'_'+parameter
# #         var_name=prefix+'_'+sitename+'_'+parameter+'norm'
# #         for j in range(days):
# #             time=tstart+datetime.timedelta(days=j)
# #             pathformat = time.strftime('%Y%m')+'/'+time.strftime('%Y%m%d')+'/'+time.strftime('%Y%m%d')+'.'+parameter+'.'+file_format
# #             sample_tplot_name=ascii2tplot(remote_data_dir=remote_data_dir,timeshift=timeshift,\
# #                                            pathformat=pathformat,prefix=prefix,sitename=sitename,parameter=parameter,file_format=file_format)
# #             if j != 0:
# #                 store_data(current_tplot_name,data={'x':np.concatenate([get_data(current_tplot_name)[0],get_data(sample_tplot_name)[0]],0),
# #                                                     'y':np.concatenate([get_data(current_tplot_name)[1],get_data(sample_tplot_name)[1]],0),
# #                                                     'v':get_data(current_tplot_name)[2]})
# #             else:
# #                 store_data(sample_tplot_name, newname=current_tplot_name)
# #             pytplot.store_data(var_name,delete=True) #元データの削除(ログに表示される)
# #         arr=get_data(current_tplot_name)[1]
# #         arr[arr==999.]=np.nan
# #         store_data(current_tplot_name, data={'x':get_data(current_tplot_name)[0], 'y':arr, 'v':get_data(current_tplot_name)[2]})
# #         start=tstart.timestamp()+9*60*60
# #         end=tend.timestamp()+9*60*60
# #         xlim(start , end) #他のplotをする際にも適応されてしまう
# #         options(current_tplot_name, 'spec',1)
# #         options(current_tplot_name, 'ytitle','BLR-'+site[0] +'\n Height \n [km]')
# #         if parameter=='uwnd'or parameter=='vwnd'or parameter=='wwnd':
# #             unit='[m/s]'
# #         elif parameter=='pwr1'or parameter=='pwr2'or parameter=='pwr3'or parameter=='pwr4'or parameter=='pwr5':
# #             unit='[dB]'
# #         else:
# #             unit='[m/s]'
# #         options(current_tplot_name, 'ztitle',parameter +'\n'+ unit)
# #     #**************************
# #     #Print of acknowledgement:
# #     #**************************
# #     print ('****************************************************************')
# #     print ('Acknowledgement')
# #     print ('****************************************************************')
# #     print ('If you acquire BLR data, we ask that you acknowledge us in your use')
# #     print ('of the data. This may be done by including text such as BLR data' )
# #     print ('provided by Research Institute for Sustainable Humanosphere of' )
# #     print ('Kyoto University. We would also appreciate receiving a copy of the') 
# #     print ('relevant publications. The distribution of BLR data has been partly')
# #     print ('supported by the IUGONET (Inter-university Upper atmosphere Global')
# #     print ('Observation NETwork) project (http://www.iugonet.org/) funded by the')
# #     print ('Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.')
