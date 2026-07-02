"""Load function for NICT GAIA model (CPL part) output data.

GAIA (Ground-to-topside model of Atmosphere and Ionosphere for Aeronomy) is an
atmosphere-ionosphere coupled model developed by NICT, Kyushu University, and
Seikei University. The CPL part is 4-D (time x longitude x latitude x altitude)
gridded model output.

netCDF file structure:
  dimensions:  lon(145), lat(91), lvl(81), time(48, unlimited)
  variables:
    lon   (lon,)   float32  longitude [degrees_east]  0..360 (2.5 deg step)
    lat   (lat,)   float32  latitude  [degrees_north] +90..-90 (2 deg step)
    lvl   (lvl,)   float32  altitude  [km]  0..1866.7
    time  (time,)  float32  units='hours since YYYY-MM-DD H:M:S TZ'  0.25..23.75
    <param> (time, lvl, lat, lon) float32  with long_name/units
  Time conversion:
    Split time.units on whitespace and use field[2] (the date 'YYYY-MM-DD')
    only. unix_time[i] = time_double(syymmdd + '/00:00:00') + time[i]*3600.
  No time-zone correction is applied: the trailing TZ in the units (e.g. 'UTC')
  is ignored, to match the original output.

  The fill value 0.0 is replaced with NaN.

Data-array dimension order (important):
  netCDF4 reads in the native order (time, lvl, lat, lon). The original
  pipeline reorders this to (time, lon, lat, alt); this implementation matches
  that final array by transposing (time, lvl, lat, lon) with axes (0, 3, 2, 1)
  = (time, lon, lat, alt).

Because the data are netCDF rather than CDF, the shared loader is not used; .nc
files are fetched with pyspedas ``download`` (the NICT server uses digest
authentication) and parsed locally with netCDF4.

Created variable (one per parameter):
  gaia_cpl_<param>   x=time[unix], y=[time, lon, lat, alt] (4D),
                     v1=lon[deg], v2=lat[deg], v3=alt[km], spec=1.
  ztitle = '<long_name> [<units>]'.
  For compatibility with the original data = {x, y, glat, glon, alt}, glat/glon/
  alt are also kept in attrs (data_att) for keogram-style post-processing.

Server (digest authentication required; supply uname/passwd):
  https://aer-nc-web.nict.go.jp/gaia/wk3/gaia/<param>_cpl/YYYY/<param>YYYYMMDDcpl.nc
"""
import os

import numpy as np

from pyspedas import (store_data, options, time_double, dailynames, download)

from iugonet.config import CONFIG

# Available parameters (19 total).
PARAMETER_ALL = [
    "xoi", "xo2i", "xn2i", "xnoi", "ginao", "ginmo", "ginmn", "ginuu",
    "ginvv", "ginww", "te", "ti", "gintmp", "efr", "eft", "efp",
    "cur", "cut", "cup",
]

# NICT GAIA CPL remote server (digest authentication).
REMOTE_BASE = "https://aer-nc-web.nict.go.jp/gaia/wk3/gaia/"


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order preserved, deduped)."""
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


def _parse_time_base(units):
    """Get the base unix seconds from 'hours since YYYY-MM-DD H:M:S [TZ]'.

    Splits the units on whitespace, uses field[2] (the date) only, and takes
    00:00:00 of that date as the base time; the time-of-day field and the TZ are
    discarded, to match the original output.
    """
    parts = units.split()
    # parts = ['hours', 'since', 'YYYY-MM-DD', 'H:M:S', ('TZ')]
    syymmdd = parts[2]
    return float(time_double(syymmdd + "/00:00:00"))


def _read_nc(path, param):
    """Read one GAIA CPL netCDF file and return coordinates, data, and metadata.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds, 'lon': (Nlon,), 'lat': (Nlat,),
       'alt': (Nlvl,), 'data': (Nt, Nlon, Nlat, Nlvl) float32 (fill 0.0 -> NaN),
       'long_name': str, 'units': str}
      None if unreadable, missing the target variable, or empty.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        if param not in ds.variables or "time" not in ds.variables:
            return None
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix = _parse_time_base(tvar.units)
        unix_time = base_unix + tvals * 3600.0

        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        alt = np.asarray(ds.variables["lvl"][:], dtype=np.float64)

        dvar = ds.variables[param]
        raw = np.ma.filled(np.ma.asarray(dvar[:]), fill_value=0.0)
        data = np.asarray(raw, dtype=np.float32)
        # netCDF native (time, lvl, lat, lon) -> final (time, lon, lat, alt)
        # via transpose axes (0, 3, 2, 1).
        data = np.transpose(data, (0, 3, 2, 1))
        # Fill value 0.0 -> NaN.
        data = np.where(data == 0.0, np.nan, data)

        long_name = getattr(dvar, "long_name", "") if hasattr(dvar, "long_name") else ""
        units = getattr(dvar, "units", "") if hasattr(dvar, "units") else ""

        return {
            "time": unix_time,
            "lon": lon,
            "lat": lat,
            "alt": alt,
            "data": data,
            "long_name": str(long_name),
            "units": str(units),
        }
    finally:
        ds.close()


