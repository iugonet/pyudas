"""Load function for MF (medium-frequency) radar wind data (RISH).

This function dispatches to one of two readers per site:

- ``pam`` (Pameungpeuk, Indonesia)
- ``pon`` (Pontianak, Indonesia)

The netCDF (.nc) files are downloaded from the RISH server and parsed in-house
with netCDF4 (``cdf_to_tplot`` cannot be used). The MF radar observes the
three-component wind (zonal/meridional/vertical) of the mesosphere/thermosphere
as height profiles (time x height).

Data format (confirmed from the actual .nc files):

pam (Pameungpeuk): file ``YYYY/YYYYMMDD_pam.nc``.
  dims: time(unlimited), range(36), station(1).
  - range: units 'm' -> divided by 1000 to convert to km.
  - time : float64, units 'seconds since 1970-01-01 00:00:00'. Already unix
           seconds, so used as-is (no time conversion).
  - uwind/vwind/wwind: dims (time, range, station), shape (Nt, 36, 1).
           Extract (Nt, 36) with [:, :, 0].
  Missing value -9999 -> NaN. Post-processing: clip uwnd/vwnd ±100, wwnd ±20,
  data_gap 1800s.
  Created variables: iug_mf_pam_{uwnd,vwnd,wwnd}

pon (Pontianak): file ``YYYY/YYYYMMDD_fca.nc``.
  dims: time(e.g. 327), height(e.g. 21). The number of heights varies per file.
  - height: units 'km'. Used as-is.
  - time  : float32, units 'seconds since YYYY-MM-DD HH:MM:SS +TZ'.
           The base date/time and the time-zone offset are read from the units
           string, and unix = time + time_double(date+'/'+time) - tz_sec.
  - uwind/vwind/wwind: dims (height, time), shape (Nh, Nt). .T gives (Nt, Nh).
  Missing value -9999 -> NaN. Post-processing: data_gap 240s, clip ±200,
  zlim ±100.
  Created variables: iug_mf_pon_{uwnd,vwnd,wwnd}
"""
import os

import numpy as np

from pyspedas import store_data, options, clip, zlim, time_double, dailynames, download

from netCDF4 import Dataset

from iugonet.config import CONFIG

# All observation sites (default 'all').
SITE_CODE_ALL = ["pam", "pon"]

# Per-site server settings.
#   remote_path : directory on the RISH server
#   pathformat  : daily file-name format passed to dailynames (year/yyyymmdd_suffix)
#   local_sub   : local storage subdirectory
SITE_INFO = {
    "pam": {
        "remote_path": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mf/pameungpeuk/nc/ver1_0_1/",
        "pathformat": "%Y/%Y%m%d_pam.nc",
        "local_sub": os.path.join("rish", "misc", "pam", "mf", "nc"),
    },
    "pon": {
        "remote_path": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mf/pontianak/nc/",
        "pathformat": "%Y/%Y%m%d_fca.nc",
        "local_sub": os.path.join("rish", "misc", "pon", "mf", "nc"),
    },
}

# Missing value (-9999 -> NaN).
MISSING_VALUE = -9999.0

# Marker used to detect a "not found" HTML error page returned instead of a .nc.
_HTML_MARKERS = (b"<!doctype", b"<html")


def _normalize_sites(site):
    """Normalize a site input (str/list, 'all' accepted) to valid site codes.

    Preserves input order and removes duplicates and invalid codes.
    """
    if isinstance(site, str):
        items = site.lower().split()
    else:
        items = [str(s).lower() for s in site]
    if "all" in items:
        return list(SITE_CODE_ALL)
    out = []
    for it in items:
        if it in SITE_CODE_ALL and it not in out:
            out.append(it)
    return out


