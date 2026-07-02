"""Load function for RISH automatic weather station (AWS) surface meteorology data.

The ASCII (CSV) files are fetched from the RISH server and parsed directly with
pandas/numpy to build tplot variables (they are not CDF, so ``cdf_to_tplot``
cannot be used). Two file formats are handled:

sgk (Shigaraki): fixed-width CSV. The first line is a header
  ``date, time_zone, lat, lon, alt`` (e.g. ``1994/05/01, +9, 136.10, 34.85,
  385``); subsequent lines are ``time, press, temp, rh, uwnd, vwnd, *, *`` (the
  last two columns are ignored). Missing value ``-999``. LT->UT conversion uses
  the header time_zone.
  Variables: iug_aws_sgk_{press,temp,rh,uwnd,vwnd}

id (bik/ktb/mnd/pon, Indonesia): comma-separated CSV with a 2-line header. Each
  data row is ``date, time, VALID, press, VALID, precipi, VALID, rh, VALID, sr,
  VALID, temp, VALID, wnddir, VALID, wndspd`` (16 columns + trailing blank). A
  value is missing (NaN) unless the ``status`` column just before it is 'VALID'.
  time_zone is fixed per station (bik=9, ktb=7, mnd=8, pon=7). Lines starting
  with ``[`` are skipped. An older format with <=15 fields (no press) is also
  handled.
  Variables: iug_aws_{site}_{press,precipi,rh,sr,temp,wnddir,wndspd}
"""
import os
import re

import numpy as np
import pandas as pd

from pyspedas import store_data, options, time_double, time_string, dailynames, download

from iugonet.config import CONFIG

# all stations (default 'all')
SITE_CODE_ALL = ["bik", "ktb", "mnd", "pon", "sgk"]

# station code -> directory name on the RISH server
SITE_DIR = {
    "bik": "biak",
    "ktb": "kototabang",
    "mnd": "manado",
    "pon": "pontianak",
    "sgk": "shigaraki",
}

# time_zone (LT - UT, hours) for the id stations
ID_TIME_ZONE = {"bik": 9.0, "ktb": 7.0, "mnd": 8.0, "pon": 7.0}

REMOTE_DATA_DIR = "http://www.rish.kyoto-u.ac.jp/radar-group/surface/"

# marker to detect when the fetched ASCII is the server's "not found" HTML error page
_HTML_MARKERS = (b"<!doctype", b"<html")


def _normalize_sites(site):
    """Normalize the site input (str/list, 'all' accepted) to a list of valid station codes.

    Preserves the input order and removes duplicates and invalid codes.
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


def _is_real_csv(path):
    """Return whether a downloaded file is a real CSV (not an HTML error page).

    The RISH server may return 200 with HTML for a non-existent date, so the
    leading bytes are inspected to exclude HTML.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(512).lstrip().lower()
    except OSError:
        return False
    return not head.startswith(_HTML_MARKERS)


def _download_csv(site, trange_shifted):
    """Download the daily CSV files for a station and (LT-shifted) trange; return local paths.

    HTML error pages are excluded.
    """
    pathformat = SITE_DIR[site] + "/aws/csv/%Y/%Y%m/%Y%m%d.csv"
    remote_names = dailynames(file_format=pathformat, trange=trange_shifted, res=24 * 3600.0)
    # download recreates the remote relative path (SITE_DIR/aws/csv/...) under
    # local_path, so only the misc root is specified here
    # -> CONFIG/local_data_dir/rish/misc/<site2>/aws/csv/YYYY/YYYYMM/YYYYMMDD.csv
    local_data_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc")
    files = download(
        remote_file=remote_names,
        remote_path=REMOTE_DATA_DIR,
        local_path=local_data_dir,
        last_version=True,
    )
    out = []
    for f in files or []:
        if os.path.isfile(f) and _is_real_csv(f):
            out.append(f)
    return sorted(set(out))


def _to_float_missing(tokens, missing=-999.0):
    """Convert a list of string tokens to a float array, mapping the fill value (-999) to NaN."""
    arr = np.array([float(t) for t in tokens], dtype=np.float64)
    arr[arr == missing] = np.nan
    return arr


_NUM_RE = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)")


def _idl_float(s):
    m = _NUM_RE.match(s)
    if not m:
        return 0.0
    return float(m.group(1).replace("d", "e").replace("D", "e"))


def _idl_float_arr(tokens):
    return np.array([_idl_float(t) for t in tokens], dtype=np.float64)


def _idl_float_missing(tokens, missing=-999.0):
    """Convert tokens with _idl_float, then map values == -999 to NaN.

    The fill masking is applied to all five sgk variables; the fixed-width
    digit truncation is reproduced in _idl_float.
    """
    arr = _idl_float_arr(tokens)
    arr[arr == missing] = np.nan
    return arr


