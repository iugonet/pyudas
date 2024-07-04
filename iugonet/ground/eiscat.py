import numpy as np

from pyspedas.utilities.time_double import time_double
# from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, zlim
from iugonet.load import load

def eiscat(
    trange=['2020-02-15', '2020-02-16'],
    site='all',
    ydatatype='alt',
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True
):

    #===== Set parameters (1) =====#
    file_format = 'cdf'
    remote_data_dir = 'http://pc115.seg20.nipr.ac.jp/www/eiscatdata/cdf/basic/'
    local_path = 'nipr/eiscat/'
    prefix = 'eiscat_'
    file_res = 3600. * 24
    site_list = ['tro_vhf','tro_uhf','esr_32m','esr_42m'] #'kir_uhf','sod_uhf']
    ydatatype_list = ['alt', 'lat', 'long']

    datatype = ''
    datatype_list = ['']
    parameter = ''
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

    # ydatatype
    ytype = list(set(ydatatype).intersection(ydatatype_list))
    if not len(ytype) == 1:
        ytype='alt'
    print(ytype)

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
        st_tmp = st.split('_')
        stn = st_tmp[0]
        ant = st_tmp[1]

        for dt in dt_list:
            print(dt)
            if len(dt) < 1:
                varname_st_dt = varname_st
            else:
                varname_st_dt = varname_st+'_'+dt
                
            for pr in pr_list:
                if len(pr) < 1:
                    varname_st_dt_pr = varname_st_dt
                else:
                    varname_st_dt_pr = varname_st_dt+'_'+pr
				
                if len(varname_st_dt_pr) > 0:
                    suffix = '_'+varname_st_dt_pr
				#===== Set parameters (2) =====#
                pathformat = stn+'/'+ant+'/%Y/eiscat_kn_'+stn+'_'+ant+'_%Y%m%d_v??.cdf'
				#==============================#

                loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    prefix=prefix, suffix=suffix, get_support_data=get_support_data, \
                    notplot=notplot, time_clip=time_clip, version=version, \
                    file_format=file_format)
            
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
                        print(f'PI :{gatt["PI_name"]}')
                        print('')
                        print(f'Affiliations: {gatt["PI_affiliation"]}')
                        print('')
                        print('Rules of the Road for EISCAT Radar Data:')
                        print('')
                        print(gatt["Rules_of_use"])
                        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
                        print('**************************************************************************')
                    except:
                        print('printing PI info and rules of the road was failed')
                
                if (not downloadonly) and (not notplot):
                    '''
                   REPLACE DATA 
                    
                    #===== Remove tplot variables =====#
                    current_tplot_name = prefix+'epoch'
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)
'''
                    #===== Rename tplot variables and set options =====#
                    titlehead = stn+'_'+ant+'\n'

                    ytype_tplot_name = prefix+ytype+'_0_'+st
                    if ytype_tplot_name in loaded_data:
                        data = get_data(ytype_tplot_name)
                        vdata=data.y
                    if ytype=='alt':
                        ysubstr='Altitude [km]'
                    elif ytype=='lat':
                        ysubstr='Latitude [deg]'
                    elif ytype=='long':
                        ysubstr='Longitude [deg]'
                    else:
                        print('Such ytypedata ('+ytype+') is not supported!')

                    current_tplot_name = prefix+'pulse_code_id_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_pulse'
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Pulse code ID'])
                            #options(new_tplot_name, 'Color', ['b', 'g', 'r'])
                            options(new_tplot_name, 'ytitle', titlehead+'Pulde code ID')
                            #options(new_tplot_name, 'ysubtitle', '[V]')
                            
                    current_tplot_name = prefix+'int_time_nominal_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_inttim'
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            if np.all(np.isnan(data.y)):
                                ylim(new_tplot_name, -50, 350)
                            else:
                                ylim(new_tplot_name, np.nanmin(data.y), np.nanmax(data.y))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['int.time'])
                            #options(new_tplot_name, 'Color', ['b', 'g', 'r'])
                            options(new_tplot_name, 'ytitle', titlehead+'Int. time')
                            options(new_tplot_name, 'ysubtitle', '[s]')             
                    
                    current_tplot_name = prefix+'lat_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_lat'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            ####new_tplot_name[2]=new_tplot_name[1]
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Lat'])
                            options(new_tplot_name, 'ytitle', titlehead+'Latitude')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec',1)
                            options(new_tplot_name, 'ztitle','Latitude [deg]')

                    current_tplot_name = prefix+'long_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_long'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Lon'])
                            options(new_tplot_name, 'ytitle', titlehead+'Longtitude')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec',1)
                            options(new_tplot_name, 'ztitle','Longitude [deg]')                            
                    current_tplot_name = prefix+'alt_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_alt'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Alt'])
                            options(new_tplot_name, 'ytitle', titlehead+'Altitude')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec',1)
                            options(new_tplot_name, 'ztitle','Altitude [km]')
                            
                    current_tplot_name = prefix+'range_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_range'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Range'])
                            options(new_tplot_name, 'ytitle', titlehead+'Range')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Range [km]')
                            
                    current_tplot_name = prefix+'ne_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name) 
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_ne'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 1e10, 1e12)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Ne'])
                            options(new_tplot_name, 'ytitle', titlehead+'Ne')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'zlog', True)
                            options(new_tplot_name, 'ztitle','Ne [m^-3]')

                    current_tplot_name = prefix+'ne_err_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_neerr'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 1e10, 1e12)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Ne err'])
                            options(new_tplot_name, 'ytitle', titlehead+'Ne err')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Ne err [m^-3]')
  
                    current_tplot_name = prefix+'te_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_te'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 0, 4000)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Te'])
                            options(new_tplot_name, 'ytitle', titlehead+'Te')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Te [K]')
                            
                    current_tplot_name = prefix+'te_err_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_teerr'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 0, 4000)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Te err'])
                            options(new_tplot_name, 'ytitle', titlehead+'Te err')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Te err [K]')
                            
                    current_tplot_name = prefix+'ti_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_ti'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 0, 3000)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Ti'])
                            options(new_tplot_name, 'ytitle', titlehead+'Ti')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Ti [K]')
                            
                    current_tplot_name = prefix+'ti_err_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_tierr'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, 0, 3000)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Ti err'])
                            options(new_tplot_name, 'ytitle', titlehead+'Ti err')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Ti err [K]')
                            
                    current_tplot_name = prefix+'vi_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_vi'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, -200, 200)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Vi'])
                            options(new_tplot_name, 'ytitle', titlehead+'Vi')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Vi [m/s]')
                            
                    current_tplot_name = prefix+'vi_err_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_vierr'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            zlim(new_tplot_name, -200, 200)
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['Vi err'])
                            options(new_tplot_name, 'ytitle', titlehead+'Vi err')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Vi err [m/s]')
                            
                    current_tplot_name = prefix+'composition_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_comp'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['comp'])
                            options(new_tplot_name, 'ytitle', titlehead+'Composition')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Composition [%]')
                            
                    current_tplot_name = prefix+'quality_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_q'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['quality'])
                            options(new_tplot_name, 'ytitle', titlehead+'Quality')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Quality')
                            
                    current_tplot_name = prefix+'quality_flag_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_qflag'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['qual.flag'])
                            options(new_tplot_name, 'ytitle', titlehead+'Quality flag')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Quality flag')
                            
                    current_tplot_name = prefix+'collision_freq_0_'+st
                    if current_tplot_name in loaded_data:
                        data = get_data(current_tplot_name)
                        if data is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+stn+ant+'_colf'
                            store_data(new_tplot_name, data={'x':data.times, 'y':data.y, 'v':vdata})
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            #clip(new_tplot_name, -1e+5, 1e+5)
                            data = get_data(new_tplot_name)
                            #ylim(new_tplot_name, np.nanmin(data[1]), np.nanmax(data[1]))
                            #;--- Labels
                            options(new_tplot_name, 'legend_names', ['col.freq'])
                            options(new_tplot_name, 'ytitle', titlehead+'Col freq')
                            options(new_tplot_name, 'ysubtitle', ysubstr)
                            options(new_tplot_name, 'spec', 1)
                            options(new_tplot_name, 'ztitle','Col.freq [s!E-1!N]')
                            
    return loaded_data
