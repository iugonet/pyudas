"""Load function for L-band Lower Troposphere Radar (LTR) wind data (RISH).

The only site is Shigaraki (``sgk``). The L-band Lower Troposphere Radar
(= Shigaraki Boundary Layer Radar) observes the three-component wind, echo
power and spectral width of the troposphere at heights of ~0.7-10 km.

The data are distributed as CSV (not netCDF). The daily, per-parameter CSV
files from the RISH radar-group server are parsed in-house to create tplot
variables (``cdf_to_tplot`` cannot be used). The files are fetched with the
pyspedas ``download`` and parsed before ``store_data``.

Data format (confirmed from the actual CSV files):

File: ``ver02.0212/YYYYMM/YYYYMMDD/YYYYMMDD.<parameter>.csv``
  (e.g. ``ver02.0212/200512/20051201/20051201.uwnd.csv``)
  - Line 1: a leading blank cell followed by height values (km). The actual
            data have 63 bins. Heights differ slightly by parameter (uwnd-type
            0.671.., pwr/wdt-type 0.675..).
  - Line 2+: ``YYYY/MM/DD HH:MM`` (local time JST) followed by the value at each
            height. 10-minute interval, 144 records/day. Missing value ``999``.
  Time conversion: the leading ``YYYY/MM/DD HH:MM`` is interpreted as JST and
  shifted to UT by ``- 9h``.

Fixed array size (to match the original output):
  The original allocates a fixed 70 height bins, fills only the actual heights
  present in the header (63), and leaves the rest (63-69) as NaN. This
  implementation likewise outputs **70 bins** (heights/data beyond the actual
  column count are NaN), padding every day to 70 even if the actual column
  count differs. A header height value of 0 becomes NaN (no 0 appears in the
  actual data).

LT->UT download window:
  The timespan is shifted earlier by 9h and one extra day is fetched, then the
  result is edge-clipped to the original UT range. This is because the UT range
  edges straddle the LT(JST) local-date files, so the window is shifted earlier
  and finally clipped to the UT trange.

Created variables (one per parameter, all 2-D time-height with spec=1):
  iug_ltr_sgk_<parameter>   x=time[UT], y=[time,height], v=height[km]
  parameter: uwnd vwnd wwnd (three-component wind [m/s]),
             pwr1..pwr5 (echo power [dB]),
             wdt1..wdt5 (spectral width [m/s])
"""
import os

import numpy as np

from pyspedas import (store_data, options, time_double, time_string,
                      dailynames, download)
from pyspedas.tplot_tools import degap, clip

from iugonet.config import CONFIG

# All observation sites (Shigaraki only).
SITE_CODE_ALL = ["sgk"]

# All parameters (this order is preserved).
PARAMETER_ALL = ["uwnd", "vwnd", "wwnd",
                 "pwr1", "pwr2", "pwr3", "pwr4", "pwr5",
                 "wdt1", "wdt2", "wdt3", "wdt4", "wdt5"]

# Units: 'dB' (index 1) is for pwr1-5 only; the rest use 'm/s' (index 0).
UNIT_ALL = ["m/s", "dB"]
_DB_PARAMS = {"pwr1", "pwr2", "pwr3", "pwr4", "pwr5"}

# RISH radar-group server.
REMOTE_DATA_DIR = ("http://www.rish.kyoto-u.ac.jp/radar-group/blr/"
                   "shigaraki/data/data/ver02.0212/")

# Data availability period for the Shigaraki LTR; dates outside are skipped.
SGK_START = time_double("1999-07-07")
SGK_END = time_double("2006-03-29")

# LT(JST) - UT shift in seconds.
LT_SHIFT = 9.0 * 3600.0

# Missing value (999 -> NaN).
MISSING_VALUE = 999.0

# Fixed number of height bins (70) to match the original output.
N_HEIGHT_FIXED = 70

# Marker used to detect a "not found" HTML error page returned instead of a CSV.
_HTML_MARKERS = (b"<!doctype", b"<html")


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


