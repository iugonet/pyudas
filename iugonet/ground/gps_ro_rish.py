"""Load function for GPS Radio Occultation (RO) FSI data (RISH).

This function dispatches per satellite (site):

- ``champ``
- ``cosmic``

The two readers have identical data format and processing; they differ only in
(1) the remote URL and version directory (champ=v1_0, cosmic=v2_0) and (2) the
satellite code in the tplot variable name (champ / cosmic). Both are handled by
a single function.

Occultation data structure (UCAR FSI netCDF, confirmed from the actual files):
  dimensions:
    event (N)   number of occultation events per file (= per day), e.g. 183
    z     (600) height grid 0.0..59.9 km (0.1 km step)
  variables:
    z                          (z,)          float  height [km]
    time                       (event,)      double units='seconds since 1980-01-06 00:00:00' (GPS epoch)
    event, gpsid, leoid        (event,)             event number / GPS sat ID / LEO sat ID
    lat, lon                   (event,)      float  occultation point lat/lon [deg]
    ref, pres, temp,
    tan_lat, tan_lon           (z, event)    float  refractivity[N]/pressure[hPa]/temp[degC]/
                                                    perigee lat[deg]/perigee lon[deg]
  Time conversion:
    unix_time = double(time) + time_double('1980-01-06/00:00:00')
  The units base (1980-01-06 = start of GPS week 0) is fixed and UTC, so the
  hard-coded addition matches exactly (verified: first event = 2006-06-01
  00:05:47).

  Missing-value masking:
    ref, pres, tan_lat, tan_lon : value == -999          -> NaN
    temp                        : value <= -200 or >= 100 -> NaN
  (The temp condition also catches -999 automatically.)

  The 2-D variables are stored in netCDF as (z, event) = (height, time).
  ncdf_varget reverses the dimension order, reading them as [event, z] =
  [time, height], so store_data receives y=[time, height]. In Python (netCDF4,
  C-order) they are read as (z, event), so they are transposed (``.T``) to
  (event, z) = [time, height]. The v (height) axis uses z as-is.

The data are not CDF, so the common load() (cdf_to_tplot) cannot be used; the
.nc files are fetched with the pyspedas ``download`` and parsed in-house with
netCDF4.

Created variables (10 per satellite, in this order):
  gps_ro_{site}_fsi_event    event number          (x=time, y=event)        spec=0
  gps_ro_{site}_fsi_gpsid    GPS satellite ID      (x=time, y=gpsid)        spec=0
  gps_ro_{site}_fsi_leoid    LEO satellite ID      (x=time, y=leoid)        spec=0
  gps_ro_{site}_fsi_lat      occultation lat [deg] (x=time, y=lat)          spec=0
  gps_ro_{site}_fsi_lon      occultation lon [deg] (x=time, y=lon)          spec=0
  gps_ro_{site}_fsi_ref      refractivity [N]      (x=time, y=[t,z], v=z)   spec=1
  gps_ro_{site}_fsi_pres     dry-air pressure [hPa](x=time, y=[t,z], v=z)   spec=1
  gps_ro_{site}_fsi_temp     dry-air temp [degC]   (x=time, y=[t,z], v=z)   spec=1
  gps_ro_{site}_fsi_tan_lat  perigee lat [deg]     (x=time, y=[t,z], v=z)   spec=1
  gps_ro_{site}_fsi_tan_lon  perigee lon [deg]     (x=time, y=[t,z], v=z)   spec=1
  The five 2-D variables use ylim 0..40 km. Gap filling is applied to every
  variable.

Data distribution (daily, DOY file names):
  champ : http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/GPS/champ/fsi/v1_0/nc/
  cosmic: http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/GPS/cosmic/fsi/v2_0/nc/
  Relative path: <YYYY>/RISHANA_<YYYY>.<DOY>.nc  (DOY is 3-digit zero-padded day of year)
"""
import os

import numpy as np

from pyspedas import (store_data, options, ylim, time_double, time_string,
                      dailynames, download)
from pyspedas.tplot_tools import degap

from iugonet.tools.tdegap import tdegap

from iugonet.config import CONFIG

# All satellites (default 'all').
SITE_CODE_ALL = ["champ", "cosmic"]

# Per-satellite settings.
#   base : base URL of the remote data directory (up to the trailing nc/)
#   ver  : version (reflected only in URL/local paths; champ=v1_0, cosmic=v2_0)
SITE_INFO = {
    "champ": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/GPS/champ/fsi/v1_0/nc/",
        "ver": "v1_0",
    },
    "cosmic": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/GPS/cosmic/fsi/v2_0/nc/",
        "ver": "v2_0",
    },
}

