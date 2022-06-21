import numpy as np

from pyspedas.utilities.time_double import time_double
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot
from ..load import load

def template(
    trange=['2020-01-01', '2020-01-02'],
    site='',
    datatype='',
    parameter=''
    no_update=False,
    downloadonly=False,
    uname=None,
    passwd=None,
    get_support_data=False,
    varformat=None,
    varnames=[],
    notplot=False,
    time_clip=False,
    version=None
    ror=True
):

    # Set parameters (1)
    file_format = 'cdf'
    local_data_dir = 'iugonet/'
    remote_data_dir = 'http://iugonet0.nipr.ac.jp/data/'
    prefix = 'iug_mag'
    file_res = 3600. * 24
    site_list = ['']
    datatype_list = ['']
    parameter_list = ['']
    
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
		    varname_st = prefix
		else:
		    varname_st = prefix+'_'+st 

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

				# Set parameters (2)
                pathformat = 'ground/geomag/isee/fluxgate/'+fres+'/'+site_input\
                        +'/%Y/isee_fluxgate_'+fres+'_'+site_input+'_%Y%m%d_v??.cdf'
            
                loaded_data_temp = load(pathformat=pathformat, file_res=file_res, \
                    trange=trange, site=st, datatype=dt, parameter=pr, \
				    prefix=varname_st_dt_pr, get_support_data=get_support_data, \
                    varformat=varformat, downloadonly=downloadonly, notplot=notplot, \
                    time_clip=time_clip, no_update=no_update, uname=uname, passwd=passwd)
            
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
                        print('PI and Host PI(s):')
                        print(gatt["PI_name"])
                        print('')
                        print('Affiliations: ')
                        print(gatt["PI_affiliation"])
                        print('')
                        print('Rules of the Road for ISEE Fluxgate Data Use:')
                        for gatt_text in gatt["TEXT"]:
                            print(gatt_text)
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
