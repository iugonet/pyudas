"""Load function for RISH Meteor Wind Radar (MWR) wind-velocity data.

A single function covers four observatories that share almost identical data
specifications and processing; they differ only in (1) the remote server URL and
version directory, (2) the file-name prefix (Wb/Wk/Ws/jkt), (3) the LT->UT time
shift (file-fetch window and edge clipping), and (4) the station code embedded in
the tplot variable names and ytitle:

- ``bik`` (Biak)
- ``ktb`` (Kototabang)
- ``sgk`` (Shigaraki)
- ``srp`` (Serpong)

netCDF file structure:
  dimensions:  time (unlimited), range (21 or 22), station (1)
  variables:
    lon, lat       (station,)       longitude/latitude [deg]
    range          (range,)         height [m]  (70000..110000/112000)
    time           (time,)  int32   units='hours since YYYY-MM-DD HH:MM:SS +TZ:00'
    uwind, vwind, sig_uwind, sig_vwind, num
                   (time, range, station)  _FillValue=-9999
  Time conversion (common to all four stations):
    unix_time[i] = time[i]*3600 + time_double(base_yymmdd/base_hhmmss) - tz_offset
  where base and tz_offset are taken from the time.units string. The reference
  time zone of units differs by station (sgk=+09:00, srp=+07:00, bik/ktb=+00:00).
  time_double interprets the reference string as UTC, so subtracting tz_offset
  corrects the file reference time (which may be in local time) to true UT. This
  matches the UT returned by netCDF4.num2date(units=...) exactly.

  The fill value -9999 is replaced with NaN. Height is converted m->km
  (range/1000).

These are not CDF files, so the shared load() (cdf_to_tplot) cannot be used. The
.nc files are fetched with pyspedas ``download`` and parsed directly with netCDF4
before calling ``store_data``.

Variables produced (five per station and parameter):
  iug_meteor_{site}_uwnd_{parameter}     zonal wind [m/s]
  iug_meteor_{site}_vwnd_{parameter}     meridional wind [m/s]
  iug_meteor_{site}_uwndsig_{parameter}  standard deviation of zonal wind [m/s]
  iug_meteor_{site}_vwndsig_{parameter}  standard deviation of meridional wind [m/s]
  iug_meteor_{site}_mwnum_{parameter}    meteor echo count
  All are 2-D (x=time[UT], y=[time,height], v=height[km]) with spec=1.

Data distribution (daily and monthly files coexist in the same directory
regardless of length):
  bik: http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/biak/      nc/ver1_0
  ktb: http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/kototabang/ nc/ver1_1_2
  sgk: http://database.rish.kyoto-u.ac.jp/arch/mudb/data/mwr/              nc/ver1_0
  srp: http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/serpong/   nc/ver1_0_2
"""
import os

import numpy as np

from pyspedas import (store_data, options, time_double, time_string,
                      dailynames, download)
from pyspedas.tplot_tools import degap, clip

from iugonet.config import CONFIG

PARAMETER_ALL = ["h2t60min00", "h2t60min30", "h4t60min00",
                 "h4t60min30", "h4t240min00"]

SITE_CODE_ALL = ["bik", "ktb", "sgk", "srp"]

# '1_day' uses YYYYMMDD files, '1_month' uses YYYYMM files.
LENGTH_ALL = ["1_day", "1_month"]

