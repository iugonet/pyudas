import numpy as np
import xarray as xr
from pytplot import tplot, store_data
import pytplot
import calendar
import copy


def change_time_to_unix_time(time_var):
    from netCDF4 import num2date
    # A function that takes a variable with units of 'seconds/minutes/hours/etc. since YYYY-MM-DD:HH:MM:SS/etc
    # and converts the variable to seconds since epoch
    units = time_var.units
    dates = num2date(time_var[:], units=units)
    unix_times = list()
    for date in dates:
        unix_time = calendar.timegm(date.timetuple())
        unix_times.append(unix_time)
    return unix_times


def add_output_table(output_table, var_name, tplot_data):
    if var_name not in output_table:
        output_table[var_name] = tplot_data
    else:
        var_data = output_table[var_name]
        for output_var in var_data:
                if np.asarray(tplot_data[output_var]).ndim == 0 and np.equal(tplot_data[output_var], None):
                    pass
                elif np.asarray(var_data[output_var]).ndim == 0 and np.equal(var_data[output_var], None):
                    var_data[output_var] = tplot_data[output_var]
                else:
                    var_data[output_var] = np.concatenate((var_data[output_var], tplot_data[output_var]))
                                    

def netcdf_to_tplot(filenames, time ='time', varnames=[], specvarname='', prefix='', suffix='', plot=False, merge=False, notplot=False):
    '''
    This function will automatically create tplot variables which depend on the time dimension from netCDF files.

    Parameters:
        filenames : str/list of str
            The file names and full paths of netCDF files.
        time: str
            The name of the netCDF file's time variable.
        varnames: str or list of str
            Load these variables only. If [] or ['*'], then load everything.
        specvarname: str
            The name of option variable(v)
        prefix: str
            The tplot variable names will be given this prefix. By default,
            no prefix is added.
        suffix: str
            The tplot variable names will be given this suffix. By default,
            no suffix is added.
        plot: bool
            The data is plotted immediately after being generated. All tplot
            variables generated from this function will be on the same plot.
            By default, a plot is not created.
        merge: bool
            If True, then data from different netCDF files will be merged into
            a single pytplot variable.
        notplot: bool
            If True, then data are returned in a hash table instead of
            being stored in tplot variables (useful for debugging, and
            access to multi-dimensional data products)
    Returns:
        List of tplot variables created (unless notplot keyword is used).
            
    Examples:
        >>> import iugonet
        >>> file = "20020325.faieb4p4a.nc"
        >>> iugonet.netcdf_to_tplot(file, time='time', varnames=['pwr', 'pnoise'], specvarname='range')

    History:
        Original code by netcdf_to_tplot.py in pytplot.
        Aug. 21, 2022:    Modify for using preprocesses in PyUDAS,    S. Abe
        Aug. 28, 2022:    Update,    S. Abe
        Oct. 22, 2022:    Update based on cdf_to_tplot.py,    S. Abe
    '''

    from netCDF4 import Dataset

    stored_variables = []
    output_table = {}
    metadata = {}

    if len(varnames) > 0:
        if '*' in varnames:
            varnames = []
   
    if isinstance(filenames, str):
        filenames = [filenames]
    elif isinstance(filenames, list):
        filenames = filenames
    else:
        print("Invalid filenames input.")
        return stored_variables

    filenames.sort()
    for filename in filenames:
        # Read in file
        file = Dataset(filename, "r")
        
        # Creating dictionaty that will contain global attributes
        gvars_and_atts = {}
        for name in file.ncattrs():
            gvars_and_atts[name] = getattr(file, name)
        
        # Creating dictionary that will contain variables and their attributes
        vars_and_atts = {}
        for name, variable in file.variables.items():
            vars_and_atts[name] = {}
            for attrname in variable.ncattrs():
                vars_and_atts[name][attrname] = getattr(variable, attrname)

        # Filling in missing values for each variable with np.nan (if values are not already nan)
        # and saving the masked variables to a new dictionary
        masked_vars = {}    # Dictionary containing properly masked variables
        for var in vars_and_atts.keys():
            reg_var = file.variables[var]
            if notplot == False:
                try:
                    var_fill_value = vars_and_atts[var]['missing_value']
                    if np.isnan(var_fill_value) != True:
                        # We want to force missing values to be nan so that plots don't look strange
                        var_mask = np.ma.masked_where(reg_var == np.float32(var_fill_value), reg_var)
                        var_filled = np.ma.filled(var_mask, np.nan)
                        masked_vars[var] = var_filled
                    elif np.isnan(var_fill_value) == True:
                        # missing values are already np.nan, don't need to do anything
                        var_filled = reg_var
                        masked_vars[var] = var_filled
                except:    # continue # Go to next iteration, this variable doesn't have data to mask (probably just a descriptor variable (i.e., 'base_time')
                    var_filled = reg_var
                    masked_vars[var] = var_filled
            else:
                var_filled = reg_var
                masked_vars[var] = var_filled                

        # Here is an exception filter that will allow a user to pick a different time variable if time doesn't exist.
        if time != '':
            time_var = file[time]
            unix_times = change_time_to_unix_time(time_var)
        elif time == '':
            time = input('Please enter time variable name. \nVariable list: {l}'.format(l=vars_and_atts.keys()))
            while True:
                if time not in vars_and_atts.keys():
                    # Making sure we input a valid response (i.e., the variable exists in the dataset), and also avoiding
                    # plotting a time variable against time.... because I don't even know what that would mean and uncover.
                    print('Not a valid variable name, please try again.')
                    continue
                elif time in vars_and_atts.keys():
                    time_var = file[time]
                    unix_times = change_time_to_unix_time(time_var)
                    break

        # Create list of variables in netCDF file
        if len(varnames) > 0:
            load_variables = [value for value in varnames if value in file.variables]
        else:
            load_variables = file.variables
        
        # Create tplot variables
        for i,var in enumerate(load_variables):
            var_name = prefix + var + suffix
            ndims = file[var].ndim
            if 'time' in file[var].dimensions:
                indx = file[var].dimensions.index('time')
            #print(ndims)
            # Process for creating tplot variable
            yval = masked_vars[var]
            # one dimension(time only)
            if ndims == 1:
                if notplot:
                    # raw data
                    tplot_data = {'y': yval}
                    add_output_table(output_table, var_name, tplot_data)
                else:
                    # tplot data
                    if 'time' in file[var].dimensions:
                        tplot_data = {'x': unix_times, 'y': yval}
                        add_output_table(output_table, var_name, tplot_data)
                        vatt = {}
                        for attrname in file[var].ncattrs():
                            vatt[attrname] = getattr(file[var], attrname)
                        metadata[var_name] = {'var_attrs': vatt, 'global_attrs': gvars_and_atts, 'file_name': filename}
                        #print(var + ': creates tplot variable')
                    else:
                        continue
 
            # two dimension (time and the other)
            elif ndims == 2:
                yval2=np.array(yval[:,:])
                if notplot:
                    # raw data
                    tplot_data = {'y': yval2}
                    add_output_table(output_table, var_name, tplot_data)
                else:
                    # tplot data
                    if 'time' in file[var].dimensions:
                        vindx = 1-indx
                        if indx == 1:
                            # transpose matrix if time dimension is not the first element
                            yval2 = yval2.T
                        tplot_data = {'x': unix_times, 'y': yval2}
                        # cannot create v_dim if the length of v value is 1
                        if file[file[var].dimensions[vindx]][:].size != 1:
                            tplot_data['v'] = file[file[var].dimensions[vindx]][:]
                        add_output_table(output_table, var_name, tplot_data)
                        vatt = {}
                        for attrname in file[var].ncattrs():
                            vatt[attrname] = getattr(file[var], attrname)
                        metadata[var_name] = {'var_attrs': vatt, 'global_attrs': gvars_and_atts, 'file_name': filename}
                        #print(var + ': creates tplot variable')
                    else:
                        continue
                        
            # three dimension (time and the other two)
            elif ndims == 3:
                #print('aaa')
                yval3=yval[:,:,:]
                yval3=np.array(yval3.filled(fill_value=np.nan))
                if notplot:
                    # raw data
                    tplot_data = {'y': yval}
                    add_output_table(output_table, var_name, tplot_data)
                else:
                    # tplot data 
                    
                    if 'time' in file[var].dimensions:
                    # create valid tplot variable.    It requires an information about option value.
                        #print(file[var].dimensions)
                        #print(specvarname)
                        if specvarname in file[var].dimensions:
                            vindx = file[var].dimensions.index(specvarname)
                            oindx = 3-indx-vindx;

                            # transpose matrix if time dimension is not the first element
                            yval3 = yval3.transpose(indx,vindx,oindx)
                           
                            ## create list of tplot_data
                            for n in range(yval3.shape[2]):
                                #print(yval3[:,:,:].shape)
                                tplot_data = {'x': np.array(unix_times), 'y': yval3[:,:,n]}
                                ### exception handling for rish data
                                
                                if file[file[var].dimensions[vindx]][:].size != 1:
                                    tplot_data['v'] = np.array(file[file[var].dimensions[vindx]][:])
                                if file[file[var].dimensions[vindx]][:].ndim == 2:
                                    tplot_data['v'] = file[file[var].dimensions[vindx]][n,:]
                                # create basename with suffix
                                var_name_n = var_name + '_' + file[var].dimensions[oindx] + '_' + str(n)
                                add_output_table(output_table, var_name_n, tplot_data)      
                                print(len(output_table))                                                         
                                vatt = {}
                                for attrname in file[var].ncattrs():
                                    vatt[attrname] = getattr(file[var], attrname)
                                metadata[var_name_n] = {'var_attrs': vatt, 'global_attrs': gvars_and_atts, 'file_name': filename}
                                #print(var + ': creates tplot variables')                    
                    else:
                        continue
                        
            # no dimension or four dimension (time and the other three)
            elif ndims == 0 or ndims >= 4:
                if notplot:
                    # raw data
                    tplot_data = {'y': yval}
                    add_output_table(output_table, var_name, tplot_data)
                else:
                    continue              
                
    if notplot:
        return output_table
                    
    # Store data in tplot_data_list
    for var_name in output_table.keys():
        to_merge = False
        if var_name in pytplot.data_quants.keys() and merge:
            prev_data_quant = pytplot.data_quants[var_name]
            to_merge = True
            
        try:
            attr_dict = {}
            if metadata.get(var_name) is not None:
                attr_dict["netCDF"] = {}
                attr_dict["netCDF"]["VATT"] = metadata[var_name]['var_attrs']
                attr_dict["netCDF"]["GATT"] = metadata[var_name]['global_attrs']
                attr_dict["netCDF"]["FILENAME"] = metadata[var_name]['file_name']
            store_data(var_name, data=output_table[var_name], attr_dict=attr_dict)
        except ValueError:
            continue

        if var_name not in stored_variables:
            stored_variables.append(var_name)

        if to_merge == True:
            cur_data_quant = pytplot.data_quants[var_name]
            plot_options = copy.deepcopy(pytplot.data_quants[var_name].attrs)
            merged_data = [prev_data_quant, cur_data_quant]
            pytplot.data_quants[var_name] = xr.concat(merged_data, dim='time').sortby('time')
            pytplot.data_quants[var_name].attrs = plot_options

    # If we are interested in seeing a quick plot of the variables, do it
    if plot:
        tplot(stored_variables)


    return stored_variables
