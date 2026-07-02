"""Load function for NICT GAIA GCM model output.

GAIA (Ground-to-topside model of Atmosphere and Ionosphere for Aeronomy) is a
coupled atmosphere-ionosphere model; this function fetches the gridded output of
its GCM (general circulation model) part from the NICT server and loads it into
tplot format.

netCDF file structure:
  dimensions: lon(128), lat(64), lvl(150), time(24, unlimited)
  variables:
    lon  (lon,)   float32  longitude 0..357.1875 [degrees_east]
    lat  (lat,)   float32  latitude 87.86..-87.86 [degrees_north]  (descending)
    lvl  (lvl,)   float32  pressure level 997.5..1.0e-9 [hPa]  (descending, surface first)
    time (time,)  float32  units='hours since YYYY-MM-DD H:M:S UTC'
    <param> main variable. The dimensionality is 4D or 3D depending on parameter:
      4D: (time, lvl, lat, lon)  e.g. gu (eastward wind velocity) [m s-1]
      3D: (time, lat, lon)       e.g. gp (surface_air_pressure) [hPa]; no lvl

Time conversion:
    syymmdd   = date field of time.units
    unix_time = time_double(syymmdd+'/00:00:00') + time*3600.0
  The units reference is UTC, so no time-zone correction is needed. This matches
  the UT returned by netCDF4.num2date(units=...) exactly.

Axis order (important for matching the original UDAS output bit-for-bit):
  The original output stores y as [time, lon, lat, lvl] (4D) / [time, lon, lat]
  (3D). In netCDF4 <param>[:] is (time, lvl, lat, lon), so
    4D: transpose (0,3,2,1) -> (time, lon, lat, lvl)
    3D: transpose (0,2,1)   -> (time, lon, lat)
  reproduces the original y element-for-element.

Missing values:
  Grid points whose value is exactly 0.0 are replaced with NaN. This data
  (gu/gp etc.) often contains no 0.0, but the masking is kept to match the
  original behavior.

These are not CDF files, so the shared load() (cdf_to_tplot) cannot be used. The
.nc files are fetched with pyspedas ``download`` (HTTP Digest authentication
supported) and parsed directly with netCDF4 before calling ``store_data``.

Variables produced (one per parameter):
  gaia_gcm_<param>
    4D: y=[time,lon,lat,lvl], v1=lon, v2=lat, v3=lvl,
        ztitle = '<long_name> [<units>]'
    3D: y=[time,lon,lat],     v1=lon, v2=lat  (no ztitle for 3D)
  The original passes named tags {x,y,glat,glon,press} to store_data, but the
  pytplot xarray backend only accepts the trailing axes of a multidimensional y
  as v1/v2/v3. So
    v1=glon(lon), v2=glat(lat), v3=press(lvl, 4D only)
  are assigned, and the named coordinates are additionally saved in
  attrs['data_att'] ({'glon','glat','press','PI_NAME':'C. Tao'}) so that the
  gaia_gcm_keogram / gaia_gcm_2dmap functions can reference them by name. When
  notplot=True, the {x,y,glat,glon,press} dictionary is returned as-is.

Data distribution:
  https://aer-nc-web.nict.go.jp/gaia/wk3/gaia/<param>_gcm/YYYY/<param>YYYYMMDDgcm.nc
  HTTP Digest authentication (realm=gaia_wk3) is required; supply uname/passwd.
  Parameters: gao gmo gu gv gw gt gz gvw gr gp (gp is 3D, the rest are 4D).
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, dailynames, download
from pyspedas.tplot_tools import data_quants

from iugonet.config import CONFIG

PARAMETER_ALL = ["gao", "gmo", "gu", "gv", "gw", "gt", "gz", "gvw", "gr", "gp"]

# base URL of the remote data directory
REMOTE_BASE = "https://aer-nc-web.nict.go.jp/gaia/wk3/gaia/"

# prefix of the output tplot variable names
PREFIX = "gaia_gcm_"


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order preserved, deduplicated)."""
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
    """Parse time.units 'hours since YYYY-MM-DD H:M:S [TZ]' into the base unix seconds.

    The units reference is UTC (with a 0:0:0 time part), so only the date field
    is used: base = time_double(syymmdd + '/00:00:00').
    """
    parts = units.split()
    syymmdd = parts[2]
    return float(time_double(syymmdd + "/00:00:00"))