# Per-station settings.
#   base    : base URL of the remote data directory
#   ver     : version directory (nc/<ver>/...)
#   prefix  : file-name prefix (Wb/Wk/Ws/jkt)
#   lt_shift: LT->UT shift in seconds. The file-fetch window is moved earlier and
#             edge-clipped to the original UT range at the end (sgk=-9h, srp=-7h,
#             bik/ktb=0).
#   label   : observatory label for the ytitle (only srp uses 'MWR-srp')
SITE_INFO = {
    "bik": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/biak/",
        "ver": "ver1_0",
        "prefix": "Wb",
        "lt_shift": 0.0,
        "label": "MW-bik",
    },
    "ktb": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/kototabang/",
        "ver": "ver1_1_2",
        "prefix": "Wk",
        "lt_shift": 0.0,
        "label": "MW-ktb",
    },
    "sgk": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/mudb/data/mwr/",
        "ver": "ver1_0",
        "prefix": "Ws",
        "lt_shift": 9.0 * 3600.0,
        "label": "MW-sgk",
    },
    "srp": {
        "base": "http://database.rish.kyoto-u.ac.jp/arch/iugonet/data/mwr/serpong/",
        "ver": "ver1_0_2",
        "prefix": "jkt",
        "lt_shift": 7.0 * 3600.0,
        "label": "MWR-srp",
    },
}

# netCDF variable name -> (tplot variable-name key, ztitle), in the order
# uwnd/vwnd/uwndsig/vwndsig/mwnum.
VAR_MAP = [
    ("uwind",     "uwnd",     "uwnd!C[m/s]"),
    ("vwind",     "vwnd",     "vwnd!C[m/s]"),
    ("sig_uwind", "uwndsig",  "uwndsig!C[m/s]"),
    ("sig_vwind", "vwndsig",  "vwndsig!C[m/s]"),
    ("num",       "mwnum",    "mwnum"),
]

# Clip range applied to each variable. tplot key -> (min, max).
TCLIP_RANGE = {
    "uwnd":    (-200.0, 200.0),
    "vwnd":    (-200.0, 200.0),
    "uwndsig": (0.0, 800.0),
    "vwndsig": (0.0, 800.0),
    "mwnum":   (0.0, 1200.0),
}


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


def _param_dir(parameter):
    """Convert a parameter name to its remote directory name.

    e.g. 'h2t60min00' -> 'h2km_t60min00', 'h4t240min00' -> 'h4km_t240min00'.
    """
    return parameter[0:2] + "km_" + parameter[2:]