def gaia_cpl_nc(
    trange=["2017-09-07", "2017-09-08"],
    parameter="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    uname=None,
    passwd=None,
    suffix="",
    verbose=2,
    ror=True,
):
    """Load NICT GAIA model (CPL part) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Data are read in daily
        files; a full day is read even for a sub-day range.
        Default: ['2017-09-07', '2017-09-08']
    parameter : str or list of str
        Physical parameter(s) to load. A space-separated string ('xoi efp') or
        a list are both accepted. 'all' loads every parameter. Valid options:
        xoi xo2i xn2i xnoi ginao ginmo ginmn ginuu ginvv ginww te ti gintmp efr
        eft efp cur cut cup.
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
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    uname : str or None
        Username for the NICT server's digest authentication.
        Default: None
    passwd : str or None
        Password for the NICT server's digest authentication.
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
        List of tplot variables created (``gaia_cpl_<param>``). Empty list if no
        data were loaded. If ``downloadonly`` is set, the list of downloaded
        file paths is returned; if ``notplot`` is set, a dictionary of data is
        returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gaia_cpl_nc(trange=['2017-09-07', '2017-09-08'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    params = _normalize(parameter, PARAMETER_ALL)
    if not params:
        print("This parameter is not valid. Please input the allowed keywords, "
              "all, " + ", ".join(PARAMETER_ALL) + ".")
        return {} if notplot else []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])

    loaded = {} if notplot else []
    dl_files = []

    for pr in params:
        # Remote relative path: <pr>_cpl/%Y/<pr>%Y%m%dcpl.nc.
        file_format = pr + "_cpl/%Y/" + pr + "%Y%m%dcpl.nc"
        remote_names = sorted(set(
            dailynames(file_format=file_format, trange=trange, res=24 * 3600.0)
        ))

        # Local destination: CONFIG/local_data_dir/gaia/wk3/gaia/...
        local_dir = os.path.join(
            CONFIG["local_data_dir"], "gaia", "wk3", "gaia"
        )
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
            print(f"No GAIA CPL {pr} data found in {trange}.")
            continue

        # ===== Read all files and concatenate along time =====
        t_list = []
        data_list = []
        lon = lat = alt = None
        long_name = units = ""
        for path in out_files:
            d = _read_nc(path, pr)
            if d is None:
                continue
            # The coordinates (lon/lat/alt) are assumed invariant across files;
            # use the last values read, along with the last file's
            # long_name/units.
            lon, lat, alt = d["lon"], d["lat"], d["alt"]
            long_name, units = d["long_name"], d["units"]
            t_list.append(d["time"])
            data_list.append(d["data"])

        if not t_list:
            print(f"No valid GAIA CPL {pr} data parsed in {trange}.")
            continue

        cpl_time = np.concatenate(t_list)
        cpl_data = np.concatenate(data_list, axis=0)  # (time, lon, lat, alt)

        # ===== Edge-clip (UT) =====
        if time_clip:
            tmask = (cpl_time >= t0) & (cpl_time <= t1)
            if not np.any(tmask):
                print(f"No GAIA CPL {pr} data within trange {trange}.")
                continue
            cpl_time = cpl_time[tmask]
            cpl_data = cpl_data[tmask, :, :, :]

        if ror:
            _print_ror()

        name = f"gaia_cpl_{pr}{suffix}"
        ztitle = (long_name + " [" + units + "]") if (long_name or units) else ""

        if notplot:
            loaded[name] = {
                "x": cpl_time, "y": cpl_data,
                "v1": lon, "v2": lat, "v3": alt,
            }
            continue

        # v1=lon, v2=lat, v3=alt correspond to y axes 1,2,3.
        store_data(name, data={
            "x": cpl_time, "y": cpl_data,
            "v1": lon, "v2": lat, "v3": alt,
        })
        options(name, "spec", 1)
        if ztitle:
            options(name, "ztitle", ztitle)
        # Keep glat/glon/alt and the PI information in the xarray attrs for
        # compatibility with data = {x, y, glat, glon, alt}, so keogram-style
        # post-processing can reference them by name (v1=glon, v2=glat, v3=alt).
        _set_attrs(name, {
            "data_att": {"acknowledgment": "", "PI_NAME": "C. Tao"},
            "glon": lon, "glat": lat, "alt": alt,
        })
        loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if (not notplot) and loaded:
        print("******************************")
        print("Data loading is successful!!")
        print("******************************")

    return loaded


def _set_attrs(name, extra):
    """Add arbitrary keys to a tplot variable's xarray attrs.

    pyspedas options() rejects keys other than known options, so ancillary
    metadata such as glat/glon/alt and the PI information are written directly
    to attrs. Does nothing if the variable does not exist.
    """
    try:
        from pyspedas.tplot_tools import data_quants
        dq = data_quants.get(name)
        if dq is None:
            return
        dq.attrs.update(extra)
    except Exception:
        pass


def _print_ror():
    """Print the acknowledgement."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("Note: If you would like to use following data for scientific purpose, "
          "please read and follow the DATA USE POLICY. The dataset used for this "
          "study is from the Ground-to-topside model of Atmosphere and Ionosphere "
          "for Aeronomy (GAIA) project carried out by the National Institute of "
          "Information and Communications Technology (NICT), Kyushu University, and "
          "Seikei University. The distribution of GAIA data has been partly "
          "supported by the IUGONET (Inter-university Upper atmosphere Global "
          "Observation NETwork) project (http://www.iugonet.org/) funded by the "
          "Ministry of Education, Culture, Sports, Science and Technology (MEXT), "
          "Japan.")
