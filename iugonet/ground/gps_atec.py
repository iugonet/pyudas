"""Load function for ISEE GPS absolute TEC global-grid data.

This is the worker behind ``gps_isee`` with datatype='atec'. It downloads the
absolute GPS-TEC grid data from the Nagoya University ISEE server and creates a
single tplot variable ``iug_gps_atec``.

netCDF file structure (confirmed from the actual files, 2017-09-08 example):
  dimensions:  time (12; 5-min/hour), latitude (360), longitude (721)
  variables:
    lat  (latitude,)               float32  latitude  [deg]  -89.9..89.6 (0.5 deg)
    lon  (longitude,)              float32  longitude [deg]  -180..180   (0.5 deg)
    time (time,)                   float64  units='seconds since YYYY-MM-DD HH:MM:SS +TZ:TZ'
    atec (latitude, longitude, time) float32  absolute TEC [10^16 el/m^2]
                                            missing_value = 999.0

Time conversion:
  unix_time[i] = double(time[i]) + time_double(syymmdd/shhmmss) - double(time_diff2)
  Here time is the elapsed seconds since (LT) midnight of the day. time_double
  interprets the base string as UTC, so the TZ offset time_diff2 from the end of
  units is subtracted to correct to true UT. time is already in seconds, so no
  *3600 factor is applied. The actual TZ is +00:00 (time_diff2=0), and the
  result matches netCDF4 num2date.

Array axis order (important for matching the original output):
  ncdf_varget reverses the netCDF header axis order, so the header
  ``atec(latitude, longitude, time)`` becomes ``atec[time, longitude, latitude]``
  (shape [12,721,360]). The ``y`` passed to store_data is stored in this
  ``[time, lon, lat]`` order, consistent with the keogram routine's
  ``reform(atec.y[*, index_glong, *])`` (axis0=time->x, axis1=lon->glon,
  axis2=lat->glat). In numpy the netCDF array (lat,lon,time) is obtained via
  transpose(2,1,0).

The missing value 999.0 is replaced with NaN.

The data are not CDF, so the common load() (cdf_to_tplot) cannot be used; the
.nc files are fetched with the pyspedas ``download`` and parsed in-house with
netCDF4.

Created variable (one):
  iug_gps_atec   data = {x: time[UT], y: atec[time,lon,lat], v1: glon, v2: glat}
                 pyspedas expresses the extra coordinates of a 3-D y via v1/v2
                 (v1=longitude lon=axis1, v2=latitude lat=axis2). The glat/glon
                 values are also kept in dlimit (metadata). dlimit.data_att holds
                 acknowledgment and PI_NAME='Y. Otsuka', and the option
                 ztitle='TEC [10^16/m^2]' is set.

Data distribution:
  https://stdb2.isee.nagoya-u.ac.jp/GPS/shinbori/AGRID2/nc/YYYY/DOY/YYYYMMDDhh_atec.nc
  One file per hour (~12 MB), fetched with last_version.
"""
import os

import numpy as np

from pyspedas import (store_data, options, time_double, time_string,
                      dailynames, download)
from pyspedas.tplot_tools import clip

from iugonet.config import CONFIG

REMOTE_DATA_DIR = "https://stdb2.isee.nagoya-u.ac.jp/GPS/shinbori/AGRID2/nc/"

# Daily file format. dailynames tokens: %Y=YYYY, %j=DOY(3 digits), %m,%d, %H=hh.
FILE_FORMAT = "%Y/%j/%Y%m%d%H_atec.nc"

# Missing value.
MISSING_VALUE = 999.0

# The only datatype for this product is 'atec'.
DATATYPE_ALL = ["atec"]

# tplot variable name.
TVAR_NAME = "iug_gps_atec"

