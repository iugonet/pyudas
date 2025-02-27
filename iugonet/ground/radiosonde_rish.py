import numpy as np

# from pyspedas.utilities.time_double import time_double
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, tplot_names
from ..load import load

def radiosonde_rish(
    trange=['2001-10-13', '2001-10-18'],
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
    prefix = 'radiosonde_'
    file_res = 3600.
    site_list = ['bdg', 'drw', 'gpn', 'ktb', 'ktr', 'pon', 'sgk', 'srp', 'uji']
    dawex_site_list = ['drw', 'gpn', 'ktr'] #  datatypeによって該当する観測点が違うため。dawexが適用できる観測点のリスト。
    dawex_site_code_list=[ 'nD', 'nG', 'nK'] # パスを生成する際のdawex_site_listにある観測点に対応するコード
    path_list = [ 'Dr', 'Gp', 'Kh'] # SysLab
    misc_site_list = ['bdg', 'ktb', 'pon', 'sgk', 'srp', 'uji'] #  datatypeによって該当する観測点が違うため。miscが適用できる観測点のリスト。
    misc_site_code_list=[ 'bandung', 'kototabang', 'pontianak',' serpong','higaraki',' uji'] # パスを生成する際のmisc_site_listにある観測点に対応するコード
    datatype_list = ['dawex', 'misc']
    parameter_list = ['']
    time_netcdf='time'
    specvarname='height' # netcdfで多次元データの場合、z軸の指定。(スペクトルプロットの縦軸)
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
                local_path = '/rish/'+datatype+'/'+site+'/radiosonde/nc/'
                if st in dawex_site_list:
                    dp = 'DAWEX'
                    ind = dawex_site_list.index(st)
                    # SysLab-----
                    # site_code = dawex_site_code_list[ind]
                    # pathformat ='%Y/'+site_code+'%m%d%h.nc'
                    site_code = dawex_site_code_list[ind]
                    path_code = path_list[ind]
                    pathformat ='%Y/'+path_code+'%m%d%h.nc'
                    # ------
                elif st in misc_site_list:
                    dp = 'sonde'
                    ind = misc_site_list.index(st)
                    site_code= misc_site_code_list[ind]
                    pathformat = '%Y/'+'%Y%m%d%h*.nc'
                # SysLab------
                # remote_data_dir='http://database.rish.kyoto-u.ac.jp/arch/iugonet/'+dp+'/data/'+ site_code +'/nc/'
                # pathformat = 'fmag/'+st+'/'+dt+'/%Y/nipr_'+dt+'_fmag_'+st+'_%Y%m%d_v??.cdf'
                remote_data_dir='http://database.rish.kyoto-u.ac.jp/arch/iugonet/'+dp+'/data/'+ path_code +'/nc/'
                pathformat = '%Y/'+site_code+'%m%d%H.nc'
                # -----
                #==============================#

                loaded_data_temp = load(trange=trange, site=st, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    uname=uname, passwd=passwd, prefix=prefix, suffix=suffix,\
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
                        # print('printing PI info and rules of the road was failed')
                            print('**************************************************************************\n' \
                            + 'If you acquire the radiosonde data, we ask that you acknowledge\n' \
                            + 'us in your use of the data. This may be done by including text such as\n' \
                            + 'radiosonde data provided by Research Institute for Sustainable Humanosphere\n' \
                            + 'of Kyoto University. We would also appreciate receiving a copy of the\n' \
                            + 'relevant publications. The distribution of radiosonde data has been partly\n' \
                            + 'supported by the IUGONET (Inter-university Upper atmosphere Global\n' \
                            + 'Observation NETwork) project (http://www.iugonet.org/) funded by the\n' \
                            + 'Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.\n' \
                            + '**************************************************************************')
                
                if (not downloadonly) and (not notplot):
                    #current_tplot_name = tplot_names(quiet=True)
                    options(loaded_data, 'Spec', 1)
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