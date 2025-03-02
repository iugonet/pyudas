import numpy as np
import pytplot
from pyspedas import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, tplot_names
from ..load import load
import datetime

def mu(
    trange = ['1986-03-17', '1986-09-18'],
    site='all',
    datatype='all',
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
    ror=True,
    iono_type='pwr',  # ionosphere data用
    length_meteor='1_day'  # meteor data用
):
    
    #===== Set parameters (1) =====#
    file_format = 'netcdf'
    # local_path = '/rish/misc/sgk/mu '
    prefix = 'iug_mu_' 
    file_res = 3600. * 24
    site_list = ['']
    datatype_list = ['troposphere', 'mesosphere', 'ionosphere', 'meteor', 'rass', 'fai']
    level_list = ['org', 'scr', 'all']
    parameter_list = ['']
    parameter_mesosphere_list = ['org', 'wnd']
    parameter_meteor_list = ['h1t60min00', 'h1t60min30', 'h2t60min00', 'h2t60min30']
    parameter_rass_list = ['uwnd', 'vwnd', 'wwnd', 'temp']
    parameter_fai_list = ['ie2e4b', 'ie2e4c', 'ie2e4d', 'ie2rea', 'ie2mya', 'ie2myb', 'ie2rta', 'ie2trb', 'iecob3', 'ied101', 'ied103', 'ied108', 'ied110', 'ied201', 'ied202', 'ied203', 'iedb4a', 'iedb4b', 'iedb4c', 'iedc4a', 'iedc4b', 'iedc4c', 'iede4a', 'iede4b', 'iede4c', 'iede4d', 'iedp01', 'iedp02', 'iedp03', 'iedp08', 'iedp10', 'iedp11', 'iedp12', 'iedp13', 'iedp1s', 'iedpaa', 'iedpbb', 'iedpcc', 'iedpdd', 'iedpee', 'iedpff', 'iedpgg', 'iedphh', 'iedpii', 'iedpjj', 'iedpkk', 'iedpl2', 'iedpll', 'iedpmm', 'iedptt', 'iedpyy', 'iedpzz', 'ieewb5', 'ieimga', 'ieimgb', 'ieimgm', 'ieimgt', 'ieis01', 'iefai1', 'iefdi2', 'ieggmt', 'iemb5i', 'iemcb3', 'iemdb3', 'iemdb5', 'iemdc3', 'iemy3a', 'iemy3b', 'iemy3c', 'iemyb5', 'iensb5', 'iepbr1', 'iepbr2', 'iepbr3', 'iepbr4', 'iepbr5', 'iepbrt', 'ieper1', 'ieper2', 'ieper3', 'ieper4', 'ieper5', 'ieper6', 'ieper7', 'ieper8', 'ieps3a', 'ieps3b', 'ieps3c', 'ieps4a', 'ieps4b', 'ieps4c', 'ieps4d', 'ieps4e', 'ieps5a', 'ieps5b', 'ieps5c', 'ieps6a', 'ieps6b', 'iepsb3', 'iepsb4', 'iepsb5', 'iepsi1', 'iepsi5', 'iepsit', 'iesp01', 'iess01', 'iess02', 'iess03', 'iess04', 'iess05', 'iess2l', 'iess3l', 'iess4l', 'iess8c', 'iessb5', 'iesst2', 'iesst3', 'iet101', 'iet102', 'ietest', 'ietst2', 'ieto02', 'ieto03', 'ieto16', 'ietob3', 'ietob4', 'ietob5', 'iey4ch', 'iey4ct', 'ieyo4a', 'ieyo4b', 'ieyo4c', 'ieyo4d', 'ieyo4e', 'ieyo4f', 'ieyo4g', 'ieyo5a', 'ieyo5b', 'ieyo5c', 'ieyo5d', 'ieyo5e', 'ieyo5f', 'ieyo5g', 'ieyo5m', 'ifco02', 'ifco03', 'ifco04', 'ifco16', 'if5bd1', 'if5bd2', 'if5bd3', 'if5bd4', 'if5bd5', 'if5be1', 'if5be2', 'if5be3', 'if5be4', 'if5be5', 'ifchk1', 'ifdp00', 'ifdp01', 'ifdp02', 'ifdp03', 'ifdp0a', 'ifdp0b', 'ifdp0c', 'ifdp0d', 'ifdp1u', 'ifdp1s', 'ifdp1t', 'ifdpll', 'ifdq01', 'ifdq02', 'ifim16', 'ifmb16', 'ifmc16', 'ifmd16', 'ifmf16', 'ifmy01', 'ifmy02', 'ifmy03', 'ifmy04', 'ifmy05', 'ifmy99', 'ifmyc1', 'ifmyc2', 'ifmyc3', 'ifmyc4', 'ifmyc5', 'ifmyc6', 'ifmyc7', 'ifmyca', 'ifmycb', 'ifmyt1', 'ifmyt2', 'ifmyt3', 'ifmyt4', 'ifmyt5', 'ifmyu1', 'ifmyu2', 'ifmyu3', 'ifmyu4', 'ifmyu5', 'ifmyv1', 'ifpsi1', 'ifpsit', 'ifss02', 'iftes1', 'iftes2', 'iftes3', 'iftes5', 'iftes6', 'iftes7', 'iftes8', 'ifts01', 'ifts02', 'ifts03', 'ifts04', 'ifts05', 'ifts06', 'ifts07']
    time_netcdf = 'time'
    # specvarname = 'height'
    specvarname = 'range'
    length_list = ['1_day', '1_month']  # meteor data用
    #==============================#

    # modify trange
    trange[1] = str(datetime.datetime.fromisoformat(trange[1]).date() + datetime.timedelta(days=1))
    
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

    if notplot:
        loaded_data = {}
    else:
        loaded_data = []

    for dt in dt_list:
        if len(dt) < 1:
            varname_st_dt = ''
        else:
            varname_st_dt = dt

        # parameter
        if dt in ['troposphere', "ionosphere"]:
            parameter_list = parameter_list
        elif dt == 'mesosphere':
            parameter_list = parameter_mesosphere_list
        elif dt == 'meteor':
            parameter_list = parameter_meteor_list
        elif dt == 'rass':
            parameter_list = parameter_rass_list
        elif dt == 'fai':
            parameter_list = parameter_fai_list

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
                local_path = '/rish/misc/sgk/mu/' + dp + '/nc/'
                remote_data_dir = 'https://www.rish.kyoto-u.ac.jp/mu/data/data/ver01.0807_1.02/'
                pathformat = '%Y%m/%Y%m%d/%Y%m%d.nc'
            
            elif dt == 'mesosphere':
                dp = 'mesosphere'

                if pr == 'org':
                    pathformat = '%Y/%Y%m/%Y%m%d.nc'
                elif pr == 'wnd':
                    pathformat = '%Y/%Y%m/%Y%m%d.wnd.nc'

                local_path = '/rish/misc/sgk/mu/' + dp + '/nc/'
                remote_data_dir = 'https://www.rish.kyoto-u.ac.jp/mu/'+dp+'/data/netcdf/'
                # pathformat = '%Y%m/%Y%m%d/%Y%m%d.nc'
                # pathformat = '%Y%m/%Y%m%d/%Y%m%d.wnd.nc'
                # pathformat = '%Y/%Y%m/%Y%m%d.wnd.nc'
            
            elif dt == 'ionosphere':
                dp = 'ionosphere'

                if iono_type == 'teti':
                    time_netcdf = 'stime'
                    specvarname = 'height'
                    local_path = 'rish/misc/sgk/mu/'+dp+'/teti/nc/' #teti data用
                    remote_data_dir = 'https://www.rish.kyoto-u.ac.jp/mu/isdata/data/teti/netcdf/'  #teti data用
                    pathformat = '%Y/%Y%m%d_teti.nc'
                elif iono_type == 'pwr':
                    time_netcdf = 'stime'
                    specvarname = 'height'
                    local_path = 'rish/misc/sgk/mu/'+dp+'/pwr/nc/'  #pwr data用
                    remote_data_dir = 'https://www.rish.kyoto-u.ac.jp/mu/isdata/data/pwr/netcdf/'   #pwr data用
                    pathformat = '%Y/%Y%m%d_pwr.nc'    #pwr data用
                elif iono_type == 'drift':
                    # specvarname = 'Vperp_e'
                                
                    local_path = 'rish/misc/sgk/mu/'+dp+'/drift/nc/' #drift data用
                    remote_data_dir = 'https://www.rish.kyoto-u.ac.jp/mu/isdata/data/drift/netcdf/'   #drift data用
                    pathformat = '%Y/%Y%m%d_drift.nc' #drift data用

            elif dt == 'meteor':
                dp = 'meteor'

                if pr == 'h1t60min00':
                    h_t = 'h1km_t60min00'
                elif pr == 'h1t60min30':
                    h_t = 'h1km_t60min30'
                elif pr == 'h2t60min00':
                    h_t = 'h2km_t60min00'
                elif pr == 'h2t60min30':
                    h_t = 'h2km_t60min30'

                remote_data_dir = ' http://www.rish.kyoto-u.ac.jp/mu/'+dp+'/data/netcdf/'

                if length_meteor == '1_day':
                    local_path = 'rish/misc/sgk/mu/'+dp+'/nc/1_day/' #lengthで1_dayが選択された場合
                    pathformat = '1_day/' + h_t + '/%Y/W%Y%m%d.'+ pr +'.nc' #lengthで1_dayが選択された場合
                elif length_meteor == '1_month':
                    local_path = 'rish/misc/sgk/mu/'+dp+'/nc/1_month/' #lengthで1_monthが選択された場合
                    pathformat = '1_month/' + h_t + '/%Y/W%Y%m.'+ pr +'.nc' #lengthで1_monthが選択された場合

            elif dt == 'rass':
                dp = 'rass'
                local_path = 'rish/misc/sgk/mu/'+dp+'/csv/' 
                remote_data_dir = 'http://www.rish.kyoto-u.ac.jp/mu/'+dp+'/data/csv/'
                pathformat = '%Y/%Y%m%d/%Y%m%d.'+pr+'.csv'
                file_format = 'csv'
                time_column = [1, 2, 3, 4, 5, 6]
                time_format = ['d', 'm', 'Y', 'H', 'M', 'S']
                delimiter=['-', ' ', ':' , ',']
                format_type = 3
                
            
            elif dt == 'fai':
                dp = 'fai'
                local_path = 'rish/misc/sgk/mu/'+dp+'/nc/' 
                remote_data_dir = 'http://www.rish.kyoto-u.ac.jp/mu/'+dp+'/data/nc/'
                pathformat = '%Y/%Y%m%d/%Y%m%d.'+pr+'.nc'
            #==============================#

            if dt != 'rass':
                loaded_data_temp = load(trange=trange, datatype=dt, parameter=pr, \
                    pathformat=pathformat, file_res=file_res, remote_path = remote_data_dir, \
                    local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                    uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                    get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
                    notplot=notplot, time_clip=time_clip, version=version, \
                    file_format=file_format, time_netcdf=time_netcdf, \
                    specvarname=specvarname, localtime=9)
            else:   # rass data
                 loaded_data_temp = load(trange=trange, datatype=dt, parameter=pr, \
                        pathformat=pathformat, file_res=file_res, remote_path=remote_data_dir, \
                        local_path=local_path, no_update=no_update, downloadonly=downloadonly, \
                        uname=uname, passwd=passwd, prefix=prefix, suffix=suffix, \
                        get_support_data=get_support_data, varformat=varformat, varnames=varnames, \
                        notplot=notplot, time_clip=time_clip, version=version, \
                        file_format=file_format, time_column=time_column, \
                        time_format=time_format, delimiter=delimiter, \
                        format_type=format_type, data_start=2, localtime=9, \
                        var_name=varname_st_dt_pr)
                        
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
                    print('Rules of the Road for RISH MU Radar Data: ')
                    print('If you acquire the middle and upper atmosphere (MU) radar data, we ask that you acknowledge us in your use of the data. This may be done by including text such as MU data provided by Research Institute for Sustainable Humanosphere of Kyoto University. We would also appreciate receiving a copy of the relevant publications. The distribution of MU radar data has been partly supported by the IUGONET (Inter-university Upper atmosphere Global Observation NETwork) project (http://www.iugonet.org/) funded by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.')
            
            
            if (not downloadonly) and (not notplot):
                #===== Remove tplot variables =====#
                # current_tplot_name = prefix+'epoch'
                # if current_tplot_name in loaded_data:
                #     store_data(current_tplot_name, delete=True)
                #     loaded_data.remove(current_tplot_name)

                for current_tplot_name in loaded_data_temp:
                    get_data_vars = get_data(current_tplot_name)
                    if get_data_vars is None:
                        store_data(current_tplot_name, delete=True)
                    else:
                        #;--- Rename
                        if dt == 'meteor':
                            new_tplot_name = current_tplot_name.replace('_station_0','')
                        else:
                            new_tplot_name = current_tplot_name

                        store_data(current_tplot_name, newname=new_tplot_name)
                        loaded_data.remove(current_tplot_name)
                        loaded_data.append(new_tplot_name)
                        clip(new_tplot_name, -9998, 9998)
                        get_data_vars = get_data(new_tplot_name)
                        #;--- Labels
                        metadata = pytplot.get_data(new_tplot_name, metadata=True)
                        options(new_tplot_name, 'ytitle','MU-'+dp)
                        options(new_tplot_name, 'ztitle', new_tplot_name)

                        if dt == 'troposphere':
                            options(new_tplot_name, 'Spec', 1)
                            options(new_tplot_name, 'ysubtitle', 'Height \n [km]')
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
                                options(new_tplot_name, 'ztitle', 'Doppler velocity\n'+new_tplot_name[-6:])
                            if 'pwr' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[dB]')
                                options(new_tplot_name, 'ztitle', 'Echo power\n'+new_tplot_name[-6:])
                            if 'width' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                options(new_tplot_name, 'ztitle', 'Spectral width\n'+new_tplot_name[-6:])
                            if 'pnoise' in new_tplot_name:    
                                options(new_tplot_name, 'ysubtitle', '[dB]')
                                options(new_tplot_name, 'ztitle', 'Noise level\n'+new_tplot_name[-6:]) 

                        if dt == 'mesosphere':
                            options(new_tplot_name, 'Spec', 1)
                            options(new_tplot_name, 'ysubtitle', 'Height \n [km]')
                            if 'uwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Zonal wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'vwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Meridional wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'wwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Vertical wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'dpl' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                options(new_tplot_name, 'ztitle', 'Doppler velocity\n'+new_tplot_name[-6:])
                            if 'pwr' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[dB]')
                                options(new_tplot_name, 'ztitle', 'Echo power\n'+new_tplot_name[-6:])
                            if 'wdt' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                options(new_tplot_name, 'ztitle', 'Spectral width\n'+new_tplot_name[-6:])

                        if dt == 'ionosphere':
                            if iono_type == 'teti':
                                options(new_tplot_name, 'Spec', 1)
                                options(new_tplot_name, 'ysubtitle', 'Height \n [km]')
                                if 'Ti' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Ion temperature')
                                    options(new_tplot_name, 'zsubtitle', '[K]')
                                if 'Te' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Electron temperature')
                                    options(new_tplot_name, 'zsubtitle', '[K]')
                                if 'er_ti' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Estimation error of \n ion temperature')
                                    options(new_tplot_name, 'zsubtitle', '[K]')
                                if 'er_te' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Estimation error of \n electron temperature')
                                    options(new_tplot_name, 'zsubtitle', '[K]')
                                if 'er_tr' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Estimation error of \n Tr (Te/Ti)')
                                    options(new_tplot_name, 'zsubtitle', '[K]')
                                if 'snr' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Signal to noise ratio')
                                    options(new_tplot_name, 'zsubtitle', '[dB]')

                            if iono_type == 'drift':
                                options(new_tplot_name, 'Spec', 0)
                                options(new_tplot_name, 'ysubtitle', 'Height \n [km]')
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                if 'Ti' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Ion temperature')
                                if 'Te' in new_tplot_name:
                                    options(new_tplot_name, 'ztitle', 'Electron temperature')

                            if iono_type == 'pwr':
                                options(new_tplot_name, 'Spec', 1)
                                options(new_tplot_name, 'ysubtitle', 'Height \n [km]')
                                options(new_tplot_name, 'ztitle', 'Echo power\n'+new_tplot_name[-6:])
                                options(new_tplot_name, 'zsubtitle', '[dB]')

                        if dt == 'meteor':
                            options(new_tplot_name, 'Spec', 1)
                            options(new_tplot_name, 'ysubtitle', 'Height \n [m]')
                            if 'uwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Zonal wind\n'+new_tplot_name[-10:])    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'sig_uwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Standard deviation of \n zonal wind\n'+new_tplot_name[-10:])    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'vwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Meridional wind\n'+new_tplot_name[-10:])
                            if 'sig_vwind' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Standard deviation of \n meridional wind\n'+new_tplot_name[-10:])    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'num' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Number of meteors\n'+new_tplot_name[-10:])    
                                options(new_tplot_name, 'zsubtitle', '[num]')

                        if dt == 'rass':
                            options(new_tplot_name, 'Spec', 1)
                            options(new_tplot_name, 'ysubtitle', 'Height \n [m]')
                            if 'uwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Zonal wind')    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'vwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Meridional wind')
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'wwnd' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Meridional wind')
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                            if 'temp' in new_tplot_name:
                                options(new_tplot_name, 'ztitle', 'Temperature')    
                                options(new_tplot_name, 'zsubtitle', '[K]')
                        
                        if dt == 'fai':
                            options(new_tplot_name, 'Spec', 1)
                            options(new_tplot_name, 'ysubtitle','Height \n [km]')
                            if 'dpl' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                options(new_tplot_name, 'ztitle', 'Doppler velocity\n'+new_tplot_name[-6:])
                            if 'pwr' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[dB]')
                                options(new_tplot_name, 'ztitle', 'Echo power\n'+new_tplot_name[-6:])
                            if 'width' in new_tplot_name:    
                                options(new_tplot_name, 'zsubtitle', '[m/s]')
                                options(new_tplot_name, 'ztitle', 'Spectral width\n'+new_tplot_name[-6:])
                            if 'pnoise' in new_tplot_name:    
                                options(new_tplot_name, 'ysubtitle', '[dB]')
                                options(new_tplot_name, 'ztitle', 'Noise level\n'+new_tplot_name[-6:]) 

    return loaded_data