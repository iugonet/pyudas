"""Load function for RISH Shigaraki (MU observatory) ionosonde (ionogram) data.

Reads ionogram data from the Shigaraki (sgk) ionosonde. Each file holds a single
observation time (15-minute interval) as ASCII text: a 2-D echo-intensity map of
frequency (2.00-18.00 MHz, 161 points at 0.10 MHz steps) vs observation height
(51-699 km, 217 points at 3 km steps). All observation times are stacked to form
a 3-D (time x frequency x height) tplot variable.

ASCII format (one file):
  lines 0-8 : 9 header lines
            line0 "Shigaraki ionosonde data"
            line1 "Start time: YYYY-MM-DD HH:MM"  (observation start, LT)
            line2 "Observation mode: ..."
            line3 "Minimum frequency (MHz): ..."
            line4 "Maximum frequency (MHz): ..."
            line5 "Minimum height (km): ..."
            line6 "Maximum height (km): ..."
            line7 "Sweep speed (kHz/sec): ..."
            line8 "Transmission power: ..."
  line 9    : frequency axis (161 whitespace-separated values, MHz)
  line 10-  : per-height rows "height intensity[161]" (height km + echo intensity)

Times are converted from LT to UT with
``time_double('YYYY-MM-DD/HH:MM') - 9h``. File names and directories are in LT;
the data times are in UT.

Because the data are ASCII rather than CDF, the shared loader is not used;
files are fetched with pyspedas ``download`` and parsed locally with numpy.

Data distribution:
  http://database.rish.kyoto-u.ac.jp/arch/mudb/data/ionosonde/text/

Created variables:
  fixed_freq=False (default): ``iug_ionosonde_sgk_ionogram``
      3-D (x=time, y=[time,freq,height], v1=freq[MHz], v2=height[km]).
  fixed_freq=True: ``iug_ionosonde_sgk_freq_{N}MHz`` (N=2,3,...,18)
      A 2-D variable per fixed frequency N MHz (x=time, y=[time,height],
      v=height[km], spec=1), extracting every 10th frequency point (= 1 MHz
      step).
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, time_clip, dailynames, download

from iugonet.config import CONFIG

# Currently only 'sgk' is available.
SITE_CODE_ALL = ["sgk"]

REMOTE_DATA_DIR = "http://database.rish.kyoto-u.ac.jp/arch/mudb/data/ionosonde/text/"

# File-name format (strftime).
PATHFORMAT = "%Y/%Y%m/%Y%m%d/%Y%m%d%H%M_ionogram.txt"

# Number of header lines.
N_HEADER = 9

# LT -> UT shift in seconds (Shigaraki = JST = UT+9h).
LT_SHIFT = 9.0 * 3600.0

ACKNOWLEDG = (
    "If you acquire the ionogram data, we ask that you acknowledge us in your "
    "use of the data. This may be done by including text such as the ionogram "
    "data provided by Research Institute for Sustainable Humanosphere of Kyoto "
    "University. We would also appreciate receiving a copy of the relevant "
    "publications. The distribution of ionogram data has been partly supported "
    "by the IUGONET (Inter-university Upper atmosphere Global Observation "
    "NETwork) project (http://www.iugonet.org/) funded by the Ministry of "
    "Education, Culture, Sports, Science and Technology (MEXT), Japan."
)


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


def _parse_ionogram(path):
    """Parse one ionogram ASCII file.

    Returns
    -------
    (time_ut, freq, height, intensity), or None for an empty/invalid file.
      time_ut   : float  observation time (unix seconds, UT)
      freq      : (Nf,)  frequency axis [MHz]
      height    : (Nh,)  height axis [km]
      intensity : (Nf, Nh)  echo intensity in [freq, height] order.
    """
    with open(path, "r") as fh:
        lines = fh.read().split("\n")
    # Strip trailing empty lines.
    while lines and lines[-1].strip() == "":
        lines.pop()
    # Need at least 9 header lines + 1 frequency line + 1 data line.
    if len(lines) < N_HEADER + 2:
        return None

    # --- Time: header[1] = "Start time: YYYY-MM-DD HH:MM". Use fixed-offset
    #     slices for date and hh:mm, then shift by -9h to obtain UT.
    h1 = lines[1]
    date = h1[12:12 + 10]
    hhmm = h1[23:23 + 5]
    time_ut = time_double(date + "/" + hhmm) - LT_SHIFT

    # --- Frequency axis: split line 9 into floats.
    freq = np.array(lines[N_HEADER].split(), dtype=np.float64)
    nf = freq.size
    if nf == 0:
        return None

    # --- Data rows: line 10 onward, "height val[nf]".
    heights = []
    rows = []
    for ln in lines[N_HEADER + 1:]:
        parts = ln.split()
        if len(parts) < nf + 1:
            continue
        vals = np.array(parts, dtype=np.float64)
        heights.append(vals[0])
        rows.append(vals[1:nf + 1])
    if not rows:
        return None

    height = np.array(heights, dtype=np.float64)            # (Nh,)
    # rows[i] = intensity along freq at height i -> (Nh, Nf). Transpose to
    # the [freq, height] order to match the original output.
    intensity = np.array(rows, dtype=np.float64).T          # (Nf, Nh)
    return time_ut, freq, height, intensity


def ionosonde_rish(
    trange=["2002-07-01", "2002-07-02"],
    site="all",
    fixed_freq=False,
    no_update=False,
    downloadonly=False,
    notplot=False,
    verbose=2,
    ror=True,
    suffix="",
):
    """Load RISH Shigaraki ionosonde (ionogram) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        When a UT range is given, the LT->UT shift (-9h) is accounted for by
        fetching the necessary LT-day files and edge-clipping to the UT range
        at the end.
        Default: ['2002-07-01', '2002-07-02']
    site : str or list of str
        Observatory/station code(s). 'all' selects every available site.
        Currently only 'sgk' is valid.
        Default: 'all'
    fixed_freq : bool
        If True, create one 2-D spectrogram variable per fixed frequency
        (2,3,...,18 MHz), ``iug_ionosonde_sgk_freq_{N}MHz``. If False, create
        the 3-D ``iug_ionosonde_sgk_ionogram``.
        Default: False
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
        List of tplot variables created. Empty list if no data were loaded.
        fixed_freq=False -> ``['iug_ionosonde_sgk_ionogram']``;
        fixed_freq=True  -> ``['iug_ionosonde_sgk_freq_2MHz', ..., '..._18MHz']``.
        If ``downloadonly`` is set, the list of downloaded file paths is
        returned; if ``notplot`` is set, a dictionary of data is returned
        instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.ionosonde_rish(trange=['2002-07-01', '2002-07-02'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    if not sites:
        print("This station code is not valid. Please input the allowed "
              "keywords, all, and sgk.")
        return {} if notplot else []

    # ===== Widen the time window by the LT->UT shift =====
    # time_org = the user-specified UT range. Fetch day_org+1 days starting at
    # start-9h.
    time_org = [time_double(trange[0]), time_double(trange[1])]
    day_org = (time_org[1] - time_org[0]) / 86400.0
    day_mod = day_org + 1.0
    win_start = time_org[0] - LT_SHIFT
    win_trange = [win_start, win_start + day_mod * 86400.0]

    # ===== File-name generation =====
    # The real data are at 15-minute intervals (:00/:15/:30/:45). Generate
    # candidates at res=900 (15 minutes); download automatically skips 404s.
    remote_names = dailynames(file_format=PATHFORMAT, trange=win_trange, res=900.0)

    loaded = {} if notplot else []

    for st in sites:  # currently only 'sgk'
        local_dir = os.path.join(
            CONFIG["local_data_dir"], "rish", st, "ionosonde", "text"
        )
        files = download(
            remote_file=remote_names,
            remote_path=REMOTE_DATA_DIR,
            local_path=local_dir,
            no_download=no_update,
            last_version=True,
            verify=False,
        )
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))

        if downloadonly:
            loaded += out_files
            continue

        if not out_files:
            print(f"No ionogram files found for {st} in {trange}.")
            continue

        # ===== Parse all files and stack along time =====
        times = []
        intens_list = []   # each element (Nf, Nh)
        freq = None
        height = None
        for path in out_files:
            res = _parse_ionogram(path)
            if res is None:
                continue
            t_ut, fq, ht, inten = res
            if freq is None:
                freq = fq
                height = ht
            times.append(t_ut)
            intens_list.append(inten)

        if not times:
            print(f"No valid ionogram data parsed for {st}.")
            continue

        site_time = np.array(times, dtype=np.float64)          # (Nt,)
        # intensity in [time, freq, height] order.
        data3d = np.array(intens_list, dtype=np.float64)       # (Nt, Nf, Nh)

        if ror:
            _print_ror()

        if not fixed_freq:
            # ===== 3-D ionogram variable =====
            name = "iug_ionosonde_sgk_ionogram" + suffix
            if notplot:
                loaded[name] = {
                    "x": site_time, "y": data3d, "v1": freq, "v2": height,
                }
            else:
                store_data(name, data={
                    "x": site_time, "y": data3d, "v1": freq, "v2": height,
                })
                # Edge-clip to the user-specified UT range.
                time_clip(name, time_org[0], time_org[1], suffix="")
                options(name, "ytitle", "Frequency [MHz]")
                options(name, "ysubtitle", "")
                loaded.append(name)
        else:
            # ===== One 2-D variable per fixed frequency =====
            # i = 0,10,20,...; the variable name is freq_(i/10+2)MHz -> 2..18 MHz.
            for i in range(0, freq.size, 10):
                mhz = i // 10 + 2
                name = f"iug_ionosonde_sgk_freq_{mhz}MHz" + suffix
                power = data3d[:, i, :]                         # (Nt, Nh)
                if notplot:
                    loaded[name] = {"x": site_time, "y": power, "v": height}
                    continue
                store_data(name, data={
                    "x": site_time, "y": power, "v": height,
                })
                # Edge-clip to the user-specified UT range.
                time_clip(name, time_org[0], time_org[1], suffix="")
                options(name, "spec", 1)
                options(name, "ytitle", "Height [km]")
                options(name, "ztitle", f"Echo power at {mhz} [MHz]")
                loaded.append(name)

    return loaded


def _print_ror():
    """Print the acknowledgement (Rules of the Road)."""
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(ACKNOWLEDG)
