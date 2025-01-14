import numpy as np
import pytplot
# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def blr_rish(
    trange=['2007-8-1', '2007-8-6'],
    site='all',
    datatype='troposphere',
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
    file_format = 'csv'
    prefix = 'iug_aws_'
    file_res = 3600
    time_column = [1, 2, 3, 4, 5]
    time_format = ['Y', 'm', 'd', 'H', 'M']
    input_time = [-1, -1, -1, -1, -1, 0]
    comment_symbol = ''
    header_only = False
    data_start = 2
    site_list = ['bik', 'ktb', 'mnd', 'pon'] # all sites(default)
    parameter_list = ['uwnd', 'wwnd', 'vwnd', 'pwr1', 'pwr2', 'pwr3', 'pwr4', 'pwr5', 'wdt1', 'wdt2', 'wdt3', 'wdt4', 'wdt5']
    unit_list = ['m/s', 'm/s', 'm/s', 'dB', 'dB', 'dB', 'dB', 'dB', 'm/s', 'm/s', 'm/s', 'm/s', 'm/s']
    datatype_list = ['troposphere']
    delimiter = ['/', ' ', ':', ',']
    no_convert_time = False
    format_type = 3
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
    # if 'all' in pr_list:
    if 'all' in pr_list:
        pr_list = parameter_list
        u_list = unit_list
    pr_list = list(sorted(set(pr_list).intersection(parameter_list), key=pr_list.index))
    #u_list = list(sorted(set(u_list).intersection(unit_list), key=u_list.index))
    
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
        
        if st == 'ktb':
            st1 = 'kototabang'
            localtime = 7.0
        elif st == 'bik':
            st1 = 'biak'
            localtime = 9.0
        elif st == 'mnd':
            st1 = 'manado'
            localtime = 8.0
        elif st == 'pon':
            st1 = 'pontianak'
            localtime = 7.0
        else:
            print('Such site name is not supported!')
            return

        for dt in dt_list:
            if len(dt) < 1:
                varname_st_dt = varname_st
            else:
                varname_st_dt = varname_st + '_' + dt

                for pr in pr_list:
                    if len(pr) < 1:
                        varname_st_dt_pr = varname_st_dt
                    else:
                        varname_st_dt_pr = varname_st_dt+'_'+pr
                        
                    pr_idx=parameter_list.index(pr)
                    
                    if len(varname_st_dt_pr) > 0:
                        suffix = '_'+varname_st_dt_pr

                    #===== Set parameters (2) =====#
                    # remote_data_dir = 'http://www.rish.kyoto-u.ac.jp/radar-group/surface/' + st + '/aws/csv/'
                    # pathformat = '%Y%Y%Y%Y/%Y%Y%Y%Y%m%m/' + st + '%Y%Y%Y%Y%m%d.csv'
                    remote_data_dir = 'http://www.rish.kyoto-u.ac.jp/radar-group/blr/' + st1 + '/data/data/ver02.0212/'
                    pathformat = '%Y%m/%Y%m%d/%Y%m%d.' + pr  + '.csv'
                    #==============================#

                    local_path = 'rish/misc/' + st + '/aws'

                    loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
                                            pathformat=pathformat, file_res=file_res, remote_path=remote_data_dir, \
                                            local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                                            uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                                            get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
                                            notplot=notplot, time_clip=time_clip, version=version, file_format=file_format, \
                                            localtime=localtime, time_column=time_column, time_format=time_format, \
                                            data_start=data_start, comment_symbol=comment_symbol, delimiter=delimiter, \
                                            format_type=format_type, no_convert_time=no_convert_time, input_time=input_time, var_name=varname_st_dt_pr)
                
                    if notplot:
                        loaded_data.update(loaded_data_temp)
                    else:
                        if loaded_data_temp == None:
                            continue
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
                          + 'If you acquire the boundary layer radar (BLR) data, \n' \
                          + 'we ask that you acknowledge us in your use of the data. This may be done by \n' \
                          + 'including text such as the BLR data provided by Research Institute\n' \
                          + 'for Sustainable Humanosphere of Kyoto University. We would also\n' \
                          + 'appreciate receiving a copy of the relevant publications. The distribution of\n' \
                          + 'BLR data has been partly supported by the IUGONET (Inter-university Upper\n' \
                          + 'atmosphere Global Observation NETwork) project (http://www.iugonet.org/) funded\n' \
                          + 'by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.\n' \
                            + '**************************************************************************')
                    
                    if (not downloadonly) and (not notplot):
                        # current_tplot_name = tplot_names(quiet=True)
                        options(varname_st_dt_pr, 'Spec', 1)
                        options(varname_st_dt_pr,'ytitle', 'BLR-'+st+'\nHeight [km]')
                        options(varname_st_dt_pr, 'ztitle', pr+'\n['+unit_list[pr_idx]+']')
                        
                        '''
                        #===== Remove tplot variables =====#
                        current_tplot_name = prefix+'epoch'
                        if current_tplot_name in loaded_data:
                            store_data(current_tplot_name, delete=True)
                            loaded_data.remove(current_tplot_name)
                        #===== Rename tplot variables and set options =====#
                        current_tplot_name = prefix+'db_dt'
                        if current_tplot_name in loaded_data:
                            get_data_vars = get_data(current_tplot_name)
                            if get_data_vars is None:
                                store_data(current_tplot_name, delete=True)
                            else:
                                #;--- Rename
                                new_tplot_name = prefix+'imag'+suffix
                                store_data(current_tplot_name, newname=new_tplot_name)
                                loaded_data.remove(current_tplot_name)
                                loaded_data.append(new_tplot_name)
                                #;--- Missing data -1.e+31 --> NaN
                                clip(new_tplot_name, -1e+5, 1e+5)
                                get_data_vars = get_data(new_tplot_name)
                                ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
                                #;--- Labels
                                options(new_tplot_name, 'legend_names', ['X','Y','Z'])
                                options(new_tplot_name, 'Color', ['b', 'g', 'r'])
                                options(new_tplot_name, 'ytitle', st.upper())
                                options(new_tplot_name, 'ysubtitle', '[V]')
                        '''

    return loaded_data