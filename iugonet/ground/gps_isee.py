"""Load function for ISEE GPS-TEC (Total Electron Content) data.

``gps_isee`` itself is a thin wrapper that validates datatype and dispatches to
a per-type sub-loader; currently the only datatype is 'atec'. The actual work
is the absolute-TEC reader, integrated into a single function here.

netCDF file structure (confirmed from the actual files):
  dimensions:  latitude (360), longitude (721), time (12)
  variables:
    lat   (latitude,)   float32  -89.9..89.6 [degrees_north]  (0.5 deg grid)
    lon   (longitude,)  float32  -180..180   [degrees_east]   (0.5 deg grid)
    time  (time,)       float64  units='seconds since YYYY-MM-DD HH:MM:SS +TZ:TZ'
    atec  (latitude, longitude, time)  float32  missing_value=999.0
                                       units='10^16 el/m^2'
  Each file covers one hour (YYYYMMDDhh) and holds 12 time steps (5-min
  interval). A full day = 24 files -> 288 time points.

  Time conversion:
    unix_time = double(time) + time_double(syymmdd/shhmmss) - double(time_diff2)
  time is seconds since the base time, so no *3600 factor (it is added
  directly). The base time's TZ is subtracted as time_diff2 to correct to true
  UT (the actual files are +00:00, so time_diff2=0 and unix=time+base).

  The missing value 999.0 is replaced with NaN.

Axis orientation (important):
  netCDF4 reads atec in C order (latitude, longitude, time), whereas ncdf_varget
  reverses the dimension order, giving atec as [time, longitude, latitude]. As
  arrays are concatenated along the leading (time) axis, the final tplot
  variable iug_gps_atec has
    y.shape = [time(=288), longitude(=721), latitude(=360)]
  (axes = [time, lon, lat]). In Python each file's atec is transposed
  (lat, lon, time) -> (time, lon, lat) and concatenated along the time axis
  (axis=0) to match the original bit-for-bit. Latitude/longitude are stored in
  the glat / glon tags (not v).

The data are not CDF, so the common load() (cdf_to_tplot) cannot be used; the
.nc files are fetched with the pyspedas ``download`` and parsed in-house with
netCDF4.

Created variable (one only):
  iug_gps_atec   x=time[UT], y=[time, lon, lat], glat=latitude[deg],
                 glon=longitude[deg]; 3-D (time x longitude x latitude).
                 ztitle='TEC [10!U16!N/m!U2!N]'.

Data distribution:
  https://stdb2.isee.nagoya-u.ac.jp/GPS/shinbori/AGRID2/nc/YYYY/DOY/YYYYMMDDhh_atec.nc
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, dailynames, download

from iugonet.config import CONFIG

# All data types. Currently only 'atec'.
DATATYPE_ALL = ["atec"]

# Base URL of the remote data directory.
REMOTE_BASE = "https://stdb2.isee.nagoya-u.ac.jp/GPS/shinbori/AGRID2/nc/"

# Created tplot variable name.
TVAR_NAME = "iug_gps_atec"

# Missing value.
FILL_VALUE = 999.0


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes.

    Preserves input order and removes duplicates.
    """
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(v).lower() for v in value]
    if "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _parse_time_units(units):
    """Parse time.units 'seconds since YYYY-MM-DD HH:MM:SS +TZ:TZ' to (base_unix, tz_sec).

    base_unix is time_double(syymmdd/shhmmss) (interpreted as UTC). The sign of
    the TZ field is honored (+ positive, - negative). If units has no TZ part,
    tz_sec=0.
    """
    parts = units.split()
    # parts = ['seconds','since','YYYY-MM-DD','HH:MM:SS','+TZ:TZ']
    syymmdd = parts[2]
    shhmmss = parts[3]
    base_unix = float(time_double(syymmdd + "/" + shhmmss))
    tz_sec = 0.0
    if len(parts) >= 5 and parts[4]:
        tzstr = parts[4]
        sign = 1.0
        if tzstr[0] in "+-":
            sign = -1.0 if tzstr[0] == "-" else 1.0
            tzstr = tzstr[1:]
        hh, _, mm = tzstr.partition(":")
        tz_sec = sign * (int(hh) * 3600.0 + (int(mm) * 60.0 if mm else 0.0))
    return base_unix, tz_sec


