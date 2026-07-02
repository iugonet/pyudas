"""Load function for Boundary Layer Radar (BLR) data (RISH).

The BLR observes tropospheric three-component wind (zonal/meridional/vertical)
and related quantities (received power pwr1-5, spectral width wdt1-5) as height
profiles (time x height). The observation sites are Kototabang (ktb), Shigaraki
(sgk) and Serpong (srp).

The data are distributed as CSV (not netCDF), so they are downloaded from the
RISH server and parsed in-house (``cdf_to_tplot`` cannot be used).

Data format (confirmed from the actual .csv files):

File: ``<remote>/YYYYMM/YYYYMMDD/YYYYMMDD.<param>.csv``
  remote = http://www.rish.kyoto-u.ac.jp/radar-group/blr/<city>/data/data/ver02.0212/
  (HTTP is redirected to HTTPS via 302; the pyspedas download handles it.)

  Line 1: height header. The first field is blank; the rest are heights [km].
          ``altitude[j] = float(height[j+1])``. A height value of 0 becomes NaN.
  Line 2+: data rows. ``YYYY/MM/DD HH:MM`` (local time, LT) followed by the
          value at each height. Missing values are ``999``. Rows starting with
          ``[`` are skipped.
  The timestamps are LT, so they are shifted to UT by ``time_shift``
  (ktb=7h, sgk=9h, srp=7h).

Site specifics:
  ktb (Kototabang): time_shift 7.0h.
  sgk (Shigaraki) : time_shift 9.0h. Data are available only for
                    1992-04-13 .. 1992-08-29.
  srp (Serpong)   : time_shift 7.0h.

Parameters (13): uwnd vwnd wwnd pwr1..pwr5 wdt1..wdt5.
  Units: pwr1-5 -> 'dB'; the rest (uwnd/vwnd/wwnd/wdt1-5) -> 'm/s'.

Created variables: iug_blr_<site>_<param> (time x height spec variables).
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, time_string, dailynames, download

from iugonet.config import CONFIG

# All observation sites (default 'all').
SITE_CODE_ALL = ["ktb", "sgk", "srp"]

# All parameters (default 'all'). The order matches the original UDAS output.
PARAMETER_ALL = [
    "uwnd", "vwnd", "wwnd",
    "pwr1", "pwr2", "pwr3", "pwr4", "pwr5",
    "wdt1", "wdt2", "wdt3", "wdt4", "wdt5",
]

# Site code -> (city directory name on the RISH server, LT-to-UT shift [hour]).
SITE_INFO = {
    "ktb": ("kototabang", 7.0),
    "sgk": ("shigaraki", 9.0),
    "srp": ("serpong", 7.0),
}

# Data availability period for sgk.
_SGK_START = time_double("1992-04-13")
_SGK_END = time_double("1992-08-29")
# Per-row truncation boundary for sgk (rows after 1992-09-01 00:00 are dropped).
_SGK_ROW_LIMIT = time_double("1992-09-01")

REMOTE_BASE = "http://www.rish.kyoto-u.ac.jp/radar-group/blr/"

# Missing value (999 -> NaN).
MISSING_VALUE = 999.0

# Marker used to detect a "not found" HTML error page returned instead of a CSV.
_HTML_MARKERS = (b"<!doctype", b"<html")

# Acknowledgement.
_ACK = (
    "If you acquire the boundary layer radar (BLR) data, we ask that you "
    "acknowledge us in your use of the data. This may be done by including "
    "text such as the BLR data provided by Research Institute for Sustainable "
    "Humanosphere of Kyoto University. We would also appreciate receiving a "
    "copy of the relevant publications. The distribution of BLR data has been "
    "partly supported by the IUGONET (Inter-university Upper atmosphere Global "
    "Observation NETwork) project (http://www.iugonet.org/) funded by the "
    "Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan."
)


def _normalize(value, valid, all_list):
    """Normalize a str/list input ('all' accepted) to a list of valid values.

    Preserves input order and removes duplicates and invalid codes.
    """
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


def _unit_of(parameter):
    """Return the unit of a parameter (pwr1-5 -> 'dB', others -> 'm/s')."""
    return "dB" if parameter.startswith("pwr") else "m/s"


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
    city, _ = SITE_INFO[site]
    remote_path = REMOTE_BASE + city + "/data/data/ver02.0212/"
    pathformat = "%Y%m/%Y%m%d/%Y%m%d." + parameter + ".csv"
    remote_names = dailynames(file_format=pathformat, trange=trange_shifted, res=24 * 3600.0)
    # download reproduces the remote_file relative path (YYYYMM/YYYYMMDD/...)
    # under local_path, storing into
    # local_data_dir/rish/misc/<site>/blr/csv/YYYYMM/YYYYMMDD/YYYYMMDD.<param>.csv.
    local_data_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", site, "blr", "csv")
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


def _parse_csv(path, time_shift, sgk_break):
    """Read one BLR CSV and return (unix_time[Nt], data[Nt, Nh], altitude[Nh]).

      - Line 1: height header; the fields after the first are heights [km].
        A height of 0 becomes NaN.
      - Line 2+: 'YYYY/MM/DD HH:MM' (LT) followed by the value at each height.
        Value 999 becomes NaN. Rows starting with '[' are skipped.
        LT -> UT is ``- time_shift*3600``.
      - For sgk only, stop reading once the timestamp exceeds 1992-09-01.
    Returns None if required elements are missing or unreadable.
    """
    try:
        with open(path, "r", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None

    # --- height header (line 1) ---
    header = lines[0].split(",")
    if len(header) < 2:
        return None
    altitude = np.array([float(h) for h in header[1:]], dtype=np.float64)
    # A height of 0 becomes NaN.
    altitude[altitude == 0.0] = np.nan
    nh = altitude.size

    # --- data rows ---
    times = []
    rows = []
    for ln in lines[1:]:
        if not ln:
            continue
        if ln[:1] == "[":            # rows starting with '[' are skipped
            continue
        d = ln.split(",")
        if len(d) < 2:
            continue
        # date 'YYYY/MM/DD HH:MM' (LT). Reformatting to 'YYYY-MM-DD/HH:MM' and
        # passing it to time_double is equivalent to the original field slicing.
        ts = d[0].strip()
        # 'YYYY/MM/DD HH:MM' -> 'YYYY-MM-DD/HH:MM'
        ymd, _, hm = ts.partition(" ")
        date_str = ymd.replace("/", "-") + "/" + hm
        lt = time_double(date_str)
        ut = lt - time_shift * 3600.0
        # For sgk, stop reading once the timestamp passes 1992-09-01.
        if sgk_break and ut > _SGK_ROW_LIMIT:
            break

        # Values: nh entries after the leading timestamp. 999 -> NaN.
        vals = d[1:1 + nh]
        row = np.full(nh, np.nan, dtype=np.float64)
        for j, v in enumerate(vals):
            try:
                fv = float(v)
            except ValueError:
                continue
            row[j] = np.nan if fv == MISSING_VALUE else fv
        times.append(ut)
        rows.append(row)

    if not times:
        return None
    return (
        np.array(times, dtype=np.float64),
        np.array(rows, dtype=np.float64),   # (Nt, Nh)
        altitude,
    )


def _print_ack():
    """Print the acknowledgement (Rules of the Road)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(_ACK)
    print("****************************************************************")