def _parse_time_units(units):
    """Parse time.units 'hours since YYYY-MM-DD HH:MM:SS +TZ:TZ' into (base_unix, tz_sec).

    base_unix is time_double(syymmdd/shhmmss) interpreted as UTC; tz_sec is the
    time-zone offset in seconds, honoring its sign (+ -> positive, - -> negative).
    """
    parts = units.split()
    # parts = ['hours','since','YYYY-MM-DD','HH:MM:SS','+TZ:TZ']
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
    """Read one netCDF file and return time/height and each data array.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds UT, 'height': (Nr,) km,
       'uwind','vwind','sig_uwind','sig_vwind','num': (Nt, Nr)}
      The fill value (-9999) becomes NaN. None if the file is unreadable or empty.
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
        # unix_time[i] = time[i]*3600 + base - tz_offset
        unix_time = tvals * 3600.0 + base_unix - tz_sec

        # height m -> km
        height = np.asarray(ds.variables["range"][:], dtype=np.float64) / 1000.0

        out = {"time": unix_time, "height": height}
        for ncname in ("uwind", "vwind", "sig_uwind", "sig_vwind", "num"):
            raw = ds.variables[ncname][:]            # (time, range, station)
            arr = np.ma.filled(np.ma.asarray(raw), fill_value=-9999.0)
            arr = np.asarray(arr, dtype=np.float64)
            # drop the trailing station axis: (time, range, station) -> (time, range)
            if arr.ndim == 3:
                arr2 = arr[:, :, 0]
            else:
                arr2 = arr
            # fill value -9999 -> NaN
            arr2 = np.where(arr2 == -9999.0, np.nan, arr2)
            out[ncname] = arr2
        return out
    finally:
        ds.close()


def _degap_dt(parameter):
    """Return the degap dt in seconds: 14400 for h4t240min00 (240-min cadence), 3600 otherwise."""
    return 14400.0 if parameter == "h4t240min00" else 3600.0


def meteor_rish(
    trange=["2008-03-01", "2008-03-31"],
    site="ktb",
    parameter="h2t60min00",
    length="1_month",
    datatype="",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load RISH Meteor Wind Radar (MWR) wind-velocity data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2008-03-01', '2008-03-31']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('bik ktb') or a
        list are both accepted. 'all' selects every available site. Valid sites:
        bik ktb sgk srp (bik=Biak, ktb=Kototabang, sgk=Shigaraki, srp=Serpong).
        Default: 'ktb'
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter. Valid
        options: h2t60min00 h2t60min30 h4t60min00 h4t60min30 h4t240min00. The
        h2/h4 prefix is the Gaussian half-width in height (+-2 km / +-4 km), and
        min00/min30 is the on-the-hour position of the Gaussian window center
        (00 / 30 minutes).
        Default: 'h2t60min00'
    length : str
        File aggregation length. Valid options: '1_month' (YYYYMM monthly files)
        and '1_day' (YYYYMMDD daily files); both coexist in the same server
        directory.
        Default: '1_month'
    datatype : str
        Unused; accepted for compatibility.
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
        Time clip the variables to exactly the range specified in trange. For
        bik/ktb only; sgk/srp are always clipped as part of their LT->UT
        processing.
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
        (``iug_meteor_{site}_{uwnd,vwnd,uwndsig,vwndsig,mwnum}_{parameter}``).
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Notes
    -----
    A full day is always read even if trange spans less than a day. For sgk/srp,
    files are fetched over a window shifted earlier by the station local-time
    offset and then edge-clipped to the original UT trange.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.meteor_rish(trange=['2008-03-01', '2008-03-31'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    if not sites:
        print("This station code is not valid. Please input the allowed "
              "keywords, all, bik, ktb, sgk, and srp.")
        return {} if notplot else []

    params = _normalize(parameter, PARAMETER_ALL)
    if not params:
        print("This parameter is not valid. Please input the allowed keywords, "
              "all, h2t60min00, h2t60min30, h4t60min00, h4t60min30, h4t240min00.")
        return {} if notplot else []

    if length not in LENGTH_ALL:
        print("LENGTH must be '1_day' or '1_month'.")
        return {} if notplot else []

    # Switch the date format of the file names between monthly and daily files
    # (monthly: YYYYMM, daily: YYYYMMDD); names are later deduplicated.
    monthly = (length == "1_month")
    date_fmt = "%Y%m" if monthly else "%Y%m%d"

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0   # read one extra full day

    loaded = {} if notplot else []
    dl_files = []

    for st in sites:
        info = SITE_INFO[st]

        # ===== shift the file-fetch window earlier by the LT->UT offset =====
        # bik/ktb use lt_shift=0; win is [t0-shift, t0-shift + day_mod*86400].
        win_start = t0 - info["lt_shift"]
        win_trange = [time_string(win_start),
                      time_string(win_start + day_mod * 86400.0)]

        for pr in params:
            pdir = _param_dir(pr)   # e.g. 'h2km_t60min00'
            # remote_file relative path: nc/<ver>/<pdir>/%Y/<prefix>DATE.<pr>.nc
            file_format = (
                "nc/" + info["ver"] + "/" + pdir + "/%Y/"
                + info["prefix"] + date_fmt + "." + pr + ".nc"
            )
            remote_names = sorted(set(
                dailynames(file_format=file_format, trange=win_trange,
                           res=24 * 3600.0)
            ))

            # local destination: CONFIG/local_data_dir/rish/misc/<site>/meteor/...
            # the remote relative path (nc/<ver>/...) is recreated under local.
            local_dir = os.path.join(
                CONFIG["local_data_dir"], "rish", "misc", st, "meteor"
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
                print(f"No MWR-{st} {pr} data found in {trange}.")
                continue

            # ===== read every file and concatenate along time =====
            t_list = []
            data_lists = {nc: [] for nc, _, _ in VAR_MAP}
            height = None
            for path in out_files:
                d = _read_nc(path)
                if d is None:
                    continue
                # The range size can be 21 or 22 depending on station/period,
                # but is constant within consecutive files of the same
                # (site, parameter); align everything to the largest range here.
                if height is None or d["height"].size > height.size:
                    height = d["height"]
                t_list.append(d["time"])
                for nc, _, _ in VAR_MAP:
                    data_lists[nc].append(d[nc])

            if not t_list:
                print(f"No valid MWR-{st} {pr} data parsed in {trange}.")
                continue

            nr = height.size
            site_time = np.concatenate(t_list)

            def _stack(arrs):
                """Vertically stack per-file (Nt_i, Nr_i) arrays, right-padding range to nr with NaN."""
                out = []
                for a in arrs:
                    if a.shape[1] < nr:
                        pad = np.full((a.shape[0], nr - a.shape[1]), np.nan)
                        a = np.hstack([a, pad])
                    elif a.shape[1] > nr:
                        a = a[:, :nr]
                    out.append(a)
                return np.concatenate(out, axis=0)

            # ===== edge-clip range (UT) =====
            # sgk/srp: always clipped to [t0, t1] as part of LT->UT processing.
            # bik/ktb: clipped to [t0, t1] only when time_clip=True.
            do_clip = (info["lt_shift"] != 0.0) or time_clip
            if do_clip:
                tmask = (site_time >= t0) & (site_time <= t1)
            else:
                tmask = np.ones(site_time.shape, dtype=bool)
            if not np.any(tmask):
                print(f"No MWR-{st} {pr} data within trange {trange}.")
                continue
            clipped_time = site_time[tmask]

            if ror:
                _print_ror(st)

            # ===== produce the 5 variables =====
            for nc, key, ztitle in VAR_MAP:
                name = f"iug_meteor_{st}_{key}_{pr}{suffix}"
                ydata = _stack(data_lists[nc])[tmask, :]

                if notplot:
                    loaded[name] = {"x": clipped_time, "y": ydata, "v": height}
                    continue

                store_data(name, data={"x": clipped_time, "y": ydata, "v": height})
                # degap inserts NaN rows into gaps (func='nan'); safe even with no data.
                try:
                    degap(name, dt=_degap_dt(pr))
                except Exception:
                    pass
                cmin, cmax = TCLIP_RANGE[key]
                clip(name, cmin, cmax)
                options(name, "spec", 1)
                options(name, "ytitle", info["label"] + "!CHeight!C[km]")
                options(name, "ztitle", ztitle)
                loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if (not notplot) and loaded:
        print("******************************")
        print("Data loading is successful!!")
        print("******************************")

    return loaded


def _print_ror(site):
    """Print the Rules of the Road / acknowledgement.

    sgk uses the Shigaraki MU Observatory wording; bik/ktb/srp use the common
    IUGONET DATA USE POLICY wording.
    """
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    if site == "sgk":
        print("If you acquire meteor wind radar data, we ask that you "
              "acknowledge us in your use of the data. This may be done by "
              "including text such as meteor wind radar data provided by "
              "Research Institute for Sustainable Humanosphere of Kyoto "
              "University. We would also appreciate receiving a copy of the "
              "relevant publications. The distribution of meteor wind radar "
              "data has been partly supported by the IUGONET (Inter-university "
              "Upper atmosphere Global Observation NETwork) project "
              "(http://www.iugonet.org/) funded by the Ministry of Education, "
              "Culture, Sports, Science and Technology (MEXT), Japan.")
    else:
        print("Note: If you would like to use following data for scientific "
              "purpose, please read and follow the DATA USE POLICY "
              "(http://database.rish.kyoto-u.ac.jp/arch/iugonet/data_policy/"
              "Data_Use_Policy_e.html). The distribution of meteor wind radar "
              "data has been partly supported by the IUGONET (Inter-university "
              "Upper atmosphere Global Observation NETwork) project "
              "(http://www.iugonet.org/) funded by the Ministry of Education, "
              "Culture, Sports, Science and Technology (MEXT), Japan.")