def _is_real_csv(path):
    """Return True if the downloaded file is a real CSV (not an HTML error page).

    The RISH server may return an HTML page with status 200 for a missing date,
    so the leading bytes are checked to exclude HTML.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(512).lstrip().lower()
    except OSError:
        return False
    return not head.startswith(_HTML_MARKERS)


def _download_csv(parameter, win_trange, no_update):
    """Download the daily CSV files for a parameter/(LT-shifted) trange.

    HTML error pages are excluded.
    """
    pathformat = "%Y%m/%Y%m%d/%Y%m%d." + parameter + ".csv"
    remote_names = dailynames(file_format=pathformat, trange=win_trange,
                              res=24 * 3600.0)
    # download reproduces the remote_file relative path (YYYYMM/YYYYMMDD/...)
    # under local_path, storing into
    # CONFIG/local_data_dir/rish/misc/sgk/ltr/csv/YYYYMM/YYYYMMDD/...
    local_data_dir = os.path.join(CONFIG["local_data_dir"],
                                  "rish", "misc", "sgk", "ltr", "csv")
    # last_version is not used: LTR CSVs have fixed file names without a version
    # suffix, and the RISH radar-group server rejects directory listings with
    # 403, so last_version=True would fail to list and thus fail to download.
    # With unique file names the behavior is the same either way.
    files = download(
        remote_file=remote_names,
        remote_path=REMOTE_DATA_DIR,
        local_path=local_data_dir,
        no_download=no_update,
        last_version=False,
    )
    out = []
    for f in files or []:
        if os.path.isfile(f) and _is_real_csv(f):
            out.append(f)
    return sorted(set(out))


def _parse_csv(path):
    """Read one LTR CSV and return {time, height, data}.

    Returns
    -------
    dict or None
      {'time': (Nt,) unix seconds UT, 'height': (Nc,) km, 'data': (Nt, Nc)}
      Nc is the actual number of height columns in that file (header cells - 1).
      Missing value 999 and height 0 become NaN. Returns None if
      unreadable/empty.

      Header: the heights are the cells after the first; a height of 0 -> NaN.
      Time: 'YYYY/MM/DD HH:MM' (JST), converted via time_double minus 9h.
      Value: 999 -> NaN. Rows starting with '[' are skipped.
    """
    try:
        with open(path, "r", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None

    # ----- header (heights) -----
    header = lines[0].split(",")
    if len(header) < 2:
        return None
    # The actual heights are the header cells after the first.
    height = np.array([_safe_float(h) for h in header[1:]], dtype=np.float64)
    n_col = height.size
    # A height of 0 is treated as missing -> NaN.
    height = np.where(height == 0.0, np.nan, height)

    # ----- data rows -----
    times = []
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        # Rows starting with '[' are skipped.
        if ln.lstrip().startswith("["):
            continue
        tok = ln.split(",")
        cell0 = tok[0]
        # cell0 is 'YYYY/MM/DD HH:MM': year 0:4, month 5:7, day 8:10, hour 11:13,
        # minute 14:16.
        if len(cell0) < 16:
            continue
        year = cell0[0:4]
        month = cell0[5:7]
        day = cell0[8:10]
        hour = cell0[11:13]
        minute = cell0[14:16]
        # JST -> UT
        t_ut = float(time_double(f"{year}-{month}-{day}/{hour}:{minute}")) - LT_SHIFT

        # Values are tok[1:1+n_col].
        vals = tok[1:1 + n_col]
        arr = np.full(n_col, np.nan, dtype=np.float64)
        for j, v in enumerate(vals):
            fv = _safe_float(v)
            # 999 -> NaN
            arr[j] = np.nan if fv == MISSING_VALUE else fv
        times.append(t_ut)
        rows.append(arr)

    if not times:
        return None
    return {
        "time": np.asarray(times, dtype=np.float64),
        "height": height,
        "data": np.vstack(rows),
    }


def _safe_float(token):
    """Convert a string to float; empty/non-numeric yields NaN.

    Returns NaN on the safe side; the LTR CSV contains numeric values only.
    """
    s = token.strip()
    if not s:
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def _pad_to(arr2d, height, n_target):
    """Pad (Nt, Nc) data and (Nc,) height with trailing NaNs to n_target columns.

    The original always outputs a fixed 70 bins, so columns below n_target are
    NaN-padded and any above are truncated.
    """
    nt, nc = arr2d.shape
    if nc < n_target:
        pad = np.full((nt, n_target - nc), np.nan)
        arr2d = np.hstack([arr2d, pad])
        hpad = np.full(n_target - nc, np.nan)
        height = np.concatenate([height, hpad])
    elif nc > n_target:
        arr2d = arr2d[:, :n_target]
        height = height[:n_target]
    return arr2d, height


def ltr_rish(
    trange=["2005-12-01", "2005-12-02"],
    site="all",
    parameter="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load Lower Troposphere Radar (LTR) wind data from RISH.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day. To handle LT(JST) -> UT, the download window is
        shifted earlier by 9h and finally edge-clipped to the original UT range.
        The data are available for 1999-07-07 to 2006-03-29.
        Default: ['2005-12-01', '2005-12-02']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. The only valid site
        is 'sgk' (Shigaraki).
        Default: 'all'
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter. Valid
        options (in this order): uwnd vwnd wwnd pwr1 pwr2 pwr3 pwr4 pwr5 wdt1
        wdt2 wdt3 wdt4 wdt5. uwnd=zonal wind, vwnd=meridional wind,
        wwnd=vertical wind [m/s]; pwrN=echo power [dB]; wdtN=Doppler spectral
        width [m/s].
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
        Accepted for compatibility; the LT->UT processing always edge-clips to
        the UT trange.
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
        List of tplot variables created (``iug_ltr_sgk_<parameter>``). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Notes
    -----
    Created variables are 2-D time-height spectrogram (spec) variables. The
    height axis is a fixed 70 bins (63 observed bins plus trailing NaNs) to
    match the original output; missing value 999 is mapped to NaN.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.ltr_rish(trange=['2005-12-01', '2005-12-02'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    if not sites:
        print("This station code is not valid. Please input the allowed "
              "keywords, all, sgk.")
        return {} if notplot else []

    params = _normalize(parameter, PARAMETER_ALL)
    if not params:
        print("This parameter is not valid. Please input the allowed keywords, "
              "all, uwnd, vwnd, wwnd, pwr1-5, wdt1-5.")
        return {} if notplot else []

    # ----- download window: shift earlier by 9h (LT->UT) and read one extra day
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0
    win_start = t0 - LT_SHIFT
    win_trange = [time_string(win_start),
                  time_string(win_start + day_mod * 86400.0)]

    loaded = {} if notplot else []
    dl_files = []

    # The only site is sgk.
    st = sites[0]

    for pr in params:
        files = _download_csv(pr, win_trange, no_update)

        if downloadonly:
            dl_files += files
            continue

        if not files:
            print(f"No LTR-{st} {pr} data found in {trange}.")
            continue

        # ----- parse all files and concatenate along time -----
        # The height of the last file is used (only data are concatenated;
        # height is overwritten). Columns are padded to a fixed 70 bins.
        t_list, d_list = [], []
        last_height = None
        max_col = 0
        parsed = []
        for path in files:
            d = _parse_csv(path)
            if d is None:
                continue
            parsed.append(d)
            max_col = max(max_col, d["height"].size)
        if not parsed:
            print(f"No valid LTR-{st} {pr} data parsed in {trange}.")
            continue

        # Always 70 bins; the actual column count is not expected to exceed 70,
        # but take the max for safety.
        n_target = max(N_HEIGHT_FIXED, max_col)
        for d in parsed:
            data2d, h = _pad_to(d["data"], d["height"], n_target)
            t_list.append(d["time"])
            d_list.append(data2d)
            last_height = h  # use the height of the last file

        all_time = np.concatenate(t_list)
        all_data = np.concatenate(d_list, axis=0)

        # ----- edge-clip to the UT trange -----
        tmask = (all_time >= t0) & (all_time <= t1)
        if not np.any(tmask):
            print(f"No LTR-{st} {pr} data within trange {trange}.")
            continue
        clip_time = all_time[tmask]
        clip_data = all_data[tmask, :]

        name = f"iug_ltr_{st}_{pr}{suffix}"

        if notplot:
            loaded[name] = {"x": clip_time, "y": clip_data, "v": last_height}
            continue

        store_data(name, data={"x": clip_time, "y": clip_data, "v": last_height})

        # ----- options -----
        unit = UNIT_ALL[1] if pr in _DB_PARAMS else UNIT_ALL[0]
        options(name, "spec", 1)
        options(name, "ytitle", f"LTR-{st}\nHeight\n[km]")
        options(name, "ztitle", f"{pr}\n[{unit}]")
        # pyspedas expects labels as a list.
        options(name, "labels", [f"LTR-{st} [km]"])

        # ----- gap fill: 10-minute data; insert NaN rows into gaps -----
        try:
            degap(name, dt=600.0)
        except Exception:
            pass

        loaded.append(name)

        if ror:
            _print_ror()

    if downloadonly:
        return sorted(set(dl_files))

    if (not notplot) and loaded:
        print("*****************************")
        print("Data loading is successful!!")
        print("*****************************")

    return loaded


def _print_ror():
    """Print the acknowledgement (Rules of the Road)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("If you acquire LTR data, we ask that you acknowledge us in your use")
    print("of the data. This may be done by including text such as LTR data")
    print("provided by Research Institute for Sustainable Humanosphere of")
    print("Kyoto University. We would also appreciate receiving a copy of the")
    print("relevant publications. The distribution of LTR data has been partly")
    print("supported by the IUGONET (Inter-university Upper atmosphere Global")
    print("Observation NETwork) project (http://www.iugonet.org/) funded by the")
    print("Ministry of Education, Culture, Sports, Science and Technology "
          "(MEXT), Japan.")