# Fixed-width columns of the sgk records. Each field is sliced by absolute
# column position, so a value wider than its field loses its trailing digit
# (e.g. vwnd '    0.47' -> ln[42:49]='    0.4' -> 0.4). This truncation is
# reproduced to match the original output bit-for-bit.
_SGK_SLICES = {
    "time": (0, 8), "press": (10, 17), "temp": (18, 25),
    "rh": (26, 33), "uwnd": (34, 41), "vwnd": (42, 49),
}


def _load_sgk(files):
    """Read the sgk (Shigaraki) fixed-width CSV; return {time, press, temp, rh, uwnd, vwnd}.

    The date and time_zone are taken from each file's header line, and each
    row's time is converted to UT.
    """
    t_all, press_all, temp_all, rh_all, uwnd_all, vwnd_all = ([] for _ in range(6))

    for fpath in files:
        with open(fpath, "r", errors="replace") as fh:
            lines = fh.read().splitlines()
        if len(lines) < 2:
            continue
        header = lines[0].split(",")
        date = header[0].strip()                 # e.g. '1994/05/01'
        time_zone = float(header[1])             # e.g. +9
        yy, mm, dd = date.split("/")
        date_prefix = f"{yy}-{mm}-{dd}/"

        times, press, temp, rh, uwnd, vwnd = ([] for _ in range(6))
        for ln in lines[1:]:
            if not ln.strip():
                continue
            # read by fixed-width column position (_SGK_SLICES), not split(',')
            if len(ln) < 49:
                ln = ln.ljust(49)
            times.append(ln[slice(*_SGK_SLICES["time"])].strip())
            press.append(ln[slice(*_SGK_SLICES["press"])])
            temp.append(ln[slice(*_SGK_SLICES["temp"])])
            rh.append(ln[slice(*_SGK_SLICES["rh"])])
            uwnd.append(ln[slice(*_SGK_SLICES["uwnd"])])
            vwnd.append(ln[slice(*_SGK_SLICES["vwnd"])])

        if not times:
            continue
        # LT -> UT
        tarr = np.asarray(time_double([date_prefix + s for s in times]),
                          dtype=np.float64) - time_zone * 3600.0
        t_all.append(tarr)
        # float() reads only the leading number (the fixed-width truncation is
        # reproduced in _idl_float); all five variables mask value == -999 to NaN.
        press_all.append(_idl_float_missing(press))
        temp_all.append(_idl_float_missing(temp))
        rh_all.append(_idl_float_missing(rh))
        uwnd_all.append(_idl_float_missing(uwnd))
        vwnd_all.append(_idl_float_missing(vwnd))

    if not t_all:
        return None
    return {
        "x": np.concatenate(t_all),
        "press": np.concatenate(press_all),
        "temp": np.concatenate(temp_all),
        "rh": np.concatenate(rh_all),
        "uwnd": np.concatenate(uwnd_all),
        "vwnd": np.concatenate(vwnd_all),
    }


def _load_id(files, site):
    """Read an id-station CSV (bik/ktb/mnd/pon); return the per-parameter arrays.

    Skips the 2-line header, comma-separated. A value is NaN unless its status
    column is 'VALID'. Both the >15-field (with press) and <=15-field (no press)
    formats are handled.
    """
    time_zone = ID_TIME_ZONE[site]
    keys = ["press", "precipi", "rh", "sr", "temp", "wnddir", "wndspd"]
    t_all = []
    data_all = {k: [] for k in keys}

    for fpath in files:
        with open(fpath, "r", errors="replace") as fh:
            lines = fh.read().splitlines()
        if len(lines) <= 2:
            continue

        times = []
        vals = {k: [] for k in keys}
        flags = {k: [] for k in keys}
        for ln in lines[2:]:               # first two lines are the header
            if not ln:
                continue
            if ln[:1] == "[":              # skip lines starting with '['
                continue
            d = ln.split(",")
            if len(d) < 3:
                continue
            # date(d[0]) + '/' + time(d[1]) -> UT
            times.append(d[0].strip() + "/" + d[1].strip())
            if len(d) <= 15:
                # older format: no press. precipi=3, rh=5, sr=7, temp=9,
                # wnddir=11, wndspd=13; status is the column just before each.
                vmap = {"press": None, "precipi": 3, "rh": 5, "sr": 7,
                        "temp": 9, "wnddir": 11, "wndspd": 13}
                fmap = {"press": None, "precipi": 2, "rh": 4, "sr": 6,
                        "temp": 8, "wnddir": 10, "wndspd": 12}
            else:
                # normal format: press=3, precipi=5, rh=7, sr=9, temp=11,
                # wnddir=13, wndspd=15; status is the column just before each.
                vmap = {"press": 3, "precipi": 5, "rh": 7, "sr": 9,
                        "temp": 11, "wnddir": 13, "wndspd": 15}
                fmap = {"press": 2, "precipi": 4, "rh": 6, "sr": 8,
                        "temp": 10, "wnddir": 12, "wndspd": 14}
            for k in keys:
                vi = vmap[k]
                if vi is None or vi >= len(d):
                    vals[k].append(np.nan)
                    flags[k].append("VALID")     # press missing: insert NaN directly
                    if vi is None:
                        flags[k][-1] = "INVALID"
                    continue
                vals[k].append(d[vi].strip())
                fi = fmap[k]
                flags[k].append(d[fi].strip() if (fi is not None and fi < len(d)) else "")

        if not times:
            continue
        tarr = np.asarray(time_double(times), dtype=np.float64) - time_zone * 3600.0
        t_all.append(tarr)
        for k in keys:
            v = vals[k]
            fl = flags[k]
            out = np.empty(len(v), dtype=np.float64)
            for i in range(len(v)):
                if fl[i] != "VALID":
                    out[i] = np.nan
                else:
                    try:
                        out[i] = float(v[i])
                    except (TypeError, ValueError):
                        out[i] = np.nan
            data_all[k].append(out)

    if not t_all:
        return None
    res = {"x": np.concatenate(t_all)}
    for k in keys:
        res[k] = np.concatenate(data_all[k])
    return res