# Common acknowledgement text (identical for champ/cosmic).
ACKNOWLEDGEMENT = (
    "If you acquire GPS radio occultation data, we ask that you acknowledge us "
    "in your use of the data. This may be done by including text such as GPS "
    "radio occultation data provided by Research Institute for Sustainable "
    "Humanosphere of Kyoto University. We would also appreciate receiving a "
    "copy of the relevant publications. The distribution of GPS radio "
    "occultation data has been partly supported by the IUGONET (Inter-university "
    "Upper atmosphere Global Observation NETwork) project "
    "(http://www.iugonet.org/) funded by the Ministry of Education, Culture, "
    "Sports, Science and Technology (MEXT), Japan."
)

# 1-D variables (x=time, y=value): (netCDF name, tplot key, ytitle), in order.
VARS_1D = [
    ("event", "event", "Event number"),
    ("gpsid", "gpsid", "GPS satellite ID"),
    ("leoid", "leoid", "LEO satellite ID"),
    ("lat",   "lat",   "Latitude [degree]"),
    ("lon",   "lon",   "Longitude [degree]"),
]

# 2-D variables (x=time, y=[time,height], v=height): (netCDF name, tplot key, ztitle).
VARS_2D = [
    ("ref",     "ref",     "Refractivity [N]"),
    ("pres",    "pres",    "Dry air pressure [hPa]"),
    ("temp",    "temp",    "Dry air temperature [degree C]"),
    ("tan_lat", "tan_lat", "Latitude of perigee point [degree]"),
    ("tan_lon", "tan_lon", "Longitude of perigee point [degree]"),
]


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes.

    Preserves input order and removes duplicates. An unspecified site
    (empty/None) is treated as 'all'.
    """
    if value is None or value == "":
        value = "all"
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


def _read_nc(path):
    """Read one netCDF (= one day) and return time/height/each variable.

    Returns
    -------
    dict or None
      {'time': (Ne,) unix seconds UT, 'height': (Nz,) km,
       'event','gpsid','leoid','lat','lon': (Ne,),
       'ref','pres','temp','tan_lat','tan_lon': (Ne, Nz)}
      Missing values are NaN. Returns None if unreadable/empty.
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
        # double(time) + time_double('1980-01-06/00:00:00') (GPS epoch)
        gps_epoch = float(time_double("1980-01-06/00:00:00"))
        unix_time = tvals + gps_epoch

        # Height z [km] is used as-is.
        height = np.asarray(ds.variables["z"][:], dtype=np.float64)

        out = {"time": unix_time, "height": height}

        # --- 1-D variables (event,) read as-is ---
        for ncname, _, _ in VARS_1D:
            arr = np.asarray(ds.variables[ncname][:], dtype=np.float64).ravel()
            out[ncname] = arr

        # --- 2-D variables (z, event) -> transpose to (event, z) ---
        for ncname, _, _ in VARS_2D:
            raw = ds.variables[ncname][:]               # (z, event)
            arr = np.ma.filled(np.ma.asarray(raw), fill_value=-999.0)
            arr = np.asarray(arr, dtype=np.float64)
            if arr.ndim == 2:
                arr = arr.T                              # -> (event, z) = [time, height]
            # missing -> NaN
            if ncname == "temp":
                # temp <= -200 or temp >= 100 -> NaN
                arr = np.where((arr <= -200.0) | (arr >= 100.0), np.nan, arr)
            else:
                # value == -999 -> NaN
                arr = np.where(arr == -999.0, np.nan, arr)
            out[ncname] = arr
        return out
    finally:
        ds.close()


