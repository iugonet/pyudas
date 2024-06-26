import numpy as np


# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from pyspedas.utilities.dailynames import dailynames
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load


def gps_atec(
    trange=['2020-01-01', '2020-01-02'],
    site='all',
    datatype='all',
	parameter='',
    fproton=False,
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
    remote_data_dir = 'https://stdb2.isee.nagoya-u.ac.jp/GPS/shinbori/AGRID2/nc/'
    local_path = 'isee/'
    prefix = 'isee_'
    file_res = 3600. * 24
    site_list = []
    datatype_list = []
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

 

				#===== Set parameters (2) =====#
            pathformat ='%Y/%DOY/%Y%m%d??_atec.nc'
				#==============================#
			
            suffix_tmp=''			
            loaded_data_temp = load(trange=trange, site=st, parameter=pr, \
                pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                no_update=no_update, downloadonly=downloadonly, uname=uname, passwd=passwd, \
                local_path=local_path, prefix=prefix, suffix=suffix_tmp, \
                get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
                notplot=notplot, time_clip=time_clip, version=version)
            
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
                    #===== Remove or Rename tplot variables, and set options =====#
                    current_tplot_name = prefix+'epoch'
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)

                    current_tplot_name = prefix+'time_cal'
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)

                    current_tplot_name = prefix+'gps_atec'
                    if current_tplot_name in loaded_data:
                        get_data_vars = get_data(current_tplot_name)
                        if get_data_vars is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+'gps_atec'+suffix
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            clip(new_tplot_name, -1e+5, 1e+5)
                            get_data_vars = get_data(new_tplot_name)
                            ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))

                    #;----- If fproton=True is set, rename tplot variables -----;
                    if fproton:
                        current_tplot_name = prefix+'f_'+dt
                        if current_tplot_name in loaded_data:
                            get_data_vars = get_data(current_tplot_name)
                            if get_data_vars is None:
                                store_data(current_tplot_name, delete=True)
                            else:
                                #;--- Rename
                                new_tplot_name = prefix+'mag_'+suffix+'_f'
                                store_data(current_tplot_name, newname=new_tplot_name)
                                loaded_data.remove(current_tplot_name)
                                loaded_data.append(new_tplot_name)
                                #;--- Missing data -1.e+31 --> NaN
                                clip(new_tplot_name, -1e+5, 1e+5)
                                get_data_vars = get_data(new_tplot_name)
                                if np.all(np.isnan(get_data_vars[1])):
                                    ylim(new_tplot_name, 40000, 49000)
                                else:
                                    ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))

                                    
                    else:
                        current_tplot_name = prefix+'f_'+dt
                        if current_tplot_name in loaded_data:
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)

    return loaded_data