def _is_real_nc(path):
    """Return True if the downloaded file is real NetCDF (not an HTML error page).

    NetCDF classic/64-bit begins with 'CDF', NetCDF-4 (HDF5) with '\\x89HDF'.
    The leading magic bytes are checked to exclude HTML error pages.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
    except OSError:
        return False
    if head[:3] == b"CDF":          # NetCDF classic / 64-bit offset
        return True
    if head[:4] == b"\x89HDF":      # NetCDF-4 / HDF5
        return True
    if head[:4] == b"\x0eSPD":      # rare alternative magic (safety)
        return True
    # Otherwise treat it as HTML etc.
    lower = head.lstrip().lower()
    return not lower.startswith(_HTML_MARKERS)


def _download_nc(site, trange):
    """Download the daily .nc files for a site/trange and return local paths.

    HTML error pages are excluded.
    """
    info = SITE_INFO[site]
    remote_names = dailynames(file_format=info["pathformat"], trange=trange, res=24 * 3600.0)
    # download reproduces the remote_file relative path (YYYY/YYYYMMDD_*.nc)
    # under local_path, storing into
    # local_data_dir/rish/misc/<site>/mf/nc/YYYY/YYYYMMDD_*.nc.
    local_data_dir = os.path.join(CONFIG["local_data_dir"], info["local_sub"])
    files = download(
        remote_file=remote_names,
        remote_path=info["remote_path"],
        local_path=local_data_dir,
        last_version=True,
    )
    out = []
    for f in files or []:
        if os.path.isfile(f) and _is_real_nc(f):
            out.append(f)
    return sorted(set(out))


def _replace_missing(arr):
    """Return a float64 array with -9999 elements replaced by NaN.

    Equivalent to the netCDF4 auto-mask, but the replacement is done explicitly
    to match the original output.
    """
    a = np.array(arr, dtype=np.float64)
    a[a == MISSING_VALUE] = np.nan
    return a


def _parse_pam(path):
    """Read a pam .nc and return {x: unix[Nt], height[36], u/v/w: [Nt,36]}.

      time is 'seconds since 1970-01-01', so it is unix seconds as-is.
      range[m] -> height[km] is /1000. wind is (time, range, station) -> [:, :, 0].
    Returns None on read failure or missing required variables.
    """
    try:
        ds = Dataset(path, "r")
    except OSError:
        return None
    try:
        ds.set_auto_mask(False)  # read raw values; replace missing explicitly
        for need in ("time", "range", "uwind", "vwind", "wwind"):
            if need not in ds.variables:
                return None

        time = np.array(ds.variables["time"][:], dtype=np.float64)  # already unix seconds
        height = np.array(ds.variables["range"][:], dtype=np.float64) / 1000.0  # m -> km

        # (time, range, station) -> (time, range): take index 0 of the station axis.
        u = ds.variables["uwind"][:]
        v = ds.variables["vwind"][:]
        w = ds.variables["wwind"][:]
        if u.ndim == 3:
            u = u[:, :, 0]
            v = v[:, :, 0]
            w = w[:, :, 0]

        return {
            "x": time,
            "height": height,
            "u": _replace_missing(u),
            "v": _replace_missing(v),
            "w": _replace_missing(w),
        }
    finally:
        ds.close()


def _parse_pon(path):
    """Read a pon .nc and return {x: unix[Nt], height[Nh], u/v/w: [Nt,Nh]}.

      time: the base date/time and the time-zone offset are read from the units
      string 'seconds since YYYY-MM-DD HH:MM:SS +TZ', and
      unix = time + time_double(date+'/'+time) - tz_sec.
      height is in km. wind is (height, time) -> .T gives (time, height).
    Returns None on read failure or missing required variables.
    """
    try:
        ds = Dataset(path, "r")
    except OSError:
        return None
    try:
        ds.set_auto_mask(False)
        for need in ("time", "height", "uwind", "vwind", "wwind"):
            if need not in ds.variables:
                return None

        tvar = ds.variables["time"]
        raw_time = np.array(tvar[:], dtype=np.float64)

        # Parse 'seconds since YYYY-MM-DD HH:MM:SS +TZ': fields [2]/[3] give the
        # base date/time, field [4] gives the time-zone offset.
        units = getattr(tvar, "units", "")
        ti = units.split()
        if len(ti) >= 4:
            syymmdd = ti[2]
            shhmmss = ti[3]
            tz_sec = 0
            if len(ti) >= 5:
                td = ti[4].split(":")
                # '+00' -> 0, '+07' -> 7, '-05' -> -5 (signed integer).
                hh = int(td[0]) if td[0] not in ("", "+", "-") else 0
                mm = int(td[1]) if len(td) > 1 and td[1] != "" else 0
                # Propagate the hour sign to the minutes for consistency.
                tz_sec = hh * 3600 + (mm * 60 if hh >= 0 else -mm * 60)
            base = time_double(syymmdd + "/" + shhmmss)
            unix_time = raw_time + base - tz_sec
        else:
            # If the units are unexpected, treat raw as unix directly (safety).
            unix_time = raw_time

        height = np.array(ds.variables["height"][:], dtype=np.float64)  # already km

        # (height, time) -> (time, height)
        u = np.array(ds.variables["uwind"][:], dtype=np.float64).T
        v = np.array(ds.variables["vwind"][:], dtype=np.float64).T
        w = np.array(ds.variables["wwind"][:], dtype=np.float64).T

        return {
            "x": unix_time,
            "height": height,
            "u": _replace_missing(u),
            "v": _replace_missing(v),
            "w": _replace_missing(w),
        }
    finally:
        ds.close()


def _concat_days(parsed_list):
    """Concatenate the daily parse results along time into a single dict.

    The height of the last file read is used (only the data are concatenated;
    height is overwritten). Days whose height length differs are skipped (only
    consistent days are concatenated).
    """
    parsed = [p for p in parsed_list if p is not None]
    if not parsed:
        return None
    height = parsed[-1]["height"]
    nh = len(height)
    xs, us, vs, ws = [], [], [], []
    for p in parsed:
        if p["u"].shape[1] != nh:
            # Skip days with a different number of height bins.
            continue
        xs.append(p["x"])
        us.append(p["u"])
        vs.append(p["v"])
        ws.append(p["w"])
    if not xs:
        return None
    return {
        "x": np.concatenate(xs),
        "height": height,
        "u": np.concatenate(us, axis=0),
        "v": np.concatenate(vs, axis=0),
        "w": np.concatenate(ws, axis=0),
    }


def mf_rish(
    trange=["2010-02-12", "2010-02-13"],
    site="all",
    downloadonly=False,
    suffix="",
    ror=True,
):
    """Load MF radar three-component wind data from RISH.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day.
        Default: ['2010-02-12', '2010-02-13']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. Valid sites:
        pam (Pameungpeuk) pon (Pontianak), both in Indonesia.
        Default: 'all'
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)
    ror : bool
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True

    Returns
    -------
    list of str
        List of tplot variables created (``iug_mf_{site}_{uwnd,vwnd,wwnd}``).
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned instead.

    Notes
    -----
    Created variables are 2-D time-height spectrogram (spec) variables.
    pam: height 52-122 km (36 bins), missing value -9999; clip uwnd/vwnd ±100,
    wwnd ±20. pon: height 60-100 km (21 bins), missing value -9999; clip ±200,
    zlim ±100.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.mf_rish(trange=['2010-02-12', '2010-02-13'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        print("This station code is not valid. Please input the allowed keywords, "
              "all, pam, and pon.")
        return []

    loaded = []
    dl_files = []

    for st in sites:
        print(st)
        files = _download_nc(st, trange)
        if not files:
            print(f"No MF-{st} data found in {trange}.")
            continue
        if downloadonly:
            dl_files += files
            continue

        # Parse the daily files and concatenate.
        parser = _parse_pam if st == "pam" else _parse_pon
        parsed = [parser(f) for f in files]
        data = _concat_days(parsed)
        if data is None:
            print(f"No valid MF-{st} data parsed in {trange}.")
            continue

        # ----- create tplot variables and post-process -----
        comps = [
            ("uwnd", data["u"], "uwnd"),
            ("vwnd", data["v"], "vwnd"),
            ("wwnd", data["w"], "wwnd"),
        ]
        site_vars = []
        for cname, yval, ztxt in comps:
            name = f"iug_mf_{st}_{cname}{suffix}"
            store_data(name, data={"x": data["x"], "y": yval, "v": data["height"]})
            options(name, "spec", 1)
            # The !C line break becomes \n in Python for ytitle / ztitle.
            options(name, "ytitle", f"MF-{st}\nheight\n[km]")
            options(name, "ztitle", f"{ztxt}\n[m/s]")
            site_vars.append((cname, name))

        # ----- clip / data_gap / zlim -----
        if st == "pam":
            for cname, name in site_vars:
                if cname == "wwnd":
                    clip(name, -20, 20)        # clip wwnd to ±20
                else:
                    clip(name, -100, 100)      # clip uwnd/vwnd to ±100
                options(name, "data_gap", 1800)  # gap threshold dt=1800
        else:  # pon
            for cname, name in site_vars:
                options(name, "data_gap", 240)   # gap threshold dt=240
                clip(name, -200, 200)            # clip to ±200
                zlim(name, -100, 100)            # z-axis limits ±100

        loaded += [name for _, name in site_vars]

        if ror:
            _print_ror()

    if downloadonly:
        return sorted(set(dl_files))

    if loaded:
        print("*****************************")
        print("Data loading is successful!!")
        print("*****************************")
    return loaded


def _print_ror():
    """Print the Rules of the Road (data use policy)."""
    print("**************************************************************************")
    print("Acknowledgement")
    print("**************************************************************************")
    print("Note: If you would like to use following data for scientific purpose, "
          "please read and follow the DATA USE POLICY")
    print("(http://database.rish.kyoto-u.ac.jp/arch/iugonet/data_policy/Data_Use_Policy_e.html")
    print("The distribution of MF radar data has been partly supported by the IUGONET")
    print("(Inter-university Upper atmosphere Global Observation NETwork) project")
    print("(http://www.iugonet.org/) funded by the Ministry of Education, Culture, "
          "Sports, Science and Technology (MEXT), Japan.")
    print("**************************************************************************")