# Acknowledgement string.
ACKNOWLEDG_STRING = (
    "Note: If you would like to use following data for scientific purpose, "
    "please read and follow the DATA USE POLICY "
    "(https://stdb2.isee.nagoya-u.ac.jp/GPS/GPS-TEC/index.html) "
    "The distribution of GPS-TEC data has been partly supported by the IUGONET "
    "(Inter-university Upper atmosphere Global Observation NETwork) project "
    "(http://www.iugonet.org/) funded by the Ministry of Education, Culture, "
    "Sports, Science and Technology (MEXT), Japan."
)


def _parse_time_units(units):
    """Parse time.units 'seconds since YYYY-MM-DD HH:MM:SS +TZ:TZ' to (base_unix, tz_sec).

    base_unix is time_double(syymmdd/shhmmss) (interpreted as UTC). If the TZ
    field is absent, tz_sec=0. A signed integer is read for the offset; the hour
    sign carries through to the whole offset (td[0] is signed, e.g. '+09'), so
    the result matches the original output.
    """
    parts = units.split()
    # parts = ['seconds','since','YYYY-MM-DD','HH:MM:SS','+TZ:TZ']
    syymmdd = parts[2]
    shhmmss = parts[3]
    base_unix = float(time_double(syymmdd + "/" + shhmmss))
    tz_sec = 0.0
    if len(parts) >= 5 and parts[4]:
        td = parts[4].split(":")
        hh = _idl_fix(td[0])
        mm = _idl_fix(td[1]) if len(td) > 1 else 0
        tz_sec = float(hh) * 3600.0 + float(mm) * 60.0
    return base_unix, tz_sec


def _idl_fix(s):
    """Read the leading signed integer from a string (mimics the original)."""
    import re
    m = re.match(r"[+-]?\d+", s.strip())
    return int(m.group()) if m else 0


