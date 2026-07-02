"""Load function for ICSWSE (Kyushu University) MAGDAS/CPMN magnetometer data.

Reads MAGDAS/CPMN magnetometer data in IAGA2002 ASCII format. Because the data
are ASCII rather than CDF, the shared CDF loader (:mod:`iugonet.load`) is
not used; files are fetched with pyspedas ``download`` and parsed locally before
being passed to ``store_data``.

Format notes (to match the original UDAS output):

* Remote path:
  ``<remote>/<SITE>/<Sec|Min>/<YYYY>/<SITE><YYYYMMDD>p<sec|min>.<sec|min>``
  (e.g. ``ASB/Sec/2013/ASB20130103psec.sec``).
* Each data line has the 7 whitespace-separated fields
  ``DATE TIME DOY C1 C2 C3 C4``; only the 4 components in fields 4-7
  (0-based columns 3..6) are read. The components are usually H,D,Z,F, but
  at some stations they are X,Y,Z,F (distinguishable from the file's ``DATE``
  header line).
* Times are generated as an evenly spaced index from a base time (00:00 UT of
  the date in the file name), not from the file's DATE/TIME columns: 86400
  points x 1 s for 1sec, 1440 points x 60 s for 1min.
* The fill value 99999.99 is replaced with NaN.
* tplot variable name: ``kyumag_mag_<site>_<resolution>_hdzf``.
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, dailynames, download

from iugonet.config import CONFIG

# Available station codes.
SITE_CODE_ALL = [
    "aab", "asb", "can", "ckt", "drb", "gsi", "ica", "krt", "lgz", "mgd",
    "onw", "sbh", "tir", "zgn",
    "abj", "asw", "cdo", "cmd", "dvs", "her", "ilr", "ktn", "lkw", "mlb",
    "prp", "scn", "twv",
    "abu", "bcl", "ceb", "dav", "eus", "hln", "jrs", "kuj", "lsk", "mnd",
    "ptk", "sma", "wad",
    "ama", "bik", "cgr", "daw", "ewa", "hob", "jyp", "lag", "lwa", "mut",
    "ptn", "tgg", "yak",
    "anc", "bkl", "chd", "des", "fym", "hvd", "kpg", "laq", "mcq", "nab",
    "roc", "tik", "yap",
]

RESOLUTION_ALL = ["1sec", "1min"]

# Moved 2026 from data.icswse.kyushu-u.ac.jp to i-SPES. The i-SPES server only
# serves the data to the SPEDAS client, i.e. it requires the HTTP request to
# carry ``User-Agent: SPEDAS`` (other user agents get 403). See _SPEDAS_HEADERS.
REMOTE_DATA_DIR = "https://data.i-spes.kyushu-u.ac.jp/gmag/data/"
_SPEDAS_HEADERS = {"User-Agent": "SPEDAS"}

LOCAL_SUBDIR = "icswse/magnetometer/iaga/"

# Fill value flag.
BAD_VALUE = 99999.99

ACKNOWLEDG_STRING = (
    "Scientists who want to engage in collaboration with ICSWSE\n"
    "should contact the project leader of MAGDAS/CPMN\n"
    "observations, Dr. Akimasa Yoshikawa, Kyushu Univ., who will\n"
    "organize such collaborations.\n"
    "There is a possibility that the PI of MAGDAS will arrange offers\n"
    "so that there is less overlapping of themes between MAGDAS research groups\n"
    "Before you use MAGDAS/CPMN data for your papers,\n"
    "you must agree to the following points;\n"
    " \n"
    " 1. Before you submit your paper, you must contact the PI\n"
    "    (Dr. Akimasa Yoshikawa: yoshi@geo.kyushu-u.ac.jp) and\n"
    "    discuss authorship.\n"
    " 2. When you submit your paper after doing the above item 1, you must mention\n"
    "    the source of the data in the acknowledgment section of your paper.\n"
    " 3. In general, you must use the following references:\n"
    "     1. Yumoto, K., and the 210MM Magnetic Observation Group, The STEP\n"
    "        210 magnetic meridian network project, J. Geomag. Geoelectr.,\n"
    "        48, 1297-1310., 1996.\n"
    "     2. Yumoto, K. and the CPMN Group, Characteristics of Pi 2 magnetic\n"
    "        pulsations observed at the CPMN stations: A review of the STEP\n"
    "        results, Earth Planets Space, 53, 981-992, 2001.\n"
    "     3. Yumoto K. and the MAGDAS Group, MAGDAS project and its application\n"
    "        for space weather, Solar Influence on the Heliosphere and Earth's\n"
    "        Environment: Recent Progress and Prospects, Edited by N. Gopalswamy\n"
    "        and A. Bhattacharyya, ISBN-81-87099-40-2, pp. 309-405, 2006.\n"
    "     4. Yumoto K. and the MAGDAS Group, Space weather activities at SERC\n"
    "        for IHY: MAGDAS, Bull. Astr. Soc. India, 35, pp. 511-522, 2007.\n"
    " 4. In all circumstances, if anything is published you must send\n"
    "    a hardcopy to the following address:\n"
    " \n"
    "        Dr. Akimasa Yoshikawa\n"
    "        PI of MAGDAS/CPMN Project\n"
    "        International Center for Space Weather Science and Education,\n"
    "        Kyushu University CE10\n"
    "        744, Motooka, Nishi-ku, Fukuoka 819-0395, JAPAN\n"
    "        TEL/FAX:+81-92-802-6240, e-mail: yoshi@geo.kyushu-u.ac.jp"
)


def _normalize_list(value, valid):
    """Normalize the input (str/list, 'all' accepted) to a list of valid lowercase codes.

    Preserves the input order and removes duplicates and invalid codes.
    """
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(s).lower() for s in value]
    if "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _pathformat(site, resolution):
    """Build the remote relative-path format (strftime) for a site and resolution.

    Examples:
        site='asb', resolution='1sec' -> 'ASB/Sec/%Y/ASB%Y%m%dpsec.sec'
        site='asb', resolution='1min' -> 'ASB/Min/%Y/ASB%Y%m%dpmin.min'
    """
    su = site[:3].upper()
    middle = resolution[1:2].upper() + resolution[2:4].lower()   # 'Sec' / 'Min'
    suf = resolution[1:4].lower()                                # 'sec' / 'min'
    return f"{su}/{middle}/%Y/{su}%Y%m%dp{suf}.{suf}"


def _read_iaga2002(path):
    """Read one IAGA2002 file and return the 4-component data array and labels.

    Rules:
      * Skip the header up to and including the column-heading line starting
        with ``DATE``.
      * Data lines have the 7 whitespace-separated fields
        ``DATE TIME DOY C1 C2 C3 C4``; only the 4 components in columns 3..6
        (0-based) are read.

    Returns
    -------
    (rdata, labels)
        rdata : ndarray, shape (nrec, 4), dtype float64
        labels : list[str] of length 4. Component names extracted from the DATE
                 heading line (e.g. ['H','D','Z','F']); ['H','D','Z','F'] if not
                 extractable.
    """
    labels = None
    data_rows = []
    in_data = False
    with open(path, "r", errors="replace") as f:
        for line in f:
            if not in_data:
                # Header part. Pick up component names on the DATE heading line,
                # then transition to the data part.
                if line[:4] == "DATE":
                    # e.g. 'DATE       TIME         DOY     ASBH      ASBD ...'
                    cols = line.split()
                    # cols[0..2] = DATE,TIME,DOY; the rest are component headings.
                    comp = cols[3:]
                    # The last character of each heading is usually the
                    # component symbol (H/D/Z/F/X/Y).
                    if len(comp) >= 4:
                        labels = [c[-1].upper() for c in comp[:4]]
                    in_data = True
                continue
            s = line.strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 7:
                continue
            try:
                data_rows.append(
                    (float(parts[3]), float(parts[4]),
                     float(parts[5]), float(parts[6]))
                )
            except ValueError:
                # Skip non-numeric (unexpected) lines.
                continue

    if labels is None or len(labels) != 4:
        labels = ["H", "D", "Z", "F"]
    if data_rows:
        rdata = np.asarray(data_rows, dtype=np.float64)
    else:
        rdata = np.empty((0, 4), dtype=np.float64)
    return rdata, labels


def gmag_icswse_iaga(
    trange=["2013-01-03", "2013-01-04"],
    site="all",
    resolution="all",
    no_download=False,
    downloadonly=False,
    notplot=False,
    ror=True,
    suffix="",
):
    """Load ICSWSE MAGDAS/CPMN magnetometer (IAGA2002) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        A full day is always read even for a sub-day range.
        Default: ['2013-01-03', '2013-01-04']
    site : str or list of str
        Observatory/station code(s) (3 characters). A space-separated string
        or a list are both accepted. 'all' selects every available site. Valid
        sites: aab asb can ckt drb gsi ica krt lgz mgd onw sbh tir zgn abj asw
        cdo cmd dvs her ilr ktn lkw mlb prp scn twv abu bcl ceb dav eus hln jrs
        kuj lsk mnd ptk sma wad ama bik cgr daw ewa hob jyp lag lwa mut ptn tgg
        yak anc bkl chd des fym hvd kpg laq mcq nab roc tik yap.
        Default: 'all'
    resolution : str or list of str
        Time resolution to load. Valid options: 1sec, 1min, all.
        Default: 'all'
    no_download : bool
        If set, only load data already present in the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
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
        List of tplot variables created (``kyumag_mag_<site>_<resolution>_hdzf``).
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gmag_icswse_iaga(trange=['2013-01-03', '2013-01-04'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_list(site, SITE_CODE_ALL)
    resolutions = _normalize_list(resolution, RESOLUTION_ALL)
    if not sites or not resolutions:
        return {} if notplot else []

    local_data_dir = os.path.join(CONFIG["local_data_dir"], LOCAL_SUBDIR)

    downloaded_files = []
    loaded = {} if notplot else []

    for res in resolutions:
        npts = 86400 if res == "1sec" else 1440
        dt_sec = 1.0 if res == "1sec" else 60.0

        for st in sites:
            pathformat = _pathformat(st, res)
            relpaths = dailynames(file_format=pathformat, trange=trange,
                                  res=24 * 3600.0)

            files = download(
                remote_file=relpaths,
                remote_path=REMOTE_DATA_DIR,
                local_path=local_data_dir,
                no_download=no_download,
                last_version=False,
                headers=_SPEDAS_HEADERS,  # i-SPES serves only to the SPEDAS UA
            )
            local_files = sorted(f for f in (files or []) if os.path.isfile(f))
            downloaded_files += local_files

            if downloadonly:
                continue

            # Read each file and concatenate component values with evenly
            # spaced times.
            time_chunks = []
            data_chunks = []
            for relpath, fpath in zip(relpaths, files or []):
                if not (fpath and os.path.isfile(fpath)):
                    continue
                # basetime: the date in the file name (00:00 UT). Extract the
                # year/month/day from the strftime-expanded relative path.
                ymd = _ymd_from_relpath(relpath)
                if ymd is None:
                    continue
                basetime = time_double(ymd)

                # Only the component values are used; labels are fixed to
                # H,D,Z,F to match the original output.
                rdata, _labels = _read_iaga2002(fpath)
                if rdata.shape[0] == 0:
                    continue

                tarr = basetime + np.arange(npts, dtype=np.float64) * dt_sec
                # If the file row count and the expected point count differ, use
                # the shorter of the two (safer than assuming full length).
                n = min(rdata.shape[0], npts)
                time_chunks.append(tarr[:n])
                data_chunks.append(rdata[:n, :])

            if not data_chunks:
                continue

            timebuf = np.concatenate(time_chunks)
            databuf = np.concatenate(data_chunks, axis=0)

            # Fill value -> NaN.
            databuf[databuf == BAD_VALUE] = np.nan
            # IDL (iug_load_gmag_icswse_iaga) reads the IAGA2002 values with
            # float(), i.e. single precision, so it stores float32. Cast to
            # float32 here to reproduce the exact stored values (otherwise a
            # ~2e-3 float32-quantisation difference remains at ~4e4 nT fields).
            databuf = databuf.astype(np.float32)

            tplot_name = f"kyumag_mag_{st}_{res}_hdzf" + suffix

            if notplot:
                loaded[tplot_name] = {"x": timebuf, "y": databuf}
                continue

            store_data(tplot_name, data={"x": timebuf, "y": databuf})

            # Labels are fixed to H,D,Z,F regardless of the actual components,
            # to match the original output (the variable-name suffix '_hdzf' is
            # likewise fixed).
            options(tplot_name, "legend_names", ["H", "D", "Z", "F"])
            options(tplot_name, "Color", ["b", "g", "r", "k"])
            options(tplot_name, "ytitle",
                    f"KYUMAG {st[:3].upper()} {res.upper()}")
            options(tplot_name, "ysubtitle", "[nT]")
            loaded.append(tplot_name)

    if ror and not downloadonly and not notplot and loaded:
        _print_ror()

    if downloadonly:
        return sorted(set(downloaded_files))
    return loaded


def _ymd_from_relpath(relpath):
    """Extract ``'YYYY-MM-DD'`` from a strftime-expanded relative path.

    Normalizes the path and reads the 8-digit date from the basename.
    Example basename: 'ASB20130103psec.sec' -> '2013-01-03'.
    """
    base = os.path.basename(relpath.replace("\\", "/"))
    # YYYYMMDD follows the 3-character uppercase site code (e.g. 'ASB').
    if len(base) >= 11:
        ymd = base[3:11]
        if ymd.isdigit():
            return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
    return None


def _print_ror():
    """Print the Rules of the Road."""
    print("")
    print("Rules of the Road for MAGDAS/CPMN Data Use:")
    print("")
    print(ACKNOWLEDG_STRING)
    print("")
    print("For more information, see")
    print("http://data.icswse.kyushu-u.ac.jp/")
    print("")
