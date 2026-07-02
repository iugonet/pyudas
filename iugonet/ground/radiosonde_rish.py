"""Load function for RISH (Kyoto University RISH) radiosonde upper-air data.

Handles netCDF data only. ``sgk`` is excluded because it is distributed as CSV
rather than netCDF.

Data retrieval and parsing
--------------------------
The shared ``load.py`` is for ``cdf_to_tplot`` only and cannot be used for
netCDF. This function fetches ``.nc`` files via ``dailynames`` -> ``download``,
parses them with ``netCDF4``, and creates tplot variables with ``store_data``.
The height profiles (time x height) are re-gridded onto the same height grids as
the original output (DAWEX by index assignment, misc by +/-dh/2 averaging).

Two data families
------------------
- **DAWEX** (drw/gpn/ktr):
  netCDF variables ``time press temperature relative_humidity dew_point uwind
  vwind``. ``time`` is minutes since the epoch (the date in the units is
  ignored; unix seconds = raw value x 60). The height grid is 0..39.9 km in
  400 points at 0.1 km steps; ``h_num = height_m // 100`` is used for index
  assignment. Fill values -999.0 or 0.0 -> NaN. ``dewp`` is present.
- **misc** (bdg/ktb/pon/srp/uji): the 4 sites bdg/ktb/pon/srp are identical;
  only uji has a different PI name.
  netCDF variables ``Launching_time press temperature relative_humidity uwind
  vwind``. The time base ``stime`` is parsed from the ``Launching_time`` units
  string; unix = stime + Launching_time (seconds). The height grid is
  0..40000 m in 1333 points at 30 m steps, re-gridded by +/-15 m averaging,
  with ``v`` stored in km. Fill value -999.00. ``dewp`` is absent.
"""
import numpy as np

from pyspedas import dailynames, download, get_data, store_data, options, time_double

from iugonet.config import CONFIG
from iugonet.tools.tdegap import tdegap

# ---- Site definitions ----------------------------------------------------
# The full site set is 'bdg drw gpn ktb ktr pon sgk srp uji'; sgk is CSV and
# excluded here.
DAWEX_SITES = ["drw", "gpn", "ktr"]
MISC_SITES = ["bdg", "ktb", "pon", "srp", "uji"]
SITE_LIST = ["bdg", "drw", "gpn", "ktb", "ktr", "pon", "srp", "uji"]

REMOTE_BASE = "http://database.rish.kyoto-u.ac.jp/arch/iugonet/"

# DAWEX: site -> (remote-directory code, file-name leading code).
_DAWEX_INFO = {
    "drw": ("Dr", "nD"),
    "gpn": ("Gp", "nG"),
    "ktr": ("Kh", "nK"),
}

# misc: site -> (URL city segment, PI name).
_MISC_INFO = {
    "bdg": ("bandung", "H. Hashiguchi"),
    "ktb": ("kototabang", "H. Hashiguchi"),
    "pon": ("pontianak", "H. Hashiguchi"),
    "srp": ("serpong", "H. Hashiguchi"),
    "uji": ("uji", "T. Tsuda"),
}

# misc common: height grid. max_height=40000, dh=30.
_MISC_DH = 30.0
_MISC_NUM_H = int(40000 / _MISC_DH)  # = 1333

# Per-parameter ztitle.
_ZTITLE = {
    "press": "Press.!C[hPa]",
    "temp": "Temp.!C[deg.]",
    "rh": "RH!C[%]",
    "dewp": "Dewp.!C[deg.]",
    "uwnd": "uwnd!C[m/s]",
    "vwnd": "vwnd!C[m/s]",
}

_ACK = (
    "If you acquire the radiosonde data, we ask that you acknowledge "
    "us in your use of the data. This may be done by including text such as "
    "the radiosonde data provided by Research Institute for Sustainable "
    "Humanosphere of Kyoto University. We would also appreciate receiving a "
    "copy of the relevant publications. The distribution of radiosonde data "
    "has been partly supported by the IUGONET (Inter-university Upper "
    "atmosphere Global Observation NETwork) project (http://www.iugonet.org/) "
    "funded by the Ministry of Education, Culture, Sports, Science and "
    "Technology (MEXT), Japan."
)


def _normalize(value, valid, all_list):
    """Normalize a str/list input ('all' accepted) to a list of valid values (order preserved, deduped)."""
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(s).lower() for s in value]
    if "all" in items:
        return list(all_list)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _time_units_scale(units):
    """Return the seconds-per-unit factor from the leading word of a time-units string."""
    head = units.strip().split()[0].lower()
    if head.startswith("second"):
        return 1.0
    if head.startswith("minute"):
        return 60.0
    if head.startswith("hour"):
        return 3600.0
    return 1.0


