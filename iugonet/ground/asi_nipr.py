import numpy as np

from pyspedas.utilities.time_double import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def asi_nipr(
    trange=['2020-01-01', '2020-01-02'],
    site='all',
    datatype='all',
    parameter='all',
    no_update=False,
    downloadonly=False,
    uname=None,
    passwd=None,
    suffix='',
    get_support_data=True,
    varformat=None,
    varnames=[],
    notplot=False,
    time_clip=False,
    version=None,
    ror=True
):

    #===== Set parameters (1) =====#
    file_format = 'cdf'
    remote_data_dir = 'http://iugonet0.nipr.ac.jp/data/'
    local_path = '/nipr/'
    prefix = 'nipr_'
    file_res = 3600.
    site_list = ['hus', 'kil', 'krn', 'lyr', 'mcm', 'skb', 'sod', 'spa', 'syo', 'tja', 'tjo', 'tro']
    datatype_list = ['']
    parameter_list = ['0000', '4278', '5577', '6300']
    time_netcdf=''
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
                pathformat = 'asi/'+st+'/%Y/%m/%d/nipr_asi_'+st+'_'+pr+'_%Y%m%d%H_v??.cdf'
                #==============================#

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
                        print('Rules of the Road for NIPR All-Sky Imager Data:')
                        print('')
                        print(gatt["TEXT"])
                        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
                        print('**************************************************************************')
                    except:
                        print('printing PI info and rules of the road was failed')
                
                if (not downloadonly) and (not notplot):

                    #===== Remove tplot variables =====#
                    current_tplot_name = prefix+'time_image'+suffix
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)

                    current_tplot_name = prefix+'mlat_center'+suffix
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)

                    current_tplot_name = prefix+'mlon_center'+suffix
                    if current_tplot_name in loaded_data:
                        store_data(current_tplot_name, delete=True)
                        loaded_data.remove(current_tplot_name)
                    
                    #===== Rename tplot variables and set options =====#
                    current_tplot_name = prefix+'image_raw'+suffix
                    if current_tplot_name in loaded_data:
                        get_data_vars = get_data(current_tplot_name)
                        if get_data_vars is None:
                            store_data(current_tplot_name, delete=True)
                        else:
                            #;--- Rename
                            new_tplot_name = prefix+'asi'+suffix
                            store_data(current_tplot_name, newname=new_tplot_name)
                            loaded_data.remove(current_tplot_name)
                            loaded_data.append(new_tplot_name)
                            #;--- Missing data -1.e+31 --> NaN
                            clip(new_tplot_name, -1e+5, 1e+5)
                            get_data_vars = get_data(new_tplot_name)
                            ylim(new_tplot_name, np.nanmin(get_data_vars[1]), np.nanmax(get_data_vars[1]))
                    '''
                    tm_vn = prefix+'epoch_image'+suffix
                    az_vn = prefix+'azimuth_angle'+suffix
                    el_vn = prefix+'elevation_angle'+suffix
                    glatcen_vn = prefix+'glat_center'+suffix
                    gloncen_vn = prefix+'glon_center'+suffix
                    glatcor_vn = prefix+'glat_corner'+suffix
                    gloncor_vn = prefix+'glon_corner'+suffix
                    alt_vn = prefix+'altitude'+suffix

                    tm_dat = get_data(tm_vn)
                    az_dat = get_data(az_vn)
                    el_dat = get_data(el_vn)
                    glatcen_dat = get_data(glatcen_vn)
                    gloncen_dat = get_data(gloncen_vn)
                    glatcor_dat = get_data(glatcor_vn)
                    gloncor_dat = get_data(gloncor_vn)
                    alt_dat = get_data(alt_vn)

                    store_data(tm_vn,delete=True)
                    loaded_data.remove(tm_vn)
                    store_data(az_vn,delete=True)
                    loaded_data.remove(az_vn)
                    store_data(el_vn,delete=True)
                    loaded_data.remove(el_vn)
                    store_data(glatcen_vn,delete=True)
                    loaded_data.remove(glatcen_vn)                    
                    store_data(gloncen_vn,delete=True)
                    loaded_data.remove(gloncen_vn)
                    store_data(glatcor_vn,delete=True)
                    loaded_data.remove(glatcor_vn)
                    store_data(gloncor_vn,delete=True)
                    loaded_data.remove(gloncor_vn)
                    store_data(alt_vn,delete=True)
                    loaded_data.remove(alt_vn)

                    time = time_double([tm_dat[0],tm_dat[-1]])
                    dim = glatcen_dat.shape
                    nalt = dim[0]
                    nx = dim[1]
                    ny = dim[2]

                    v1 = [0, 1]
                    vx = range(nx)
                    vy = range(ny)

                    azel = np.zeros((2, nx, ny, 2))
                    azel[0, :, :, 0] = az_dat
                    azel[0, :, :, 1] = az_dat
                    azel[1, :, :, 0] = el_dat
                    azel[1, :, :, 1] = el_dat
                    store_data(prefix+'asi'+suffix+'_azel', data={'x':time, 'y':azel, 'v1':v1, 'v2':vx, 'v3':vy})
                    loaded_data.append(prefix+'asi'+suffix+'_azel')

                    pos_cen = np.zeros((2, nalt, nx, ny ,2))
                    pos_cen[0, :, :, :, 0] = glatcen_dat
                    pos_cen[0, :, :, :, 1] = glatcen_dat
                    pos_cen[1, :, :, :, 0] = gloncen_dat
                    pos_cen[1, :, :, :, 1] = gloncen_dat
                    store_data(prefix+'asi'+suffix+'_pos_cen', data={'x':time, 'y':pos_cen, 'v1':v1, 'v2':alt_dat, 'v3':vx, 'v4':vy})
                    loaded_data.append(prefix+'asi'+suffix+'pos_cen')

                    vx2 = range(nx+1)
                    vy2 = range(ny+1)
                    pos_cor = np.zeros((2, nalt, nx+1, ny+1, 2))
                    pos_cor[0, :, :, :, 0] = glatcor_dat
                    pos_cor[0, :, :, :, 1] = glatcor_dat
                    pos_cor[1, :, :, :, 0] = gloncor_dat
                    pos_cor[1, :, :, :, 1] = gloncor_dat
                    store_data(prefix+'asi'+suffix+'_pos_cor', data={'x':time, 'y':pos_cor, 'v1':v1, 'v2':alt_dat, 'v3':vx2, 'v4':vy2})
                    loaded_data.append(prefix+'asi'+suffix+'_pos_cor')
                    '''
    return loaded_data