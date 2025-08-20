import pyspedas
import numpy as np
import pytplot
from pyspedas import get_data
from pytplot import data_exists

def nn(data_in, time_in):
    """
    This function mimics the functionality of IDL's nn.pro, searching for the
    index of the data point nearest to a specified time.
    It supports 3D or higher 'y' data, 2D or higher 'v' data, and multiple
    'v' variables (v1, v2, ...).

    Parameters:
    ----------
    data_in : str or int or list/np.ndarray or dict
        A tplot variable name, index, an array of Unix times, or a dictionary-like
        data structure such as the return value from get_data().
    time_in : str or float or list of str/float
        The time(s) to search for. Can be specified as a string in
        'YYYY-MM-DD/hh:mm:ss' format, or as a Unix time (float).
        Multiple times can be specified in a list.

    Returns:
    -------
    dict
        A dictionary containing the following keys:
        'indices': A numpy.ndarray of the found indices.
        'x': An array of the nearest times found.
        'y': (if present) An array of the y data values.
        'v', 'v1', 'v2', ...: (if present) Arrays of the v data values.
        
        Returns None if the search fails.
    """

    # --- 1. Process Input Data (data_in) ---
    if isinstance(data_in, str):
        # If a tplot variable name is provided
        if not data_exists(data_in):
            print(f"Error: tplot variable '{data_in}' not found.")
            return None
        data = get_data(data_in)
        # Debug: print data structure
        # print(f"Debug: data type = {type(data)}")
        #if isinstance(data, dict):
            # print(f"Debug: data keys = {list(data.keys())}")
        # elif data is not None:
            # print(f"Debug: data content = {data}")
        
        # Handle pytplot variable object
        if hasattr(data, 'times') and hasattr(data, 'y'):
            # Convert pytplot variable to dictionary format
            data_dict = {'x': data.times, 'y': data.y}
            # Add other attributes if they exist
            for attr in dir(data):
                if not attr.startswith('_') and attr not in ['times', 'y']:
                    attr_value = getattr(data, attr)
                    if isinstance(attr_value, np.ndarray):
                        data_dict[attr] = attr_value
            data = data_dict
    elif isinstance(data_in, int):
        # If a tplot index is provided
        var_name = pytplot.tplot_names(data_in)
        if not var_name:
            print(f"Error: No tplot variable found for index '{data_in}'.")
            return None
        data = get_data(var_name[0])
    elif isinstance(data_in, (list, np.ndarray)):
        # If a time array is provided directly
        data = {'x': np.array(data_in)}
    elif isinstance(data_in, dict):
        # If a dictionary (like the output of get_data) is provided
        if 'x' in data_in:
            data = data_in
        else:
            print("Error: Dictionary input missing 'x' key.")
            return None
    else:
        print("Error: Unsupported data input format.")
        return None

    if data is None:
        print("Error: No valid time data found.")
        return None
    
    if not isinstance(data, dict) or 'x' not in data:
        print("Error: Invalid data format - missing 'x' key.")
        return None
    
    if len(data['x']) == 0:
        print("Error: No valid time data found.")
        return None
    
    source_times = data['x']

    # --- 2. Process Input Time (time_in) ---
    target_times_unix = pyspedas.time_double(time_in)
    if not isinstance(target_times_unix, (list, np.ndarray)):
        target_times_unix = [target_times_unix]
    target_times_unix = np.array(target_times_unix)
    
    # --- 3. Calculate Nearest Indices ---
    # Efficiently calculate using NumPy broadcasting
    diffs = np.abs(source_times[:, np.newaxis] - target_times_unix)
    nearest_indices = diffs.argmin(axis=0)

    # --- 4. Construct the Result ---
    result = {'indices': nearest_indices}
    result['x'] = source_times[nearest_indices]

    # Process all data variables starting with 'y' or 'v'
    for key, value in data.items():
        if key == 'x' or key == 'time': # Skip the time axis
             continue
        
        # Ensure it's a NumPy array
        if isinstance(value, np.ndarray):
            # Use powerful NumPy slicing (...) for multidimensional arrays
            sliced_value = value[nearest_indices, ...]
            
            # If input was a single time (scalar), squeeze the first dimension
            if len(nearest_indices) == 1:
                sliced_value = np.squeeze(sliced_value, axis=0)
            
            result[key] = sliced_value
            
    return result