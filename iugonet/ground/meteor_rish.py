import numpy as np
import pytplot
# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def meteor_rish(
    trange=['1983-10-01', '1983-10-02'],
    site='sgk',
    datatype='',
	parameter='all',
    no_update=False,
    downloadonly=False,
    uname=None,
    passwd=None,
	suffix='',
    get_support_data=False,
    varformat=None,
    varnames=[],
    notplot=False,
    time_clip=False,
    version=None,
    ror=True
):

    #===== Set parameters (1) =====#
    file_format = 'netcdf'
    #local_path = 'rish/misc/'
    prefix = 'iug_meteor_'
    file_res = 3600. * 24
    site_list = ['bik', 'ktb', 'sgk', 'srp']
    datatype_list = ['']
    parameter_list = ['h2t60min00', 'h2t60min30', 'h4t60min00', 'h4t60min30', 'h4t240min00']
    time_netcdf='time'
    specvarname='range'
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
    print(pr_list)
    
    if notplot:
        loaded_data = {}
    else:
        loaded_data = []

    for st in st_list:
        print(st)		
        if len(st) < 1:
            varname_st = ''
        else:
            varname_st = st 

        for dt in dt_list:
            print(dt)
            if len(dt) < 1:
                varname_st_dt = varname_st
            else:
                varname_st_dt = varname_st+'_'+dt
                
            for pr in pr_list:
                print(pr)
                if len(pr) < 1:
                    varname_st_dt_pr = varname_st_dt
                else:
                    varname_st_dt_pr = varname_st_dt+'_'+pr
				
                if len(varname_st_dt_pr) > 0:
                    suffix = '_'+varname_st_dt_pr

                pr1=pr[0:2]+'km_'+pr[2:]
                print(pr1)

                if st == 'sgk':
                    dtrange=np.array(time_double(trange))+9*3600
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/mudb/data/mwr/'
                    pathformat = 'nc/ver1_0/'+pr1+'/%Y/Ws%Y%m%d.'+pr+'.nc'
                elif st == 'bik':
                    dtrange=np.array(time_double(trange))+0*3600
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/biak/'
                    pathformat = 'nc/ver1_0/'+pr1+'/%Y/Wb%Y%m%d.'+pr+'.nc'
                elif st == 'ktb':
                    dtrange=np.array(time_double(trange))+0*3600
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/kototabang/'
                    pathformat = 'nc/ver1_1_2/'+pr1+'/%Y/Wk%Y%m%d.'+pr+'.nc'
                elif st == 'srp':
                    dtrange=np.array(time_double(trange))+7*3600
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/serpong/'
                    pathformat = 'nc/ver1_0_2/'+pr1+'/%Y/jkt%Y%m%d.'+pr+'.nc'

                local_path = 'rish/misc/'+st+'/meteor'

                loaded_data_temp = load(trange=dtrange, site=st, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                    get_support_data=get_support_data, varformat=varformat, specvarname=specvarname, varnames=varnames, \
                    notplot=notplot, time_clip=time_clip, version=version, \
                    file_format=file_format, time_netcdf=time_netcdf)
            
                if notplot:
                    loaded_data.update(loaded_data_temp)
                else:
                    loaded_data += loaded_data_temp
					
                if (len(loaded_data_temp) > 0) and ror:
                    try:
                        if isinstance(loaded_data_temp, list):
                            if downloadonly:
                                cdf_file = cdflib.CDF(loaded_data_temp[-1])
                                gatt = cdf_file.globalattsget()
                            else:
                                gatt = get_data(loaded_data_temp[-1], metadata=True)['CDF']['GATT']
                        elif isinstance(loaded_data_temp, dict):
                            gatt = loaded_data_temp[list(loaded_data_temp.keys())[-1]]['CDF']['GATT']
                        print('**************************************************************************')
                        print(gatt["Logical_source_description"])
                        print('')
                        print(f'Information about {gatt["Station_code"]}')
                        print(f'PI :{gatt["PI_name"]}')
                        print('')
                        print(f'Affiliations: {gatt["PI_affiliation"]}')
                        print('')
                        print('Rules of the Road for NIPR Fluxgate Magnetometer Data:')
                        print('')
                        print(gatt["TEXT"])
                        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
                        print('**************************************************************************')
                    except:
                        #print('printing PI info and rules of the road was failed')                
                     
                        print('************************************************************************** \n' \
                              +  'Note: If you would like to use following data for scientific purpose, please read and follow the DATA USE POLICY \n' \
                        + '(http://database.rish.kyoto- u.ac.jp/arch/iugonet/data_policy/Data_Use_Policy_e.html \n' \
                        + 'The distribution of meteor wind radar data has been partly supported by the IUGONET (Inter-university Upper \n' \
                        + 'atmosphere Global Observation NETwork) project (http://www.iugonet.org/) funded \n' \
                        + 'by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan. \n' \
                        + '**************************************************************************')

                #print(loaded_data_temp)
                
                if (not downloadonly) and (not notplot):
                    '''
				    clip(tplot_name, -1e+4, 1e+4)
                    ylim(tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
                    options(tplot_name, 'legend_names', ['H','D','Z'])
                    options(tplot_name, 'Color', ['b', 'g', 'r'])
                    options(tplot_name, 'ytitle', '\n'.join(tplot_name.split('_')))
                    '''
                    # SysLab(1)-----
                    #===== Remove tplot variables =====#
                    if ('iug_meteor_range_'+site+'_'+pr in loaded_data_temp) or ('iug_meteor_time_'+site+'_'+pr in loaded_data_temp):
                        store_data('iug_meteor_time_'+site+'_'+pr, delete=True)
                        loaded_data.remove('iug_meteor_time_'+site+'_'+pr)
                    # (1)-----

                    # SysLab(2)-----
                    #===== Rename tplot variables and set options =====#
                    for current_tplot_name in loaded_data_temp:
                        get_data_vars = get_data(current_tplot_name)
                        if get_data_vars is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = current_tplot_name.replace('_station_0', '')
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            clip(new_tplot_name, -9998, 9998)
                            get_data_vars = get_data(new_tplot_name)
                            #;--- Labels
                            dp = new_tplot_name.replace('_'+site+'_'+pr, '')
                            dp = dp.replace(prefix, '')
                            metadata = pytplot.get_data(new_tplot_name, metadata=True)
                            uni = metadata['netCDF']['VATT']['units']
                            options(new_tplot_name, 'ytitle','MW-'+site)
                            options(new_tplot_name, 'ysubtitle', 'Height \n [m]') #共通
                            options(new_tplot_name, 'ztitle', dp)
                            options(new_tplot_name, 'zsubtitle', '['+uni+']')
                    # (2)-----
                            
                    current_tplot_name=prefix+'uwind_'+st+'_'+pr
                    print(current_tplot_name)
                    options(current_tplot_name, 'Spec', 1)

                    current_tplot_name=prefix+'vwind_'+st+'_'+pr
                    print(current_tplot_name)
                    options(current_tplot_name, 'Spec',1)

                    current_tplot_name=prefix+'sig_uwind_'+st+'_'+pr
                    print(current_tplot_name)
                    options(current_tplot_name, 'Spec', 1)

                    current_tplot_name=prefix+'sig_vwind_'+st+'_'+pr
                    print(current_tplot_name)
                    options(current_tplot_name, 'Spec',1)

    return loaded_data
