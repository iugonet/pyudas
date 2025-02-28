import numpy as np

# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, tplot_names
from ..load import load

def mf_rish(
    trange=['2010-02-12', '2010-02-13'],
    site='all',
    datatype='all',
    parameter='',
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
    local_path = '/iugonet/rish/misc/' + site + '/mf/nc/'
    prefix = 'mf_'
    file_res = 3600. * 24
    site_list = ['pam', 'pon']
    datatype_list = ['']
    parameter_list = ['']
    time_netcdf='time'
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

    for st in st_list:
        print(st)		
        if len(st) < 1:
            varname_st = ''
        else:
            varname_st = st 

        for dt in dt_list:
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

                #===== Set parameters (2) =====#
                if st == 'pam':
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mf/pameungpeuk/nc/ver1_0_1/'
                    specvarname = 'range'
                    pathformat ='%Y/%Y%m%d_pam.nc'
                elif st == 'pon':
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mf/pontianak/nc/'
                    specvarname = 'height'
                    pathformat ='%Y/%Y%m%d_fca.nc'
                #==============================#

                loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
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
                        + '(http://database.rish.kyoto-u.ac.jp/arch/iugonet/data_policy/Data_Use_Policy_e.html \n' \
                        + 'The distribution of MF radar data has been partly supported by the IUGONET (Inter-university Upper \n' \
                        + 'atmosphere Global Observation NETwork) project (http://www.iugonet.org/) funded \n' \
                        + 'by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan. \n' \
                        + '**************************************************************************')
                
                if (not downloadonly) and (not notplot):
                    #===== Remove tplot variables =====#
                    # current_tplot_name = prefix+'epoch'
                    # if current_tplot_name in loaded_data:
                    #     store_data(current_tplot_name, delete=True)
                    #     loaded_data.remove(current_tplot_name)
                    #===== Rename tplot variables and set options =====#
                    current_tplot_name = tplot_names(quiet=True)
                    options(current_tplot_name, 'Spec', 1)
                    if site == 'pam':
                        clip('mf_uwind_pam_station_0', -100, 100)
                        clip('mf_vwind_pam_station_0', -100, 100)
                        clip('mf_wwind_pam_station_0', -20, 20)
                    elif site == 'pon':
                        clip('mf_uwind_pon_station_0', -200, 200)
                        clip('mf_vwind_pon_station_0', -200, 200)
                        clip('mf_wwind_pon_station_0', -200, 200)
                        zlim('mf_uwind_pon_station_0', -100, 100)
                        zlim('mf_vwind_pon_station_0', -100, 100)
                        zlim('mf_wwind_pon_station_0', -100, 100)


    return loaded_data
