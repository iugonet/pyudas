import numpy as np
import pytplot
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, tplot_names
from ..load import load

def ear(
    trange=['2001-10-13', '2001-10-18'],    
    site='',
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
    # remote_date_dir = 'http://www2.rish.kyoto-u.ac.jp/ear/'
    # local_path = '/rish/misc/ktb/ear'
    prefix = 'iug_ear_'   
    file_res = 3600. * 24
    site_list = ['']
    datatype_list = ['troposphere', 'e_region', 'ef_region', 'v_region', 'f_region']
    parameter_list = ['','eb1p2a', 'eb1p2b', 'eb1p2c', 'eb2p1a', 'eb3p2a', 'eb3p2b', 'eb3p4a', 'eb3p4b', 'eb3p4c', 'eb3p4d', 'eb3p4e', 'eb3p4f', 'eb3p4g', 'eb3p4h', 'eb4p2c', 'eb4p2d', 'eb4p4', 'eb4p4a', 'eb4p4b', 'eb4p4d', 'eb5p4a', 'efb1p16', 'efb1p16a', 'efb1p16b', 'vb3p4a', '150p8c8a', '150p8c8b', '150p8c8c', '150p8c8d', '150p8c8e', '150p8c8b2a', '150p8c8b2b', '150p8c8b2c', '150p8c8b2d', '150p8c8b2e', '150p8c8b2f', 'fb1p16a', 'fb1p16b', 'fb1p16c', 'fb1p16d', 'fb1p16e', 'fb1p16f', 'fb1p16g', 'fb1p16h', 'fb1p16i', 'fb1p16j1', 'fb1p16j2', 'fb1p16j3', 'fb1p16j4', 'fb1p16j5', 'fb1p16j6', 'fb1p16j7', 'fb1p16j8', 'fb1p16j9', 'fb1p16j10', 'fb1p16j11', 'fb1p16k1', 'fb1p16k2', 'fb1p16k3', 'fb1p16k4', 'fb1p16k5', 'fb1p16m2', 'fb1p16m3', 'fb1p16m4', 'fb8p16', 'fb8p16k1', 'fb8p16k2', 'fb8p16k3', 'fb8p16k4', 'fb8p16m1', 'fb8p16m2']
    time_netcdf = 'time'
    #specvarname = 'height'
    specvarname = 'range'   # heightだとデータがtplotに入らない。rangeだと入る。
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

                #===== Set parameters (2) =====#
                
                if dt == 'troposphere':
                    dp = 'troposphere'
                    local_path = 'rish/misc/ktb/ear/troposphere/nc/' 
                    remote_data_dir = 'https://www2.rish.kyoto-u.ac.jp/ear/data/data/ver02.0212/'
                    pathformat = '%Y%m/%Y%m%d/%Y%m%d.nc'

                elif dt in ['e_region', 'ef_region', 'v_region', 'f_region']:
                    dp = 'e_region'
                    local_path = 'rish/misc/ktb/ear/fai/'+ dp +'/nc/' 
                    remote_data_dir = 'http://www2.rish.kyoto-u.ac.jp/ear/data-fai/data/nc/'
                    parameter = pr
                    pathformat = '%Y/%Y%m%d/%Y%m%d.fai'+ pr +'.nc'
                    # parameter = parameter_list[i]
                    # pathformat = '%Y/%Y%M%D/%Y %M%D%h.fai'+ parameter[i]+'.nc'
                
                #==============================#

                loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                    get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
                    notplot=notplot, time_clip=time_clip, version=version, \
                    file_format=file_format, time_netcdf=time_netcdf, specvarname=specvarname)
            
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
                        print('Rules of the Road for RISH EAR Data: ')
                        print('The Equatorial Atmosphere Radar belongs to Research Institute for Sustainable Humanosphere (RISH), Kyoto University and is operated by RISH and National Institute of Aeronautics and Space (LAPAN) Indonesia. Distribution of the data has been partly supported by the IUGONET (Inter-university Upper atmosphere Global Observation NETwork) project (http://www.iugonet.org/) funded by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.')
                
                if (not downloadonly) and (not notplot):
                    #===== Remove tplot variables =====#
                    # current_tplot_name = prefix+'epoch'
                    # if current_tplot_name in loaded_data:
                    #     store_data(current_tplot_name, delete=True)
                    #     loaded_data.remove(current_tplot_name)
                    #===== Rename tplot variables and set options =====#
                    for current_tplot_name in loaded_data_temp:
                        get_data_vars = get_data(current_tplot_name)
                        if get_data_vars is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = current_tplot_name.replace('__','_')
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            clip(new_tplot_name, -9998, 9998)
                            get_data_vars = get_data(new_tplot_name)
                            #;--- Labels
                            metadata = pytplot.get_data(new_tplot_name, metadata=True)
                            options(new_tplot_name, 'Spec', 1)
                            if 'pnoise' in new_tplot_name:    
                                options(new_tplot_name, 'Spec', 0)
                            options(new_tplot_name, 'ytitle', 'Height')
                            options(new_tplot_name, 'ysubtitle', '[km]')
                            options(new_tplot_name, 'ztitle', new_tplot_name)
                            print(new_tplot_name[-6:])
                            if 'zwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Zonal wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'mwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Meridional wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'vwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Vertical wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'dpl' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                # options(new_tplot_name, 'ztitle', 'Doppler velocity\n'+{new_tplot_name[-6:]})
                            if 'pwr' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[dB]')
                                # options(new_tplot_name, 'ztitle', 'Echo power\n'+{new_tplot_name[-6:]})
                            if 'width' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                # options(new_tplot_name, 'ztitle', 'Spectral width\n'+{new_tplot_name[-6:]})
                            if 'pnoise' in new_tplot_name:    
                                options(new_tplot_name, 'ysubtitle', '[dB]')
                                # options(new_tplot_name, 'ztitle', 'Noise level\n'+{new_tplot_name[-6:]}) 
                
                    # value_list = ['event', 'gpsid', 'leoid', 'lat', 'lon', 'ref', 'pres', 'temp', 'tan_lat', 'tan_lon']
                    # for val_name in value_list:
                    #     p_name = prefix + val_name + '_cosmic'
                    #     gZpowet_data_vars = get_data(p_name)
                    #     if get_data_vars is None:
                    #         store_data(p_name, delete=True)
                    #     else:
                    #         #;--- Rename
                    #         new_tplot_name = prefix+val_name
                    #         store_data(p_name, newname=new_tplot_name)
                    #         loaded_data.remove(p_name)
                    #         loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            # clip(new_tplot_name, -1e+5, 1e+5)
                            # get_data_vars = get_data(new_tplot_name)
                            # ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
                            #;--- Labels
                            # options(new_tplot_name, 'legend_names', ['X','Y','Z'])
                            # options(new_tplot_name, 'Color', ['b', 'g', 'r'])
                            # options(new_tplot_name, 'ytitle', st.upper())
                            # options(new_tplot_name, 'ysubtitle', '[V]')

    return loaded_data