def _read_nc(path):
    """Read one netCDF file and return time/lat/lon/atec.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds UT,
       'lat':  (Nlat,) [deg], 'lon': (Nlon,) [deg],
       'atec': (Nt, Nlon, Nlat)}   already transposed to [time, lon, lat] order.
      Missing value 999.0 -> NaN. Returns None if unreadable/empty.
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

        latitude = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        longitude = np.asarray(ds.variables["lon"][:], dtype=np.float64)

        # atec is C order (lat, lon, time) in netCDF4.
        raw = ds.variables["atec"][:]
        arr = np.ma.filled(np.ma.asarray(raw), fill_value=FILL_VALUE)
        arr = np.asarray(arr, dtype=np.float64)
        # ncdf_varget reverses the axes -> [time, lon, lat]; transpose
        # (lat, lon, time) -> (time, lon, lat) to match.
        atec = np.transpose(arr, (2, 1, 0))
        # Missing value 999.0 -> NaN.
        atec = np.where(atec == FILL_VALUE, np.nan, atec)

        return {"time": unix_time, "lat": latitude,
                "lon": longitude, "atec": atec}
    finally:
        ds.close()


def gps_isee(
    trange=["2017-09-08", "2017-09-09"],
    datatype="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load ISEE GPS-TEC (absolute TEC) grid data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day (all hourly files for that day are fetched).
        Default: ['2017-09-08', '2017-09-09']
    datatype : str or list of str
        Type of data to load. 'all' resolves to atec. Valid options: atec
        (currently the only one; 'dtec'/'roti' may be added in the future).
        Default: 'all'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables ({name: {'x','y','glat','glon'}}) instead
        of creating tplot variables.
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
        List of tplot variables created (normally ``['iug_gps_atec']``). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Notes
    -----
    Structure of the created variable ``iug_gps_atec``:
      x  : (Nt,)  unix seconds (UT). A full day gives Nt=288 (5-min interval).
      y  : (Nt, Nlon, Nlat)  TEC [10^16 el/m^2]. axes = [time, lon, lat].
      v1 : (Nlon,)  geographic longitude [deg] (-180..180)  -> y axis1.
      v2 : (Nlat,)  geographic latitude [deg] (-89.9..89.6) -> y axis2.
      Missing values are NaN. ztitle='TEC [10!U16!N/m!U2!N]', spec=1.
    Latitude/longitude are conceptually the glat/glon tags of the data
    structure, but pyspedas store_data cannot handle a 3-D y plus arbitrary
    keys, so they are passed as v1/v2. The glat/glon values are also kept in
    attr_dict and can be retrieved via
    ``get_data(name, metadata=True)['glat'/'glon']`` (used as atec.glat/atec.glon
    in downstream routines such as keogram).

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gps_isee(trange=['2017-09-08', '2017-09-09'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    dtypes = _normalize(datatype, DATATYPE_ALL)
    if not dtypes:
        print("This datatype is not valid. Please input the allowed "
              "keywords, all or atec.")
        return {} if notplot else []

    # Currently the only datatype is atec; do nothing otherwise.
    if "atec" not in dtypes:
        return {} if notplot else []

    # ===== file download (YYYY/DOY/YYYYMMDDhh + _atec.nc, one file per hour) =====
    # dailynames(res=3600) yields the same file-name set as the hourly,
    # de-duplicated listing (24 for a full day; partials also match).
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    file_format = "%Y/%j/%Y%m%d%H_atec.nc"
    remote_names = sorted(set(
        dailynames(file_format=file_format, trange=[trange[0], trange[1]],
                   res=3600.0)
    ))

    # Local storage: CONFIG/local_data_dir/isee/gps/AGRID2/nc/...
    local_dir = os.path.join(
        CONFIG["local_data_dir"], "isee", "gps", "AGRID2", "nc"
    )
    files = download(
        remote_file=remote_names,
        remote_path=REMOTE_BASE,
        local_path=local_dir,
        no_download=no_update,
        last_version=True,
    )
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files

    if not out_files:
        print(f"No ISEE GPS-TEC (atec) data found in {trange}.")
        return {} if notplot else []

    # ===== read all files and concatenate along the time axis (axis=0) =====
    t_list = []
    atec_list = []
    latitude = None
    longitude = None
    for path in out_files:
        d = _read_nc(path)
        if d is None:
            continue
        # lat/lon are common to all files (0.5 deg fixed grid); use the last read.
        latitude = d["lat"]
        longitude = d["lon"]
        t_list.append(d["time"])
        atec_list.append(d["atec"])   # (Nt_i, Nlon, Nlat)

    if not t_list:
        print(f"No valid ISEE GPS-TEC (atec) data parsed in {trange}.")
        return {} if notplot else []

    unix_time = np.concatenate(t_list, axis=0)            # (Nt,)
    atec = np.concatenate(atec_list, axis=0)              # (Nt, Nlon, Nlat)

    # ===== edge-clip (time_clip) =====
    if time_clip:
        tmask = (unix_time >= t0) & (unix_time <= t1)
        if not np.any(tmask):
            print(f"No ISEE GPS-TEC data within trange {trange}.")
            return {} if notplot else []
        unix_time = unix_time[tmask]
        atec = atec[tmask, :, :]

    if ror:
        _print_ror()

    name = TVAR_NAME + suffix

    # notplot returns the data structure (glat/glon tags) as a dict.
    if notplot:
        return {name: {"x": unix_time, "y": atec,
                       "glat": latitude, "glon": longitude}}

    # ===== store_data =====
    # store_data treats dict keys other than x/y as xarray coordinates and fails
    # to resolve dimensions for a 3-D y plus arbitrary keys (glat/glon). Per the
    # pyspedas convention the two non-time axes are passed as v1/v2; with
    # y.shape=(time, lon, lat):
    #   v1 = longitude (721) -> y axis1, v2 = latitude (360) -> y axis2
    # (axes bind by matching length; a wrong order silently drops the
    # coordinates). The glat/glon tag meaning (atec.glat/atec.glon downstream) is
    # also kept in attr_dict so it is retrievable via get_data(metadata=True).
    store_data(
        name,
        data={"x": unix_time, "y": atec, "v1": longitude, "v2": latitude},
        attr_dict={"glat": latitude, "glon": longitude,
                   "PI_NAME": "Y. Otsuka",
                   "ztitle": "TEC [10!U16!N/m!U2!N]"},
    )
    options(name, "ztitle", "TEC [10!U16!N/m!U2!N]")
    options(name, "spec", 1)

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
          "The distribution of GPS-TEC data has been partly supported by "
          "the IUGONET (Inter-university Upper atmosphere Global Observation "
          "NETwork) project (http://www.iugonet.org/) funded by the Ministry "
          "of Education, Culture, Sports, Science and Technology (MEXT), Japan.")