def _read_nc(path):
    """Read one netCDF file and return time/lat/lon/atec.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds UT,
       'lat': (Nlat,), 'lon': (Nlon,),
       'atec': (Nt, Nlon, Nlat) in [time,lon,lat] order, missing 999 -> NaN}
      Returns None if unreadable/empty.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec = _parse_time_units(tvar.units)
        # unix_time = time + base - tz_sec (time is already in seconds)
        unix_time = tvals + base_unix - tz_sec

        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)

        # netCDF atec(latitude, longitude, time); ncdf_varget reverses the axes
        # to [time, longitude, latitude], so transpose(2,1,0) gives the same order.
        raw = ds.variables["atec"][:]
        arr = np.ma.filled(np.ma.asarray(raw), fill_value=MISSING_VALUE)
        arr = np.asarray(arr, dtype=np.float64)
        atec = np.transpose(arr, (2, 1, 0))   # (time, lon, lat)
        # Missing value 999.0 -> NaN.
        atec = np.where(atec == MISSING_VALUE, np.nan, atec)

        return {"time": unix_time, "lat": lat, "lon": lon, "atec": atec}
    finally:
        ds.close()


def gps_atec(
    trange=["2017-09-08", "2017-09-09"],
    datatype="atec",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load ISEE GPS absolute TEC global-grid data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. One file per hour
        (~12 MB) is fetched; each hourly file within the range is downloaded and
        concatenated along time.
        Default: ['2017-09-08', '2017-09-09']
    datatype : str
        Type of data to load. 'atec' is the only valid value for this product.
        Default: 'atec'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables ({TVAR: {x, y, glat, glon}}) instead of
        creating tplot variables.
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    verbose : int
        Verbosity level for diagnostic messages.
        Default: 2
    ror : bool
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created (``['iug_gps_atec'+suffix]``). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Notes
    -----
    The created variable ``iug_gps_atec`` is
    ``data = {x: time[UT s], y: atec[time, lon, lat], v1: longitude lon,
    v2: latitude lat}``. Longitude/latitude are expressed via the pyspedas 3-D
    spectrogram coordinate convention (v1=axis1, v2=axis2); the glat/glon values
    are also stored in metadata (dlimit). The ``y`` axis order is
    ``[time, lon, lat]`` to match ncdf_varget (reversed axes). Missing value
    999.0 is mapped to NaN.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gps_atec(trange=['2017-09-08', '2017-09-09'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    # The only datatype is 'atec'; accept but validate the argument.
    if isinstance(datatype, str):
        dt_items = datatype.lower().split()
    else:
        dt_items = [str(d).lower() for d in datatype]
    if "all" not in dt_items and not any(d in DATATYPE_ALL for d in dt_items):
        print("This datatype is not valid. Please input the allowed keyword, "
              "'atec'.")
        return {} if notplot else []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])

    # Enumerate hourly file names and de-duplicate.
    remote_names = sorted(set(
        dailynames(file_format=FILE_FORMAT, trange=trange, res=3600.0)
    ))

    # Local storage: CONFIG/local_data_dir/isee/gps/AGRID2/nc/...
    local_dir = os.path.join(
        CONFIG["local_data_dir"], "isee", "gps", "AGRID2", "nc"
    )
    files = download(
        remote_file=remote_names,
        remote_path=REMOTE_DATA_DIR,
        local_path=local_dir,
        no_download=no_update,
        last_version=True,
    )
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files

    if not out_files:
        print(f"No GPS-ATEC data found in {trange}.")
        return {} if notplot else []

    # ===== read all files and concatenate along time =====
    # The lat/lon grid is identical in every file (0.5 deg, 360x721); the
    # lat/lon of the last successfully read file is used.
    t_list = []
    atec_list = []
    glat = None
    glon = None
    for path in out_files:
        d = _read_nc(path)
        if d is None:
            continue
        t_list.append(d["time"])
        atec_list.append(d["atec"])   # (Nt, Nlon, Nlat)
        glat = d["lat"]
        glon = d["lon"]

    if not t_list:
        print(f"No valid GPS-ATEC data parsed in {trange}.")
        return {} if notplot else []

    time_arr = np.concatenate(t_list)          # (Ntotal,)
    atec_arr = np.concatenate(atec_list, axis=0)   # (Ntotal, Nlon, Nlat)

    # ===== edge-clip (time_clip) =====
    if time_clip:
        tmask = (time_arr >= t0) & (time_arr <= t1)
        if not np.any(tmask):
            print(f"No GPS-ATEC data within trange {trange}.")
            return {} if notplot else []
        time_arr = time_arr[tmask]
        atec_arr = atec_arr[tmask, :, :]

    name = TVAR_NAME + suffix

    if notplot:
        if ror:
            _print_ror()
        # Return the {x,y,glat,glon} structure as a dict.
        return {name: {"x": time_arr, "y": atec_arr,
                       "glat": glat, "glon": glon}}

    # glat/glon are also kept in metadata (for keogram/2dmap use).
    dlimit = {"data_att": {"acknowledgment": ACKNOWLEDG_STRING,
                           "PI_NAME": "Y. Otsuka",
                           "glat": glat, "glon": glon}}
    # In pyspedas a 3-D y uses v1/v2 as extra coordinates (v1=lon=axis1, v2=lat=axis2).
    store_data(name, data={"x": time_arr, "y": atec_arr,
                           "v1": glon, "v2": glat}, attr_dict=dlimit)
    options(name, "ztitle", "TEC [10^16/m^2]")

    if ror:
        _print_ror()

    print("******************************")
    print("Data loading is successful!!")
    print("******************************")

    return [name]


def _print_ror():
    """Print the acknowledgement (Rules of the Road)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("Note: If you would like to use following data for scientific "
          "purpose, please read and follow the DATA USE POLICY "
          "(https://stdb2.isee.nagoya-u.ac.jp/GPS/GPS-TEC/index.html). "
          "The distribution of GPS-TEC data has been partly supported by the "
          "IUGONET (Inter-university Upper atmosphere Global Observation "
          "NETwork) project (http://www.iugonet.org/) funded by the Ministry "
          "of Education, Culture, Sports, Science and Technology (MEXT), Japan.")