def gps_ro_rish(
    trange=["2006-06-01", "2006-06-02"],
    site="all",
    datatype="",
    parameter="",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load GPS Radio Occultation (RO) FSI data from RISH.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day (per DOY daily file).
        Default: ['2006-06-01', '2006-06-02']
    site : str or list of str
        Satellite code(s). A space-separated string or a list are both accepted;
        an empty string/None is also treated as 'all'. 'all' selects every
        available satellite. Valid sites: champ (GPS/CHAMP) cosmic (GPS/COSMIC).
        Default: 'all'
    datatype : str
        Unused (accepted for compatibility).
        Default: ''
    parameter : str
        Unused (accepted for compatibility).
        Default: ''
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
        List of tplot variables created
        (``gps_ro_{site}_fsi_{event,gpsid,leoid,lat,lon,ref,pres,temp,tan_lat,tan_lon}``).
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gps_ro_rish(trange=['2006-06-01', '2006-06-02'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    if not sites:
        print("This station code is not valid. Please input the allowed "
              "keywords, all, champ, and cosmic.")
        return {} if notplot else []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])

    loaded = {} if notplot else []
    dl_files = []
    acked = False

    for st in sites:
        info = SITE_INFO[st]

        # remote_file relative path: <YYYY>/RISHANA_<YYYY>.<DOY>.nc.
        # DOY = day of year (3 digits). Enumerate daily file names (res=1 day)
        # and de-duplicate.
        file_format = "%Y/RISHANA_%Y.%j.nc"
        remote_names = sorted(set(
            dailynames(file_format=file_format, trange=trange, res=24 * 3600.0)
        ))

        # Local storage: CONFIG/local_data_dir/rish/<site>/fsi/<ver>/...
        local_dir = os.path.join(
            CONFIG["local_data_dir"], "rish", st, "fsi", info["ver"]
        )
        files = download(
            remote_file=remote_names,
            remote_path=info["base"],
            local_path=local_dir,
            no_download=no_update,
            last_version=True,
        )
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))

        if downloadonly:
            dl_files += out_files
            continue

        if not out_files:
            print(f"No GPS-RO {st.upper()} FSI data found in {trange}.")
            continue

        # ===== read all daily files and concatenate along time =====
        # The height of the last file read is used, but z is fixed across files
        # (0..59.9 km, 600 points).
        t_list = []
        d1 = {nc: [] for nc, _, _ in VARS_1D}
        d2 = {nc: [] for nc, _, _ in VARS_2D}
        height = None
        for path in out_files:
            d = _read_nc(path)
            if d is None:
                continue
            if height is None or d["height"].size > height.size:
                height = d["height"]
            t_list.append(d["time"])
            for nc, _, _ in VARS_1D:
                d1[nc].append(d[nc])
            for nc, _, _ in VARS_2D:
                d2[nc].append(d[nc])

        if not t_list:
            print(f"No valid GPS-RO {st.upper()} FSI data parsed in {trange}.")
            continue

        nz = height.size
        site_time = np.concatenate(t_list)

        # Concatenate 2-D arrays (z is fixed, but align to nz for safety).
        def _stack2(arrs):
            out = []
            for a in arrs:
                if a.shape[1] < nz:
                    pad = np.full((a.shape[0], nz - a.shape[1]), np.nan)
                    a = np.hstack([a, pad])
                elif a.shape[1] > nz:
                    a = a[:, :nz]
                out.append(a)
            return np.concatenate(out, axis=0)

        # ===== edge-clip range (UT), applied when time_clip=True =====
        if time_clip:
            tmask = (site_time >= t0) & (site_time <= t1)
            if not np.any(tmask):
                print(f"No GPS-RO {st.upper()} FSI data within trange {trange}.")
                continue
        else:
            tmask = np.ones(site_time.shape, dtype=bool)
        clipped_time = site_time[tmask]

        if ror and not acked:
            _print_ror()
            acked = True

        # ===== create the five 1-D variables =====
        for nc, key, ytitle in VARS_1D:
            name = f"gps_ro_{st}_fsi_{key}{suffix}"
            ydata = np.concatenate(d1[nc])[tmask]
            if notplot:
                loaded[name] = {"x": clipped_time, "y": ydata}
                continue
            store_data(name, data={"x": clipped_time, "y": ydata})
            options(name, "ytitle", ytitle)
            options(name, "spec", 0)
            try:
                degap(name, overwrite=True)
            except Exception:
                pass
            loaded.append(name)

        # ===== create the five 2-D variables =====
        for nc, key, ztitle in VARS_2D:
            name = f"gps_ro_{st}_fsi_{key}{suffix}"
            ydata = _stack2(d2[nc])[tmask, :]
            if notplot:
                loaded[name] = {"x": clipped_time, "y": ydata, "v": height}
                continue
            store_data(name, data={"x": clipped_time, "y": ydata, "v": height})
            options(name, "spec", 1)
            options(name, "ytitle", "Height [km]")
            options(name, "ztitle", ztitle)
            # ylim 0..40 km
            ylim(name, 0, 40)
            # Gap fill. The original IDL (iug_load_gps_{champ,cosmic}_fsi_nc.pro)
            # applies ``tdegap, /overwrite`` to each 2-D profile variable, which
            # inserts NaN rows at the (IDL-specific) gap spacing. Use the
            # IDL-faithful tdegap (iugonet.tools.tdegap) rather than
            # pyspedas degap so the inserted time rows match IDL exactly.
            tdegap(name, overwrite=True)
            loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if (not notplot) and loaded:
        print("******************************")
        print("Data loading is successful!!")
        print("******************************")

    return loaded


def _print_ror():
    """Print the Rules of the Road / acknowledgement."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(ACKNOWLEDGEMENT)
