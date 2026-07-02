"""Load function for Luneberg-lens wind profiler radar (LL-WPR) data (RISH).

Loads the zonal/meridional/vertical wind (uwnd/vwnd/wwnd), received power
(pwr1-5) and spectral width (wdt1-5) observed by the LL-WPR as time-height
profiles.

The data are distributed as CSV (ASCII), not netCDF
(``http://www.rish.kyoto-u.ac.jp/radar-group/blr/<site>/data/data/ver02.0212/``),
so ``cdf_to_tplot`` is not used; the CSV is parsed in-house and passed to
``store_data``.

Data format (confirmed from the actual CSV files):

  File name: ``YYYYMM/YYYYMMDD/YYYYMMDD.<parameter>.csv``
  Remote:    ``.../radar-group/blr/<site2>/data/data/ver02.0212/``
             site2 = biak/manado/pontianak/shigaraki

  CSV structure:
    Line 1 (header): the first cell is blank; the rest are heights [km]
       e.g. ``                ,  0.482,  0.579, ...``
    Line 2+ (data): ``YYYY/MM/DD HH:MM, v, v, ...``
       e.g. ``2006/04/01 00:00,  999.0,  999.0,    1.1, ...``
    Missing value = ``999`` (-> NaN). Rows starting with ``[`` are skipped.

  Time conversion (LT -> UT): the time_zone is fixed per site,
    bik=9, mnd=8, pon=7, sgk=9 (hours).
    unix = time_double('YYYY-MM-DD/HH:MM:00') - time_zone * 3600.
    The download window is also shifted earlier by the LT offset (reading one
    extra day) and the result is edge-clipped to the original UT trange.

  Height: the header cells after the first, converted to float [km]. A height
    value of 0 is set to NaN.

Created variables (per site/parameter): ``iug_wpr_<site>_<parameter>``
  x=time[UT], y=[time, height], v=height[km], spec=1.
  Unit (ztitle): pwr1-5 is dB; the rest (uwnd/vwnd/wwnd/wdt1-5) is m/s.
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, time_string, dailynames, download
from pyspedas.tplot_tools import degap

from iugonet.config import CONFIG

# All observation sites (default 'all').
SITE_CODE_ALL = ["bik", "mnd", "pon", "sgk"]

# All parameters (default 'all').
PARAMETER_ALL = [
    "uwnd", "vwnd", "wwnd",
    "pwr1", "pwr2", "pwr3", "pwr4", "pwr5",
    "wdt1", "wdt2", "wdt3", "wdt4", "wdt5",
]

# Site code -> directory name on the RISH server.
SITE_DIR = {
    "bik": "biak",
    "mnd": "manado",
    "pon": "pontianak",
    "sgk": "shigaraki",
}

# LT -> UT time_zone [hour]. Used both for the download-window shift and for the
# per-row LT->UT conversion; both agree at bik=9 mnd=8 pon=7 sgk=9.
TIME_ZONE = {"bik": 9.0, "mnd": 8.0, "pon": 7.0, "sgk": 9.0}

# Remote data directory:
#   'http://www.rish.kyoto-u.ac.jp/radar-group/blr/'+site2+'/data/data/ver02.0212/'
REMOTE_BASE = "http://www.rish.kyoto-u.ac.jp/radar-group/blr/"
REMOTE_SUFFIX = "/data/data/ver02.0212/"

# Units: 'dB' (index 1) is for pwr1-5 only; the rest use 'm/s' (index 0).
UNIT_ALL = ["m/s", "dB"]

# Missing value (999 -> NaN).
MISSING_VALUE = 999.0

# Start of data availability; dates before this are not read.
START_TIME = time_double("2006-3-30")

# Marker used to detect a "not found" HTML error page returned instead of a CSV.
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


def _normalize_parameters(parameter):
    """Normalize a parameter input (str/list, 'all' accepted) to valid names.

    Preserves input order and removes duplicates and invalid values.
    """
    if isinstance(parameter, str):
        items = parameter.lower().split()
    else:
        items = [str(p).lower() for p in parameter]
    if "all" in items:
        return list(PARAMETER_ALL)
    out = []
    for it in items:
        if it in PARAMETER_ALL and it not in out:
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


def _download_csv(site, parameter, trange_shifted):
    """Download the daily CSV files for a site/parameter/(LT-shifted) trange.

    HTML error pages are excluded. Returns a sorted list of local file paths.
    """
    site2 = SITE_DIR[site]
    # The remote is per site at ".../blr/<site2>/data/data/ver02.0212/".
    # remote_file is the date-only relative path; download reproduces this
    # relative structure under local_path.
    remote_path = f"{REMOTE_BASE}{site2}{REMOTE_SUFFIX}"
    pathformat = f"%Y%m/%Y%m%d/%Y%m%d.{parameter}.csv"
    remote_names = dailynames(file_format=pathformat, trange=trange_shifted,
                              res=24 * 3600.0)
    # Store per site so identically named files from other sites do not collide.
    local_data_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc",
                                  site2, "wpr", "csv")
    files = download(
        remote_file=remote_names,
        remote_path=remote_path,
        local_path=local_data_dir,
        last_version=True,
    )
    out = []
    for f in files or []:
        if os.path.isfile(f) and _is_real_csv(f):
            out.append(f)
    return sorted(set(out))


def _parse_height(header_line):
    """Extract the height array [km] from the header line.

    The cells after the first (blank) one are converted to float; a height
    value of 0 is set to NaN.
    """
    tokens = header_line.split(",")
    alt = np.array([float(t) for t in tokens[1:]], dtype=np.float64)
    alt[alt == 0.0] = np.nan
    return alt


def _parse_file(fpath, nh):
    """Read one CSV and return (times[LT strings], data[Nt, nh]).

    times are in 'YYYY-MM-DD/HH:MM:00' form (for time_double, still LT). A data
    value of 999 becomes NaN. Rows starting with ``[`` and blank rows are
    skipped. nh is the number of height bins from the header; rows with a
    mismatching column count are truncated to / NaN-padded to nh.
    """
    times = []
    rows = []
    with open(fpath, "r", errors="replace") as fh:
        # The header line is consumed by the caller, so skip it here.
        first = True
        for ln in fh:
            if first:
                first = False
                continue
            s = ln.rstrip("\n").rstrip("\r")
            if not s.strip():
                continue
            if s[:1] == "[":          # rows starting with '[' are skipped
                continue
            tok = s.split(",")
            if len(tok) < 2:
                continue
            # data[0] example: '2006/04/01 00:00'.
            dt = tok[0].strip()
            year = dt[0:4]
            month = dt[5:7]
            day = dt[8:10]
            hour = dt[11:13]
            minute = dt[14:16]
            times.append(f"{year}-{month}-{day}/{hour}:{minute}:00")

            # Values: data[1..nh]. 999 -> NaN; short rows NaN, long rows truncated.
            vals = np.full(nh, np.nan, dtype=np.float64)
            for j in range(nh):
                k = j + 1
                if k < len(tok):
                    t = tok[k].strip()
                    if t:
                        v = float(t)
                        vals[j] = np.nan if v == MISSING_VALUE else v
            rows.append(vals)

    if not times:
        return None, None
    return times, np.array(rows, dtype=np.float64)


def _load_param(files, site):
    """Read the daily files for one site/parameter and return the concatenation.

    The height of the last file read is used (only the data are concatenated
    along time; height is overwritten). Days with a different number of height
    bins cannot be concatenated and are skipped.
    Returns {'x': unix[Nt], 'height': [Nh], 'y': [Nt, Nh]} or None.
    """
    tz = TIME_ZONE[site]
    parsed = []   # (lt_times, data, height)
    for fpath in files:
        with open(fpath, "r", errors="replace") as fh:
            header_line = fh.readline().rstrip("\n").rstrip("\r")
        try:
            height = _parse_height(header_line)
        except ValueError:
            continue
        nh = len(height)
        if nh == 0:
            continue
        lt_times, data = _parse_file(fpath, nh)
        if lt_times is None:
            continue
        parsed.append((lt_times, data, height))

    if not parsed:
        return None

    height = parsed[-1][2]      # use the height of the last file
    nh = len(height)
    xs, ys = [], []
    for lt_times, data, h in parsed:
        if data.shape[1] != nh:
            continue           # skip days with a different number of height bins
        # LT -> UT
        tarr = np.asarray(time_double(lt_times), dtype=np.float64) - tz * 3600.0
        xs.append(tarr)
        ys.append(data)
    if not xs:
        return None
    return {
        "x": np.concatenate(xs),
        "height": height,
        "y": np.concatenate(ys, axis=0),
    }


def wpr_rish(
    trange=["2006-04-01", "2006-04-02"],
    site="all",
    parameter="all",
    downloadonly=False,
    suffix="",
):
    """Load LL-WPR wind, power and spectral-width data from RISH.

    The data are distributed as CSV, so they are parsed in-house rather than
    via netCDF.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day.
        Default: ['2006-04-01', '2006-04-02']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. Valid sites:
        bik (Biak) mnd (Manado) pon (Pontianak) sgk (Shigaraki).
        Default: 'all'
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter. Valid
        options: uwnd vwnd wwnd (three-component wind [m/s]), pwr1 pwr2 pwr3
        pwr4 pwr5 (received power [dB]), wdt1 wdt2 wdt3 wdt4 wdt5 (spectral
        width [m/s]).
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
        List of tplot variables created (``iug_wpr_<site>_<parameter>``). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned instead.

    Notes
    -----
    Created variables are 2-D time-height spectrogram (spec=1) variables;
    missing value 999 is mapped to NaN. To handle the LT-to-UT conversion, the
    download is done over a window shifted earlier by the site local-time offset
    (and one extra day), then edge-clipped to the original UT trange and
    gap-filled.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.wpr_rish(trange=['2006-04-01', '2006-04-02'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        print("This station code is not valid. Please input the allowed keywords, "
              "all, bik, mnd, pon, and sgk.")
        return []

    parameters = _normalize_parameters(parameter)
    if not parameters:
        print("This parameter is not valid. Please input the allowed parameters, "
              "all, uwnd, vwnd, wwnd, pwr1-5, and wdt1-5.")
        return []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0   # read one extra full day

    # Do nothing if the start date is before the data availability period.
    if t0 < START_TIME:
        print(f"No WPR data before {time_string(START_TIME)}.")
        return [] if not downloadonly else []

    loaded = []
    dl_files = []

    for st in sites:
        tz = TIME_ZONE[st]
        # LT -> UT shifted window
        start = t0 - tz * 3600.0
        trange_shifted = [time_string(start), time_string(start + day_mod * 86400.0)]

        for prm in parameters:
            files = _download_csv(st, prm, trange_shifted)
            if not files:
                continue
            if downloadonly:
                dl_files += files
                continue

            data = _load_param(files, st)
            if data is None:
                continue

            name = f"iug_wpr_{st}_{prm}{suffix}"
            store_data(name, data={"x": data["x"], "y": data["y"], "v": data["height"]})

            # ---- edge cut: original UT trange [t0, t1] (closed interval) ----
            x = data["x"]
            mask = (x >= t0) & (x <= t1)
            if not np.any(mask):
                # Do not create a variable if all data are out of range.
                store_data(name, delete=True)
                continue
            if not np.all(mask):
                store_data(name, data={"x": x[mask],
                                       "y": data["y"][mask],
                                       "v": data["height"]})

            # ---- options ----
            # Unit: 'dB' for pwr1-5 only, 'm/s' otherwise.
            unit = UNIT_ALL[1] if prm.startswith("pwr") else UNIT_ALL[0]
            # The !C line break becomes \n in Python.
            options(name, "ytitle", f"WPR-{st}\nHeight\n[km]")
            options(name, "ztitle", f"{prm}\n[{unit}]")
            options(name, "labels", f"WPR-{st} [km]")
            options(name, "spec", 1)

            # ---- gap fill ----
            try:
                degap(name, overwrite=True)
            except Exception:
                # Keep the variable even if degap fails (e.g. non-monotonic time).
                pass

            loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if loaded:
        print("*****************************")
        print("Data loading is successful!!")
        print("*****************************")
        _print_ack()
    return loaded


def _print_ack():
    """Print the acknowledgement."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("we ask that you acknowledge us in your use of the data. This may")
    print("be done by including text such as WPR(LQ-7) data provided by Research")
    print("Institute for Sustainable Humanosphere of Kyoto University. The Biak,")
    print("Manado and Pontianak-WPR data were obtained by the JEPP-HARIMAU")
    print("and SATREPS-MCCOE projects promoted by JAMSTEC and BPPT under collaboration")
    print("with RISH of Kyoto University and LAPAN. We would also appreciate receiving")
    print("a copy of the relevant publications. The distribution of WPR(LQ-7) data has")
    print("been partly supported by the IUGONET (Inter-university Upper atmosphere Global")
    print("Observation NETwork) project (http://www.iugonet.org/) funded by the Ministry")
    print("of Education, Culture, Sports, Science and Technology (MEXT), Japan.")
