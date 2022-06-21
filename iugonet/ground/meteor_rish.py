import numpy as np

from pyspedas.utilities.time_double import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def meteor_rish(
    trange=['2011-10-01', '2011-11-01'],
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
    local_path = 'rish/misc/sgk/meteor/'
    prefix = 'iug_meteor_'
    file_res = 3600. * 24
    site_list = ['bik', 'ktb', 'sgk', 'srp']
    datatype_list = ['']
    parameter_list = ['h2t60min00', 'h2t60min30', 'h4t60min00', 'h4t60min30', 'h4t240min00']
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
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/mudb/data/mwr/'
                    pathformat = 'nc/ver1_0/'+pr1+'/%Y/Ws%Y%m%d.'+pr+'.nc'
                elif st == 'bik':
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/biak/'
                    pathformat = 'nc/ver1_0/'+pr1+'/%Y/Wb%Y%m%d.'+pr+'.nc'
                elif st == 'bik':
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/kototabang/'
                    pathformat = 'nc/ver1_1_2/'+pr1+'/%Y/Wk%Y%m%d.'+pr+'.nc'
                elif st == 'srp':
                    remote_data_dir = 'http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/serpong/'
                    pathformat = 'nc/ver1_0_2/'+pr1+'/%Y/jkt%Y%m%d.'+pr+'.nc'

                loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                    get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
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
                        print('printing PI info and rules of the road was failed')
                
                if (not downloadonly) and (not notplot):
                    '''
				    clip(tplot_name, -1e+4, 1e+4)
                    ylim(tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
                    options(tplot_name, 'legend_names', ['H','D','Z'])
                    options(tplot_name, 'Color', ['b', 'g', 'r'])
                    options(tplot_name, 'ytitle', '\n'.join(tplot_name.split('_')))
                    '''

                return loaded_data