def _read_nc(path, param):
    """Read one netCDF file and return time/coordinates/main variable in the original axis order.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds UT, 'lat': (Nlat,), 'lon': (Nlon,),
       'lvl': (Nlvl,) or None,
       'y'  : 4D (Nt, Nlon, Nlat, Nlvl) or 3D (Nt, Nlon, Nlat),
       'ndim': 4 or 3,
       'long_name': str, 'units': str}
      A value of exactly 0.0 becomes NaN. None if the file is unreadable, empty,
      or missing the main variable.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        if param not in ds.variables:
            return None
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix = _parse_time_units(tvar.units)
        # unix_time = time_double(syymmdd/00:00:00) + time*3600
        unix_time = base_unix + tvals * 3600.0

        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)

        var = ds.variables[param]
        raw = np.ma.filled(np.ma.asarray(var[:]), fill_value=0.0)
        data = np.asarray(raw, dtype=np.float64)   # (time, lvl, lat, lon) or (time, lat, lon)

        long_name = getattr(var, "long_name", "")
        var_units = getattr(var, "units", "")

        if data.ndim == 4:
            # netCDF (time, lvl, lat, lon) -> (time, lon, lat, lvl)
            y = np.transpose(data, (0, 3, 2, 1))
            lvl = np.asarray(ds.variables["lvl"][:], dtype=np.float64)
            ndim = 4
        elif data.ndim == 3:
            # netCDF (time, lat, lon) -> (time, lon, lat)
            y = np.transpose(data, (0, 2, 1))
            lvl = None
            ndim = 3
        else:
            return None

        # mask the main variable: a value of exactly 0.0 -> NaN
        y = np.where(y == 0.0, np.nan, y)

        return {
            "time": unix_time,
            "lat": lat,
            "lon": lon,
            "lvl": lvl,
            "y": y,
            "ndim": ndim,
            "long_name": long_name,
            "units": var_units,
        }
    finally:
        ds.close()


def gaia_gcm_nc(
    trange=["2017-09-07", "2017-09-08"],
    parameter="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    uname=None,
    passwd=None,
    suffix="",
    verbose=2,
    ror=True,
):
    """Load NICT GAIA GCM model output (netCDF).

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Daily files (YYYYMMDD)
        are fetched. A full day is always read even if trange spans less than a
        day.
        Default: ['2017-09-07', '2017-09-08']
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter (all 10). A
        space-separated string ('gu gv') or a list are both accepted. Valid
        options: gao gmo gu gv gw gt gz gvw gr gp. gp is 3D (surface air
        pressure); the rest are 4D.
        Default: 'all'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
    uname : str or None
        Username for the NICT server's HTTP Digest authentication.
        Default: None
    passwd : str or None
        Password for the NICT server's HTTP Digest authentication.
        Default: None
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)
    verbose : int
        Verbosity level for diagnostic messages.
        Default: 2
    ror : bool
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True

    Returns
    -------
    list of str
        List of tplot variables created (``gaia_gcm_<param>``). Empty list if no
        data were loaded. If ``downloadonly`` is set, the list of downloaded file
        paths is returned; if ``notplot`` is set, a dictionary of data is
        returned instead.

    Notes
    -----
    Each ``gaia_gcm_<param>`` keeps the coordinates glat/glon(/press) in addition
    to y (referenced by the later gaia_gcm_keogram / gaia_gcm_2dmap functions).
    Each file is large (~118 MB for 4D), so reading many parameters x many days
    at once incurs a heavy download/memory load.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gaia_gcm_nc(trange=['2017-09-07', '2017-09-08'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    params = _normalize(parameter, PARAMETER_ALL)
    if not params:
        print("This parameter is not valid. Please input the allowed keywords, "
              "all, gao, gmo, gu, gv, gw, gt, gz, gvw, gr, gp.")
        return {} if notplot else []

    # Fetch window: daily file names are generated for each day overlapping
    # trange and deduplicated. dailynames does not include the end day when the
    # end is exactly 00:00:00, so a 1-day request reads a single file.
    loaded = {} if notplot else []
    dl_files = []
    last_meta = None

    for pr in params:
        # remote_file relative path: <pr>_gcm/%Y/<pr>%Y%m%dgcm.nc
        file_format = pr + "_gcm/%Y/" + pr + "%Y%m%dgcm.nc"
        remote_names = sorted(set(
            dailynames(file_format=file_format, trange=trange,
                       res=24 * 3600.0)
        ))

        # local destination: CONFIG/local_data_dir/gaia/wk3/gaia/<pr>_gcm/...
        # the remote relative path (<pr>_gcm/...) is recreated under local.
        local_dir = os.path.join(CONFIG["local_data_dir"], "gaia", "wk3", "gaia")

        files = download(
            remote_file=remote_names,
            remote_path=REMOTE_BASE,
            local_path=local_dir,
            username=uname,
            password=passwd,
            no_download=no_update,
            last_version=True,
        )
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))

        if downloadonly:
            dl_files += out_files
            continue

        if not out_files:
            print(f"No GAIA GCM {pr} data found in {trange}.")
            continue

        # ===== read every file and concatenate along time =====
        t_list = []
        y_list = []
        lat = lon = lvl = None
        ndim = None
        long_name = var_units = ""
        for path in out_files:
            d = _read_nc(path, pr)
            if d is None:
                continue
            # use the coordinates/attributes of the last file read.
            lat, lon, lvl = d["lat"], d["lon"], d["lvl"]
            ndim = d["ndim"]
            long_name, var_units = d["long_name"], d["units"]
            t_list.append(d["time"])
            y_list.append(d["y"])

        if not t_list:
            print(f"No valid GAIA GCM {pr} data parsed in {trange}.")
            continue

        site_time = np.concatenate(t_list)
        ydata = np.concatenate(y_list, axis=0)

        name = PREFIX + pr + suffix

        if notplot:
            # return the named tags {x,y,glat,glon,press}.
            d_np = {"x": site_time, "y": ydata, "glat": lat, "glon": lon}
            if ndim == 4:
                d_np["press"] = lvl
            loaded[name] = d_np
            last_meta = (pr, long_name, var_units, ndim)
            continue

        # The pytplot/xarray store_data treats every dict key other than x,y as a
        # coordinate dimension and does not accept the named tags (glat/glon/press)
        # directly; the trailing axes of a multidimensional y must be given as
        # v1,v2,v3. For y[time,lon,lat,(lvl)] assign
        #   v1 = glon (lon), v2 = glat (lat), v3 = press (lvl, 4D only)
        # so that y matches the original element for element.
        if ndim == 4:
            data = {"x": site_time, "y": ydata,
                    "v1": lon, "v2": lat, "v3": lvl}
        else:
            data = {"x": site_time, "y": ydata, "v1": lon, "v2": lat}

        store_data(name, data=data)

        # Save the named coordinates glat/glon/press in attrs['data_att'] so the
        # later gaia_gcm_keogram / gaia_gcm_2dmap functions can reference them by
        # name.
        try:
            dq = data_quants[name]
            data_att = {"glon": lon, "glat": lat}
            if ndim == 4:
                data_att["press"] = lvl
            data_att["PI_NAME"] = "C. Tao"
            dq.attrs.setdefault("data_att", {})
            dq.attrs["data_att"].update(data_att)
        except Exception:
            pass

        # set ztitle for 4D only (no options on the 3D branch)
        if ndim == 4:
            options(name, "ztitle", f"{long_name} [{var_units}]")
        loaded.append(name)

        last_meta = (pr, long_name, var_units, ndim)

    if downloadonly:
        return sorted(set(dl_files))

    if ror and last_meta is not None:
        _print_ror()

    if (not notplot) and loaded:
        print("******************************")
        print("Data loading is successful!!")
        print("******************************")

    return loaded


def _print_ror():
    """Print the Rules of the Road / acknowledgement (DATA USE POLICY)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("Note: If you would like to use following data for scientific purpose, "
          "please read and follow the DATA USE POLICY "
          "(https://gaia-web.nict.go.jp/data_e.html). The dataset used for this "
          "study is from the Ground-to-topside model of Atmosphere and Ionosphere "
          "for Aeronomy (GAIA) project carried out by the National Institute of "
          "Information and Communications Technology (NICT), Kyushu University, "
          "and Seikei University. The distribution of GAIA data has been partly "
          "supported by the IUGONET (Inter-university Upper atmosphere Global "
          "Observation NETwork) project (http://www.iugonet.org/) funded by the "
          "Ministry of Education, Culture, Sports, Science and Technology (MEXT), "
          "Japan.")