def _print_ack():
    """Print the acknowledgement (Rules of the Road)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(_ACK)
    print("****************************************************************")


# ===========================================================================
#  DAWEX (drw / gpn / ktr)
# ===========================================================================
def _load_dawex(site, trange, no_update, downloadonly):
    """Load DAWEX radiosonde netCDF data."""
    url_code, name_code = _DAWEX_INFO[site]
    remote_path = REMOTE_BASE + "DAWEX/data/" + url_code + "/nc/"
    local_path = CONFIG["local_data_dir"] + "/rish/DAWEX/" + site + "/radiosonde/nc/"
    # File name at hourly resolution. Example: 2001/nD101311.nc
    # (month 10, day 13, hour 11).
    pathformat = "%Y/" + name_code + "%m%d%H.nc"

    remote_names = dailynames(file_format=pathformat, trange=trange, res=3600.0)
    files = download(
        remote_file=remote_names,
        remote_path=remote_path,
        local_path=local_path,
        no_download=no_update,
        last_version=True,
        verify=False,
    )
    files = sorted(f for f in (files or []) if _is_file(f))
    if downloadonly or not files:
        return files if downloadonly else []

    # Height grid: 400 points at 0.1 km steps. grid[i] = i*0.1 km.
    n_h = 400
    height_grid = np.arange(n_h, dtype=np.float32) * np.float32(0.1)

    params = ["press", "temp", "rh", "dewp", "uwnd", "vwnd"]
    # netCDF variable name -> internal parameter name.
    var_map = {
        "press": "press",
        "temperature": "temp",
        "relative_humidity": "rh",
        "dew_point": "dewp",
        "uwind": "uwnd",
        "vwind": "vwnd",
    }
    times = []
    cols = {p: [] for p in params}

    import netCDF4

    for fn in files:
        try:
            ds = netCDF4.Dataset(fn, "r")
        except OSError:
            continue
        try:
            tvar = ds.variables["time"]
            scale = _time_units_scale(tvar.units)
            # The date in the units is ignored; sonde_time = raw_value * dt.
            traw = float(np.array(tvar[:]).ravel()[0])
            unix_t = traw * scale

            ht = np.array(ds.variables["height"][:]).ravel()
            # Grid index by integer division: h_num = height_m // 100.
            h_num = (ht // 100).astype(int)

            # Assign each parameter onto the 400-point grid (initial value 0.0).
            row = {p: np.zeros(n_h, dtype=np.float32) for p in params}
            for ncname, p in var_map.items():
                if ncname not in ds.variables:
                    continue
                vals = np.array(ds.variables[ncname][:]).ravel()
                valid = (h_num >= 0) & (h_num < n_h)
                row[p][h_num[valid]] = vals[valid].astype(np.float32)
            # Fill values -999.0 or 0.0 -> NaN (over the whole grid).
            for p in params:
                a = row[p]
                a[(a == -999.0) | (a == 0.0)] = np.nan
        finally:
            ds.close()

        times.append(unix_t)
        for p in params:
            cols[p].append(row[p])

    if not times:
        return []

    x = np.array(times, dtype=np.float64)
    created = []
    for p in params:
        y = np.array(cols[p], dtype=np.float32)  # shape (ntime, 400)
        name = "iug_radiosonde_" + site + "_" + p
        store_data(
            name,
            data={"x": x, "y": y, "v": height_grid},
            attr_dict={"data_att": {"acknowledgment": _ACK, "PI_NAME": "T. Tsuda"}},
        )
        options(name, "spec", 1)
        options(name, "ytitle", "RSND-" + site + "!CHeight!C[km]")
        options(name, "ztitle", _ZTITLE[p])
        created.append(name)
    # Apply tdegap (overwrite) to each variable to insert NaN rows at gaps, to
    # match the original output.
    for nm in created:
        tdegap(nm, overwrite=True)
    return created


# ===========================================================================
#  misc (bdg / ktb / pon / srp / uji)
# ===========================================================================
def _load_misc(site, trange, no_update, downloadonly):
    """Load misc radiosonde netCDF data."""
    city, pi_name = _MISC_INFO[site]
    remote_path = REMOTE_BASE + "sonde/data/" + city + "/nc/"
    local_path = CONFIG["local_data_dir"] + "/rish/misc/" + site + "/radiosonde/nc/"
    # File name at hourly resolution. Example: 2013/201303130000.nc.
    # The '*' is resolved by last_version.
    pathformat = "%Y/%Y%m%d%H*.nc"

    remote_names = dailynames(file_format=pathformat, trange=trange, res=3600.0)
    files = download(
        remote_file=remote_names,
        remote_path=remote_path,
        local_path=local_path,
        no_download=no_update,
        last_version=True,
        verify=False,
    )
    files = sorted(f for f in (files or []) if _is_file(f))
    if downloadonly or not files:
        return files if downloadonly else []

    # Height grid: 1333 points at 30 m steps, 0..40000 m.
    ht_grid = np.arange(_MISC_NUM_H, dtype=np.float32) * np.float32(_MISC_DH)
    v_km = ht_grid / 1000.0

    params = ["press", "temp", "rh", "uwnd", "vwnd"]
    var_map = {
        "press": "press",
        "temperature": "temp",
        "relative_humidity": "rh",
        "uwind": "uwnd",
        "vwind": "vwnd",
    }
    times = []
    cols = {p: [] for p in params}

    import netCDF4

    for fn in files:
        try:
            ds = netCDF4.Dataset(fn, "r")
        except OSError:
            continue
        try:
            lt = ds.variables["Launching_time"]
            # Parse stime from the units: split on whitespace, take the date
            # (info[2]) and time (info[3]).
            info = lt.units.strip().split()
            stime = time_double(info[2] + "/" + info[3])
            launch = np.array(lt[:]).ravel().astype(np.float64)  # seconds (usually [0])

            height = np.array(ds.variables["height"][:]).ravel().astype(np.float64)

            # Read raw data and map fill value -999.00 -> NaN.
            raw = {}
            for ncname, p in var_map.items():
                arr = np.array(ds.variables[ncname][:]).astype(np.float64).ravel()
                arr[arr == -999.00] = np.nan
                raw[p] = arr

            # Re-grid onto the 30 m grid by +/-dh/2 averaging. With ht[i]=i*dh,
            # selecting ht[i]-dh/2 <= height < ht[i]+dh/2 is equivalent to
            # bin = floor((height + dh/2) / dh).
            binned = {p: np.full(_MISC_NUM_H, np.nan, dtype=np.float32) for p in params}
            bin_idx = np.floor((height + _MISC_DH / 2.0) / _MISC_DH).astype(int)
            in_range = (bin_idx >= 0) & (bin_idx < _MISC_NUM_H)
            uniq = np.unique(bin_idx[in_range])
            for b in uniq:
                sel = in_range & (bin_idx == b)
                for p in params:
                    vals = raw[p][sel]
                    if np.any(~np.isnan(vals)):
                        binned[p][b] = np.float32(np.nanmean(vals))
        finally:
            ds.close()

        # sonde_time = stime + Launching_time (usually length 1).
        for tv in launch:
            times.append(stime + tv)
        for p in params:
            cols[p].append(binned[p])

    if not times:
        return []

    x = np.array(times, dtype=np.float64)
    # zlim settings: uwnd -40..40, vwnd -20..20.
    zlim_map = {"uwnd": (-40, 40), "vwnd": (-20, 20)}
    created = []
    for p in params:
        y = np.array(cols[p], dtype=np.float32)  # shape (ntime, 1333)
        name = "iug_radiosonde_" + site + "_" + p
        store_data(
            name,
            data={"x": x, "y": y, "v": v_km},
            attr_dict={"data_att": {"acknowledgment": _ACK, "PI_NAME": pi_name}},
        )
        options(name, "spec", 1)
        options(name, "ytitle", "RSND-" + site + "!CHeight!C[km]")
        options(name, "ztitle", _ZTITLE[p])
        if p in zlim_map:
            options(name, "zrange", list(zlim_map[p]))
        created.append(name)
    # Apply tdegap (overwrite) to each variable, to match the original output.
    for nm in created:
        tdegap(nm, overwrite=True)
    return created


def _is_file(path):
    import os

    return os.path.isfile(path)


def radiosonde_rish(
    trange=["2001-10-13", "2001-10-18"],
    site="all",
    datatype="all",
    no_update=False,
    downloadonly=False,
    ror=True,
):
    """Load RISH radiosonde upper-air netCDF data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2001-10-13', '2001-10-18']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. Valid sites (netCDF
        only; CSV-only sgk is excluded): bdg drw gpn ktb ktr pon srp uji.
        Default: 'all'
    datatype : str
        Type of data to load; logically ANDed with site. Valid options: dawex,
        misc, all.
        Default: 'all'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    ror : bool
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True

    Returns
    -------
    list of str
        List of tplot variables created
        (``iug_radiosonde_{site}_{press|temp|rh|dewp|uwnd|vwnd}``). Empty list
        if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned instead.

    Notes
    -----
    DAWEX (drw/gpn/ktr) creates the 6 parameters press/temp/rh/dewp/uwnd/vwnd;
    misc (bdg/ktb/pon/srp/uji) creates the 5 parameters excluding dewp. The
    height profiles are re-gridded onto the same height grid as the original
    output.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.radiosonde_rish(trange=['2001-10-13', '2001-10-18'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_LIST, SITE_LIST)
    dtypes = _normalize(datatype, ["dawex", "misc"], ["dawex", "misc"])
    if not sites or not dtypes:
        return []

    loaded = []
    for st in sites:
        # Dispatch by datatype.
        if st in DAWEX_SITES and "dawex" in dtypes:
            loaded += _load_dawex(st, trange, no_update, downloadonly)
        elif st in MISC_SITES and "misc" in dtypes:
            loaded += _load_misc(st, trange, no_update, downloadonly)

    if ror and not downloadonly and loaded:
        _print_ack()

    return loaded
