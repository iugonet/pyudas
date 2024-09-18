import cdflib
import netCDF4
import pytplot

# from pyspedas.analysis.time_clip import time_clip as tclip
from pyspedas.utilities.dailynames import dailynames
from pyspedas.utilities.download import download
from pytplot import cdf_to_tplot 
from .netcdf_to_tplot import netcdf_to_tplot
from .ascii_to_tplot import ascii2tplot
from .download_txt import download_txt

from .config import CONFIG

def load(trange=['2017-03-27', '2017-03-28'],
         site=None,
         datatype='',
		 parameter='',
         pathformat=None,
         file_res=24*3600.,
		 remote_path='',
         local_path='',
         no_update=False,
         downloadonly=False,
         uname=None,
         passwd=None,
         prefix='',
         suffix='',
         get_support_data=False,
         varformat=None,
         specvarname='',
         varnames=[],
         notplot=False,
         time_clip=False,
         version=None,
         file_format='cdf',
         time_netcdf='time',
         localtime=0,
         time_column=1,
         time_format=['Y', 'm', 'd', 'H', 'M'],
         input_time=[-1, -1, -1, -1, -1, -1],
         header_only=False,
         data_start=0,
         comment_symbol='%',
         delimiter=' ',
         format_type=1,
         no_convert_time=False,
         var_name=''):

    # find the full remote path names using the trange
    # SysLab-----
    remote_names = dailynames(file_format=pathformat,
                              trange=trange, res=file_res, suffix='')
    # if len(suffix_hour) == 0:
    #     remote_names = dailynames(file_format=pathformat,
    #                         trange=trange, res=file_res, suffix='')
    # else:
    #     remote_names = []
    #     for i in range(len(suffix_hour)):
    #         if len(suffix_minutes) == 0:
    #             fmt = pathformat.split('.')[0] + suffix_hour[i] + '.' + pathformat.split('.')[1]
    #             tmp = dailynames(file_format=fmt,
    #                             trange=trange, res=file_res, suffix='')
    #         else:
    #             for j in range(len(suffix_minutes)):
    #                 fmt = pathformat.split('.')[0] + suffix_hour[i] + suffix_minutes[j] + '.' + pathformat.split('.')[1]
    #                 tmp = dailynames(file_format=fmt,
    #                                 trange=trange, res=file_res, suffix='')
    #         remote_names.extend(tmp)
    # SysLab-----

    out_files = []

    # SysLab -----
    # files = download(remote_file=remote_names, remote_path=remote_path, local_path=CONFIG[
    #                 'local_data_dir']+local_path, no_download=no_update, last_version=True, username=uname, password=passwd)
    if file_format != 'txt':
        files = download(remote_file=remote_names, remote_path=remote_path, local_path=CONFIG[
                        'local_data_dir']+local_path, no_download=no_update, last_version=True, username=uname, password=passwd
                        ,verify=False) # SSLエラーが出るので、verify=Falseを追加。
    else:
        files = download_txt(remote_file=remote_names, remote_path=remote_path, local_path=CONFIG[
                            'local_data_dir']+local_path)
    # SysLab -----
        
    if files is not None:
        for file in files:
            out_files.append(file)

    out_files = sorted(out_files)

    if downloadonly:
        return out_files

    '''
    print(out_files)
    print(prefix)
    print(suffix)
    print(get_support_data)
    print(varformat)
    print(varnames)
    print(notplot)
    '''

    if file_format == 'cdf':
        tvars = cdf_to_tplot(out_files, prefix=prefix, suffix=suffix, get_support_data = \
            get_support_data, varformat=varformat, varnames=varnames, notplot=notplot)
    elif file_format == 'netcdf':
        tvars = netcdf_to_tplot(out_files, time=time_netcdf, prefix=prefix, suffix=suffix, \
            specvarname=specvarname, varnames=varnames, notplot=notplot)
    elif (file_format == 'csv') or (file_format == 'txt'):
              tvars = ascii2tplot(out_files, trange=trange, localtime=localtime, time_column=time_column, \
                            time_format=time_format, notplot=notplot, input_time=input_time, header_only=header_only, \
                            data_start=data_start, comment_symbol=comment_symbol, delimiter=delimiter, \
                            format_type=format_type, no_convert_time=no_convert_time, file_format=file_format, var_name=var_name)
    else:
        print('This file format is not supported!')
        return
    
    if notplot:
        if len(out_files) > 0 and file_format == 'cdf':
            cdf_file = cdflib.CDF(out_files[-1])
            cdf_info = cdf_file.cdf_info()
            all_cdf_variables = cdf_info['rVariables'] + cdf_info['zVariables']
            gatt = cdf_file.globalattsget()
            for var in all_cdf_variables:
                t_plot_name = prefix + var + suffix
                if t_plot_name in tvars:
                    vatt = cdf_file.varattsget(var)
                    tvars[t_plot_name]['CDF'] = {'VATT':vatt,
                                                'GATT':gatt,
                                                'FILENAME':out_files}
        elif len(out_files) > 0 and file_format == 'netcdf':                    
            netcdf_file = netCDF4.Dataset(out_files[-1], "r")
            gatt= {}
            for name in netcdf_file.ncattrs():
                gatt[name] = getattr(netcdf_file, name)
            for name, var in netcdf_file.variables.items():
                t_plot_name = prefix + name + suffix
                if t_plot_name in tvars:
                    vatt = {}
                    for attrname in var.ncattrs():
                        vatt[attrname] = getattr(var, attrname)
                    tvars[t_plot_name]['netCDF'] = {'VATT':vatt,
                                                    'GATT':gatt,
                                                    'FILENAME':out_files}                    
        return tvars

    if time_clip:
        for new_var in tvars:
            tclip(new_var, trange[0], trange[1], suffix='')

    return tvars