def _clip_store(name, x, y, t0, t1, ytitle):
    """Time clip, then store_data + options(ytitle). Returns False (and stores nothing) if empty.

    The time range is the closed interval [t0, t1], as in pyspedas time_clip.
    """
    mask = (x >= t0) & (x <= t1)
    if not np.any(mask):
        return False
    store_data(name, data={"x": x[mask], "y": y[mask]})
    options(name, "ytitle", ytitle)
    return True


def aws_rish(
    trange=["2007-08-01", "2007-08-06"],
    site="all",
    downloadonly=False,
    suffix="",
):
    """Load RISH automatic weather station (AWS) surface meteorology data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2007-08-01', '2007-08-06']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. Valid sites: bik ktb
        mnd pon sgk (sgk=Shigaraki, bik=Biak, ktb=Kototabang, mnd=Manado,
        pon=Pontianak).
        Default: 'all'
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created. Empty list if no data were loaded. If
        ``downloadonly`` is set, the list of downloaded file paths is returned
        instead.

    Notes
    -----
    A full day is always read even if trange spans less than a day. Because of
    the LT->UT time shift, files are fetched over a window shifted earlier by
    the station local-time offset (+1 day) and then clipped to the original UT
    trange.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.aws_rish(trange=['2007-08-01', '2007-08-06'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        print("This station code is not valid. Please input the allowed keywords, "
              "all, bik, ktb, mnd, pon, and sgk.")
        return []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0   # read one extra full day

    loaded = []
    dl_files = []

    for st in sites:
        # generate daily file names over the LT->UT shifted window
        tz = 9.0 if st == "sgk" else ID_TIME_ZONE[st]
        start = t0 - tz * 3600.0
        trange_shifted = [time_string(start), time_string(start + day_mod * 86400.0)]

        files = _download_csv(st, trange_shifted)
        if not files:
            print(f"No AWS-{st} data found in {trange}.")
            continue
        if downloadonly:
            dl_files += files
            continue

        if st == "sgk":
            d = _load_sgk(files)
            if d is None:
                continue
            params = [
                ("press", "AWS-sgk!CPress.!C[hPa]"),
                ("temp", "AWS-sgk!CTemp.!C[degree C]"),
                ("rh", "AWS-sgk!CRH!C[%]"),
                ("uwnd", "AWS-sgk!Cuwnd!C[m/s]"),
                ("vwnd", "AWS-sgk!Cvwnd!C[m/s]"),
            ]
            for key, ytitle in params:
                name = f"iug_aws_sgk_{key}{suffix}"
                if _clip_store(name, d["x"], d[key], t0, t1, ytitle):
                    loaded.append(name)
        else:
            d = _load_id(files, st)
            if d is None:
                continue
            params = [
                ("press", f"AWS-{st}!CPress.!C[hPa]"),
                ("precipi", f"AWS-{st}!CPrecipi.!C[mm]"),
                ("rh", f"AWS-{st}!CRH!C[%]"),
                ("sr", f"AWS-{st}!CSolar rad.!C[kW/m2]"),
                ("temp", f"AWS-{st}!CTemp.!C[degree C]"),
                ("wnddir", f"AWS-{st}!CWind dirction!C[degree]"),
                ("wndspd", f"AWS-{st}!CWind speed!C[m/s]"),
            ]
            for key, ytitle in params:
                name = f"iug_aws_{st}_{key}{suffix}"
                if _clip_store(name, d["x"], d[key], t0, t1, ytitle):
                    loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if loaded:
        print("*****************************")
        print("Data loading is successful!!")
        print("*****************************")
    return loaded