def blr_rish(
    trange=["2007-08-01", "2007-08-06"],
    site="all",
    parameter="all",
    downloadonly=False,
    suffix="",
    ror=True,
):
    """Load Boundary Layer Radar (BLR) wind data from RISH.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day.
        Default: ['2007-08-01', '2007-08-06']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are
        both accepted. 'all' selects every available site. Valid sites:
        ktb (Kototabang) sgk (Shigaraki) srp (Serpong).
        Default: 'all'
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter. Valid
        options: uwnd (zonal) vwnd (meridional) wwnd (vertical) pwr1 pwr2 pwr3
        pwr4 pwr5 wdt1 wdt2 wdt3 wdt4 wdt5.
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
        List of tplot variables created (``iug_blr_<site>_<param>``). Empty list
        if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned instead.

    Notes
    -----
    Created variables are 2-D time-height spectrogram (spec) variables; missing
    value 999 is mapped to NaN. The CSV timestamps are LT, so they are shifted
    to UT by the site time_shift (ktb/srp=7h, sgk=9h) and then clipped to the
    original UT trange. File download is done over a window shifted earlier by
    time_shift (and one extra day) to cover the LT-to-UT offset. sgk is valid
    only for the data availability period 1992-04-13..1992-08-29.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.blr_rish(trange=['2007-08-01', '2007-08-06'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL, SITE_CODE_ALL)
    if not sites:
        print("This station code is not valid. Please input the allowed keywords, "
              "all, ktb, sgk, and srp.")
        return []
    parameters = _normalize(parameter, PARAMETER_ALL, PARAMETER_ALL)
    if not parameters:
        return []

    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0   # read one extra full day

    loaded = []
    dl_files = []

    for st in sites:
        print(st)
        city, time_shift = SITE_INFO[st]

        # sgk: skip entirely if the date is outside the data availability period.
        if st == "sgk" and (t0 < _SGK_START or t0 > _SGK_END):
            continue

        # Build daily file names over the LT -> UT shifted window.
        start = t0 - time_shift * 3600.0
        trange_shifted = [time_string(start), time_string(start + day_mod * 86400.0)]

        for pr in parameters:
            files = _download_csv(st, pr, trange_shifted)
            if not files:
                continue
            if downloadonly:
                dl_files += files
                continue

            # Parse the daily CSV files and concatenate along time. The altitude
            # of the last file read is used (only the data are concatenated).
            sgk_break = (st == "sgk")
            xs, ys = [], []
            altitude = None
            for f in files:
                res = _parse_csv(f, time_shift, sgk_break)
                if res is None:
                    continue
                x, y, alt = res
                if altitude is not None and y.shape[1] != altitude.size:
                    # Skip days with a different number of height bins.
                    continue
                altitude = alt
                xs.append(x)
                ys.append(y)
            if not xs:
                continue

            x = np.concatenate(xs)
            y = np.concatenate(ys, axis=0)

            # ----- time clip -----
            # Clip to the closed interval of the original UT trange [t0, t1].
            mask = (x >= t0) & (x <= t1)
            if not np.any(mask):
                continue
            x = x[mask]
            y = y[mask]

            # ----- create tplot variable -----
            name = f"iug_blr_{st}_{pr}{suffix}"
            store_data(
                name,
                data={"x": x, "y": y, "v": altitude},
                attr_dict={"data_att": {"acknowledgment": _ACK, "PI_NAME": "H. Hashiguchi"}},
            )
            options(name, "spec", 1)
            options(name, "ytitle", f"BLR-{st}!CHeight!C[km]")
            options(name, "ztitle", f"{pr}!C[{_unit_of(pr)}]")
            # Gap handling expressed via the pyspedas data_gap option.
            options(name, "data_gap", 600)
            loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))

    if loaded:
        print("*****************************")
        print("Data loading is successful!!")
        print("*****************************")
        if ror:
            _print_ack()
    return loaded
