"""Load function for WDC for Geomagnetism, Kyoto geomagnetic index and observatory data (WDC ASCII).

The WDC fixed-width ASCII records are not CDF, so the shared CDF loader is not
used; files are fetched with pyspedas ``download`` and parsed within this module
before calling ``store_data``.

Supported indices / observatories
---------------------------------
* ``dst``  : Dst index (hourly)
* ``ae``   : AE/AU/AL/AO (+ provisional AX) indices (hourly / min)
* ``sym``  : SYM-H, SYM-D indices (min)
* ``asy``  : ASY-H, ASY-D indices (min)
* ``wp``   : Wp index and the number of stations used (min)
* individual observatories (``kak`` ``mmb`` etc., see :data:`VSNAMES_ALL`):
  H/D/Z/X/Y/F/I hourly / min values

Data format notes
-----------------
WDC hourly record (Dst / AE-hour / observatory-hour)
  ``http://wdc.kugi.kyoto-u.ac.jp/hyplt/format/wdchrformat.html``
  Fixed width (0-based): name=[0:3], yy=[3:5], mm=[5:7], element=[7],
  dd=[8:10], version=[13] (Dst only century=[14:16]), basevalue=[16:20],
  24 hourly values = 4 chars each starting at offset 20.
  Value: ``var/600 + base`` for D/I, otherwise ``var + base*100``. Missing
  ``9999`` -> NaN. The base time of each day is 00:30 (data_resolution/2 = 1800 s).

WDC 1-min record (observatory-min / AE-min / SYM / ASY)
  ``http://wdc.kugi.kyoto-u.ac.jp/mdplt/format/wdcformat.html``
  Fixed width: yy=[12:14], mm=[14:16], dd=[16:18], element=[18], hour=[19:21],
  name=[21:24] (AE is detected by the leading 8 chars ``AEALAOAU``),
  60 minute values = 6 chars each starting at offset 34.
  Value: ``var`` as-is for SYM/ASY, ``var/600`` for D/I, otherwise ``var``
  (base 0). Missing ``99999`` -> NaN. The base time of each hour is +30 s.

The time grid is generated from the minimum to maximum observed base time at the
``data_resolution`` cadence; missing rows are filled with NaN.
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, dailynames, download

from iugonet.config import CONFIG

# IUGONET mirror
REMOTE_DATA_DIR = "http://wdc-data.iugonet.org/data/"
LOCAL_SUBDIR = "wdc_kyoto/geomag/"

# Wp index (Nose et al.). Moved 2026 from ISEE Nagoya University
# (www.isee.nagoya-u.ac.jp/~nose.masahito) to Nagoya City University.
WP_REMOTE_DATA_DIR = "https://www.ds.nagoya-cu.ac.jp/~nose/s-cubed/data/"
WP_LOCAL_SUBDIR = "geom_indices/kyoto/Wp/"

# missing flags
MISSING_HOUR = 9999     # hourly records
MISSING_MIN = 99999     # 1-min records
MISSING_WP = 999.000    # Wp index


# ---------------------------------------------------------------------------
# valid site names
# ---------------------------------------------------------------------------
_VSNAMES_STR = (
    "dst ae sym asy wp "
    "ABB AAA AAE ABG ABK ABN ACR ADA AED AGN AHM AIA AIF ALE ALH ALM ALU AMD "
    "AML AMN AMS AMT AMU ANC ANK ANN ANO APA API AQU ARC ARE ARK ARS ASC ASH "
    "ASK ASO ASP AVE AVI AWS AWY BAG BAL BBG BDE BDV BEL BEY BFE BFO BGA BGY "
    "BIN BJI BJN BKC BKK BLC BLT BMT BNA BNG BOC BOD BOP BOU BOX BRD BRS BRT "
    "BRW BSL BTI BTV BUZ BYR CAI CAO CAT CAX CBB CBI CCL CCP CCS CDN CDP CDS "
    "CEV CFI CHR CHT CKA CLA CLB CLF CLH CLI CLL CMB CMO CNB CNH COI COP CPA "
    "CPI CPS CPY CRC CSR CSS CSY CTA CTO CTX CUS CWE CZA CZT DAL DAR DAV DBN "
    "DIK DLN DLR DLT DOB DOU DRS DRV DUR DVS EAA EBR EGS EIC EKP ELI ELT ENB "
    "ENK EPN ESA ESK ETT EUA EUS EYR FAN FCC FCP FMM FRA FRD FRL FRN FSM FSP "
    "FSV FTN FUQ FUR FYU GCK GDH GEL GEN GIB GIM GIR GIT GJO GLM GLN GNA GRM "
    "GRW GTT GUA GUI GVD GWC GZH HAD HAN HBA HBK HBT HCR HEA HER HII HIS HKC "
    "HLL HLP HLS HLW HNA HON HRB HRI HRN HTY HUA HUS HVN HYB IBD INK IQA IRT "
    "ISC ISK ISL IVA IVI IZN JAI JOP JRV JUL KAK KAM KAR KDU KEM KGD KHB KHS "
    "KIR KIV KND KNG KNT KNY KNZ KOD KOR KOT KOU KRC KSA KSH KTG KTS KUM KUY "
    "KWJ KZA KZN LAA LAS LAU LDV LED LER LGR LIV LMD LMM LNN LNP LOB LOC LOV "
    "LOZ LPB LQA LRM LRV LSA LUA LUC LUK LVV LWI LYC LYN LZH LZV MAB MAN MAW "
    "MBC MBO MCL MCM MCP MCQ MDS MEA MEL MEV MFP MGD MGS MID MIR MIZ MJR MKL "
    "MLT MMB MMH MMK MNH MNK MNN MOG MOL MOS MRI MRN MUB MUT MWC MZL NAI NAL "
    "NAQ NCK NDA NEW NGK NGP NHO NKK NMP NMT NOK NOW NPF NPG NPH NPJ NPL NPM "
    "NRD NRW NSM NTS NUR NVL NVS NWP NWS NYI OAS ODE OKN ONW ORC OTT OUJ PAB "
    "PAF PAG PAI PBK PBQ PCU PEB PEG PET PHU PIL PIO PIU PLS PMG PND PNN POD "
    "POK POL POT PPT PRU PSM PST PTS PTU QGZ QIX QSB QUE QZH RAC RBD RDJ RES "
    "RIT ROB ROD RPC RSV RYB SAB SAH SAS SBA SCO SDH SED SEO SEY SFS SGG SHB "
    "SHL SHT SHU SIL SIM SIT SJG SKT SLU SMG SNA SNK SOD SOG SOR SOU SPA SPB "
    "SPL SPT SRE SRO SSH SSO STF STJ STO SUA SUB SVD SWI SYO SZT TAL TAM TAN "
    "TEH TEO TEV TFS THJ THL THU THY TIK TIP TIR TJO TKH TKT TLK TMB TMK TMP "
    "TNB TND TNG TOK TOL TOO TPA TRD TRO TRW TST TSU TTB TUC TUL TUM TUN UBA "
    "UGT UJJ UKH UMA UPS URC VAL VIC VLA VLJ VNA VOS VQS VSK VSS WAT WES WHN "
    "WHS WIA WIK WIL WIT WKE WLH WMQ WNG WNP WRH YAK YAU YCB YKC YSH YSS ZAR "
    "ZKW ZUY"
)
VSNAMES_ALL = _VSNAMES_STR.lower().split()
# default sites when site is unspecified
DEFAULT_SITES = ["kak", "asy", "sym", "ae", "dst", "wp"]

# sites treated as indices (vs. individual observatories)
INDEX_SITES = {"dst", "ae", "sym", "asy", "wp"}


def _check_valid_name(site, valid):
    """Normalize the input (str/list, 'all' accepted) to lowercase codes within valid.

    Preserves the input order and removes duplicates and invalid codes.
    """
    if isinstance(site, str):
        items = site.lower().split()
    else:
        items = [str(s).lower() for s in site]
    if "all" in items:
        return list(valid)
    out = []
    vset = set(valid)
    for it in items:
        if it in vset and it not in out:
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# remote relative path generation
# ---------------------------------------------------------------------------
def _relpaths(sname, res, level, trange):
    """Return the list of WDC remote relative paths for sname/res/level.

    Uses ``dirformat='%Y/'`` and ``fileformat='%y%m'`` by default, switching to a
    per-day path only for AE realtime.

    Returns
    -------
    list[str]
        e.g. ``['hour/index/dst/2007/dst0701']``.
    """
    s = sname.lower()
    if not level:
        level = "all"

    # collect (dir, prefix, suffix) specs
    specs = []  # list of (dir, prefix, suffix)
    dirformat = "%Y/"
    fileformat = "%y%m"

    if s == "dst":
        if level == "all" or level == "final":
            specs.append((res + "/index/dst/", s, ""))
        if level == "all" or level[0:4] == "prov":
            specs.append((res + "/index/pvdst/", s, ""))

    elif s == "ae":
        if level == "all" or level == "final":
            for d, p in zip(["ae", "au", "al", "ao"],
                            ["ae.", "au.", "al.", "ao."]):
                specs.append((res + "/index/" + d + "/", p, ""))
        if level == "all" or level[0:4] == "prov":
            if res == "min":
                # before 1996
                for d, p in zip(["a.e", "a.u", "a.l", "a.o"],
                                ["ae", "au", "al", "ao"]):
                    specs.append((res + "/index/" + d + "/", p, ""))
                # after 1995
                for p in ["ae", "au", "al", "ao", "ax"]:
                    specs.append((res + "/index/pvae/", p, ""))
        if level == "all" or level[0:4] == "real":
            if res == "min":
                for p in ["ae", "au", "al", "ao"]:
                    specs.append((res + "/index/rtae/", p, ""))
                dirformat = "%Y/%m/%d/"
                fileformat = "%y%m%d"

    elif s == "sym" or s == "asy":
        specs.append((res + "/index/asy/", "asy", ".wdc"))

    else:  # individual stations
        suf = ".wdc" if res == "min" else ""
        specs.append((res + "/" + s + "/", s, suf))

    relpaths = []
    for d, prefix, suffix in specs:
        # dailynames takes a single file_format, so dir + dirformat + prefix +
        # fileformat + suffix are combined into one strftime format
        # (e.g. 'hour/index/dst/%Y/dst%y%m').
        fmt = d + dirformat + prefix + fileformat + suffix
        names = dailynames(trange=trange, file_format=fmt)
        relpaths.extend(names)
    # unique, preserving order
    seen = set()
    uniq = []
    for r in relpaths:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def _relpath_to_year(relpath, sname):
    """Extract the year (4-digit str) from a data path string.

    For index types (dst/ae/sym/asy) it is the YYYY in ``.../index/<obs>/<YYYY>/...``;
    for observatories it is the YYYY in ``.../<sname>/<YYYY>/...``.
    """
    s = sname.lower()
    segm = relpath.replace("\\", "/").split("/")
    if s in ("sym", "asy", "ae", "dst"):
        for i, seg in enumerate(segm):
            if seg == "index" and i + 2 < len(segm):
                return segm[i + 2]
    else:
        for i, seg in enumerate(segm):
            if seg == s and i + 1 < len(segm):
                return segm[i + 1]
    return "0"


def _download_files(relpaths, no_download):
    """Download each relpath one by one and return the local paths that exist.

    ``last_version=False`` for ASCII files. A 404 makes download return an empty list.
    """
    local_dir = os.path.join(CONFIG["local_data_dir"], LOCAL_SUBDIR)
    out = []
    for rf in relpaths:
        lf = rf.replace("/", os.sep)
        files = download(remote_file=rf, local_file=lf,
                         remote_path=REMOTE_DATA_DIR, local_path=local_dir,
                         last_version=False, no_download=no_download)
        for f in (files or []):
            if f and os.path.isfile(f):
                out.append(f)
    return out


def _is_data_line_hour(line, sname, relpath):
    """Decide whether one hourly record line is a data line for the site; return the year.

    Returns (ok, year_str).
    """
    name = line[0:3]
    if name != sname.upper():
        return False, None
    year_lower = line[3:5]
    if sname.lower() == "dst":
        year = line[14:16] + year_lower  # century + yy
    else:
        year = _relpath_to_year(relpath, sname)
        try:
            if int(year[2:4]) != int(year_lower):
                return False, None
        except ValueError:
            return False, None
    return True, year


# ---------------------------------------------------------------------------
# hourly parser
# ---------------------------------------------------------------------------
def _parse_hour(local_files, relpaths, sname):
    """Parse the hourly records and return (timebuf, databuf, elemlist).

    Two-pass logic:
      pass 1: scan all lines to determine basetime_start/end and elemlist.
      pass 2: store the values into databuf[idx, elemnum].
    data_resolution=3600 s, base 00:30 of each day.

    Returns
    -------
    (timebuf, databuf, elemlist) or (None, None, None) if no data.
        timebuf : ndarray (nt,) unix seconds
        databuf : ndarray (nt, n_elem) float
        elemlist: list[str] element symbols in order of appearance
    """
    data_resolution = 3600.0
    basetime_resolution = 86400.0

    # match local_files to relpaths by basename
    def relpath_for(file):
        base = os.path.basename(file)
        for r in relpaths:
            if os.path.basename(r) == base:
                return r
        return relpaths[0] if relpaths else ""

    # ---- pass 1: scan ----
    elemlist = []
    basetime_start = None
    basetime_end = None

    parsed = []  # cache (basetime, element, line, year) for pass2
    for file in local_files:
        relpath = relpath_for(file)
        with open(file, "r", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                ok, year = _is_data_line_hour(line, sname, relpath)
                if not ok:
                    continue
                month = line[5:7]
                day = line[8:10]
                basetime = time_double(
                    "%s-%s-%s" % (year, month, day)) + data_resolution / 2
                element = line[7:8]
                if basetime_start is None or basetime < basetime_start:
                    basetime_start = basetime
                if basetime_end is None or basetime_end < basetime:
                    basetime_end = basetime
                if element not in elemlist:
                    elemlist.append(element)
                parsed.append((basetime, element, line))

    if not elemlist or basetime_start is None or basetime_end is None:
        return None, None, None

    buf_size = int(round(
        (basetime_end - basetime_start + basetime_resolution)
        / data_resolution))
    if buf_size <= 0:
        return None, None, None
    timebuf = basetime_start + np.arange(buf_size) * data_resolution
    databuf = np.full((buf_size, len(elemlist)), np.nan, dtype=np.float64)

    # ---- pass 2: fill ----
    for basetime, element, line in parsed:
        elemnum = elemlist.index(element)
        basevalue_str = line[16:20]
        if len(basevalue_str.strip()) == 0:
            basevalue = 0
        else:
            basevalue = int(basevalue_str)
        # 24 hourly values, 4 chars each, offset 20
        variations = np.array(
            [_int_or_missing(line[20 + k * 4: 24 + k * 4], MISSING_HOUR)
             for k in range(24)], dtype=np.float64)
        if element in ("D", "I"):
            value = variations / 600.0 + float(basevalue)
        else:
            value = variations + float(basevalue * 100)
        # missing: variations == 9999 -> NaN
        value[variations == MISSING_HOUR] = np.nan
        # the 24-element value array is laid out into 24 consecutive slots
        # (the 24 hours of that day) starting at idx
        idx = int((basetime - basetime_start) / data_resolution)
        if idx < 0 or idx > buf_size:
            continue
        end = min(idx + value.size, buf_size)
        if end > idx:
            databuf[idx:end, elemnum] = value[:end - idx]

    return timebuf, databuf, elemlist


# ---------------------------------------------------------------------------
# 1-min parser
# ---------------------------------------------------------------------------
def _parse_min(local_files, relpaths, sname):
    """Parse the 1-min records and return (timebuf, databuf, elemlist).

    Same two-pass logic with data_resolution=60 s and base +30 s of each hour.
    SYM/ASY use the value as-is, D/I use var/600, others use var.

    Returns as above.
    """
    data_resolution = 60.0
    basetime_resolution = 3600.0
    s = sname.lower()

    def relpath_for(file):
        base = os.path.basename(file)
        for r in relpaths:
            if os.path.basename(r) == base:
                return r
        return relpaths[0] if relpaths else ""

    def is_data_line(line, relpath):
        if s == "ae":
            if line[0:8] != "AEALAOAU":
                return False, None
        else:
            if line[21:24] != sname.upper():
                return False, None
        year = _relpath_to_year(relpath, sname)
        year_lower = line[12:14]
        try:
            if int(year[2:4]) != int(year_lower):
                return False, None
        except ValueError:
            return False, None
        return True, year

    # ---- pass 1 ----
    elemlist = []
    basetime_start = None
    basetime_end = None
    parsed = []
    for file in local_files:
        relpath = relpath_for(file)
        with open(file, "r", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                ok, year = is_data_line(line, relpath)
                if not ok:
                    continue
                month = line[14:16]
                day = line[16:18]
                hour = line[19:21]
                element = line[18:19]
                basetime = (time_double("%s-%s-%s" % (year, month, day))
                            + int(hour) * basetime_resolution
                            + data_resolution / 2)
                if basetime_start is None or basetime < basetime_start:
                    basetime_start = basetime
                if basetime_end is None or basetime_end < basetime:
                    basetime_end = basetime
                if element not in elemlist:
                    elemlist.append(element)
                parsed.append((basetime, element, line))

    if not elemlist or basetime_start is None or basetime_end is None:
        return None, None, None

    buf_size = int(round(
        (basetime_end - basetime_start + basetime_resolution)
        / data_resolution))
    if buf_size <= 0:
        return None, None, None
    timebuf = basetime_start + np.arange(buf_size) * data_resolution
    databuf = np.full((buf_size, len(elemlist)), np.nan, dtype=np.float64)

    # ---- pass 2 ----
    for basetime, element, line in parsed:
        elemnum = elemlist.index(element)
        # 60 values, 6 chars each, offset 34
        variations = np.array(
            [_int_or_missing(line[34 + k * 6: 40 + k * 6], MISSING_MIN)
             for k in range(60)], dtype=np.float64)
        if s in ("sym", "asy"):
            value = variations.copy()
        elif element in ("D", "I"):
            value = variations / 600.0
        else:
            value = variations.copy()
        value[variations == MISSING_MIN] = np.nan
        # the 60-element value array is laid out into 60 consecutive slots
        # (the 60 minutes of that hour) starting at idx
        idx = int((basetime - basetime_start) / data_resolution)
        if idx < 0 or idx > buf_size:
            continue
        end = min(idx + value.size, buf_size)
        if end > idx:
            databuf[idx:end, elemnum] = value[:end - idx]

    return timebuf, databuf, elemlist


def _int_or_missing(field, missing):
    """Convert a fixed-width field to int; treat a blank field as the missing value.

    WDC fill is given explicitly as 9999/99999, so missing is returned only when
    the field cannot be parsed (blank/non-numeric); it is mapped to NaN later.
    """
    t = field.strip()
    if t == "" or t == "-":
        return missing
    try:
        return int(t)
    except ValueError:
        try:
            return int(float(t))
        except ValueError:
            return missing


# ---------------------------------------------------------------------------
# tplot var name / options
# ---------------------------------------------------------------------------
# element symbol -> matplotlib color
_COLOR_MAP = {
    "H": "b", "D": "g", "Z": "r", "X": "c", "Y": "y", "F": "k", "I": "m",
    "U": "b", "L": "g", "E": "r", "O": "k",
}


def _make_var_meta(sname, element, res, level):
    """Return (tplot_name, ytitle, ysubtitle, labels).

    element is the list of component symbols in order of appearance.
    """
    s = sname.lower()
    n = len(element)
    if s == "dst":
        if level and level[:4].lower() == "prov":
            name = "wdc_mag_dst_prov"
            ytitle = "Prov. Dst"
        else:
            name = "wdc_mag_dst"
            ytitle = "Dst"
        return name, ytitle, "[nT]", ["Dst"]

    if s in ("sym", "asy"):
        if n == 1:
            name = "wdc_mag_" + (s + "-" + element[0]).lower()
            ytitle = (s + "-" + element[0]).upper()
            labels = [(s + "-" + element[0]).upper()]
        else:
            name = "wdc_mag_" + s
            ytitle = s.upper()
            labels = [(s + "-" + e).upper() for e in element]
        return name, ytitle, "[nT]", labels

    if s == "ae":
        if not res:
            res = "min"
        if n == 1:
            e = element[0]
            name = "wdc_mag_a" + e.lower()
            ytitle = "A" + e.upper()
            ysub = "[#]" if e.upper() == "X" else "[nT]"
            labels = ["A" + e.upper()]
        else:
            name = "wdc_mag_ae"
            ytitle = "AE"
            ysub = "[nT]"
            labels = ["A" + e.upper() for e in element]
        if level and level[:4].lower() == "prov":
            name += "_prov"
            ytitle = "Prov. " + ytitle
        elif level and level[:4].lower() == "real":
            name += "_real"
            ytitle = "Realtime " + ytitle
        if res == "min":
            name += "_1min"
            ytitle += "\n(1-min)"
        elif res in ("hour", "hr"):
            name += "_1hr"
            ytitle += "\n(hourly)"
        return name, ytitle, ysub, labels

    # individual stations
    name = "wdc_mag_" + s
    ytitle = s.upper()
    ysub = "[nT]"
    if n == 1:
        e = element[0]
        name += "_" + e.lower()
        ytitle += " " + e.upper()
        ysub = "[deg]" if e.upper() in ("D", "I") else "[nT]"
    if level and level[:4].lower() == "prov":
        name += "_prov"
        ytitle += " Prov."
    elif level and (level[:2].lower() == "ql" or level.lower() == "quicklook"):
        name += "_ql"
        ytitle += " QL"
    if res == "min":
        name += "_1min"
        ytitle += "\n(1-min)"
    elif res in ("hour", "hr"):
        name += "_1hr"
        ytitle += "\n(hourly)"
    labels = []
    for e in element:
        if e in ("D", "I"):
            labels.append(e + " [deg]")
        else:
            labels.append(e + " [nT]")
    return name, ytitle, ysub, labels


def _store(name, timebuf, databuf, elemlist, ytitle, ysubtitle, labels,
           notplot, loaded, suffix):
    """Store databuf as a tplot variable and set its options.

    databuf is stored as 1-D for a single component, or (nt, n_elem) for
    multiple components.
    """
    if databuf.shape[1] == 1:
        y = databuf[:, 0]
    else:
        y = databuf
    vname = name + suffix
    if notplot:
        loaded[vname] = {"x": timebuf, "y": y}
        return vname
    store_data(vname, data={"x": timebuf, "y": y})
    options(vname, "ytitle", ytitle)
    options(vname, "ysubtitle", ysubtitle)
    if labels:
        options(vname, "legend_names", labels)
    colors = [_COLOR_MAP.get(e, "k") for e in elemlist]
    if colors:
        options(vname, "Color", colors)
    loaded.append(vname)
    return vname


# ---------------------------------------------------------------------------
# Wp index
# ---------------------------------------------------------------------------
def _load_wp(trange, no_download, downloadonly, notplot, loaded, suffix,
             downloaded):
    """Load the Wp index and the number of stations used.

    The remote path is ``YYYYMM/YYYYMMDD.H`` (ISEE, Nagoya). Each day has 1440
    rows (1-min); column 2 (0-based) is Wp and column 14 is the station count.
    Missing 999.000 -> NaN.
    """
    local_dir = os.path.join(CONFIG["local_data_dir"], WP_LOCAL_SUBDIR)
    relpaths = dailynames(file_format="%Y%m/%Y%m%d.H", trange=trange)

    timebuf = []
    databuf = []  # list of (wp, nstn)
    for rf in relpaths:
        files = download(remote_file=rf, remote_path=WP_REMOTE_DATA_DIR,
                         local_path=local_dir, last_version=False,
                         no_download=no_download)
        local_files = [f for f in (files or []) if f and os.path.isfile(f)]
        downloaded.extend(local_files)
        if downloadonly:
            continue
        for f in local_files:
            base = os.path.basename(rf)            # YYYYMMDD.H
            year = base[0:4]
            month = base[4:6]
            day = base[6:8]
            basetime = time_double("%s-%s-%s" % (year, month, day))
            # skip the 2-line header; columns 2 and 14
            rows = np.genfromtxt(f, skip_header=2)
            if rows.ndim == 1:
                rows = rows.reshape(1, -1)
            if rows.shape[0] == 0:
                continue
            wp = rows[:, 2]
            nstn = rows[:, 14]
            n = rows.shape[0]
            t = basetime + np.arange(n) * 60.0
            timebuf.append(t)
            databuf.append(np.column_stack([wp, nstn]))

    if downloadonly:
        return
    if not databuf:
        return
    timebuf = np.concatenate(timebuf)
    databuf = np.concatenate(databuf, axis=0)
    # missing 999.000 -> NaN
    databuf[databuf == MISSING_WP] = np.nan

    name1 = "wdc_mag_Wp_index" + suffix
    name2 = "wdc_mag_Wp_nstn" + suffix
    if notplot:
        loaded[name1] = {"x": timebuf, "y": databuf[:, 0]}
        loaded[name2] = {"x": timebuf, "y": databuf[:, 1]}
        return
    store_data(name1, data={"x": timebuf, "y": databuf[:, 0]})
    options(name1, "ytitle", "WDC_Wp")
    options(name1, "ysubtitle", "[nT]")
    options(name1, "legend_names", ["Wp"])
    loaded.append(name1)
    store_data(name2, data={"x": timebuf, "y": databuf[:, 1]})
    options(name2, "ytitle", "WDC_Wp_nstn")
    options(name2, "ysubtitle", "")
    options(name2, "legend_names", ["Wp_nstn"])
    loaded.append(name2)


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def gmag_wdc(
    trange=["2007-01-22", "2007-01-23"],
    site="kak asy sym ae dst wp",
    resolution=None,
    level=None,
    no_download=False,
    downloadonly=False,
    notplot=False,
    suffix="",
):
    """Load WDC Kyoto geomagnetic index and observatory data (WDC ASCII).

    For each site the hourly/min resolution and the default level are chosen,
    and the data are read with the matching parser to build tplot variables.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Even for less than a
        month, the whole month is read (WDC files are monthly).
        Default: ['2007-01-22', '2007-01-23']
    site : str or list of str
        Observatory ABB code(s) or index name(s). A space-separated string or a
        list are both accepted. 'all' selects every available site. Indices: dst
        ae sym asy wp. Observatories: e.g. kak mmb (see :data:`VSNAMES_ALL`).
        Default: 'kak asy sym ae dst wp'
    resolution : str or None
        'min' / 'hour' ('hr' accepted). If unspecified the default is 'min', but
        sym/asy/wp are forced to min and dst is forced to hour.
        Default: None
    level : str or None
        'final' / 'provisional' / 'real'. If unspecified, dst/ae try
        ['final', 'provisional', 'real'] in order and the others use 'final'.
        Default: None
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
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created (e.g. ``wdc_mag_dst``,
        ``wdc_mag_ae_prov_1min``, ``wdc_mag_sym``, ``wdc_mag_kak_1hr``). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gmag_wdc(trange=['2007-01-22', '2007-01-23'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _check_valid_name(site, VSNAMES_ALL)
    if not sites:
        return {} if notplot else []

    loaded = {} if notplot else []
    downloaded = []

    for s in sites:
        sl = s.lower()

        # ---- default level ----
        if not level:
            if sl in ("dst", "ae"):
                levels = ["final", "provisional", "real"]
            else:
                levels = ["final"]
        else:
            levels = [level]

        # ---- default/forced resolution ----
        if not resolution:
            res = "min"
        else:
            res = resolution
        if sl in ("sym", "asy", "wp"):
            res = "min"
        elif sl == "dst":
            res = "hour"

        # ---- Wp uses a dedicated parser ----
        if sl == "wp":
            _load_wp(trange, no_download, downloadonly, notplot, loaded,
                     suffix, downloaded)
            continue

        for lv in levels:
            relpaths = _relpaths(sl, "hour" if res in ("hour", "hr") else "min",
                                 lv, trange)
            if not relpaths:
                continue
            local_files = _download_files(relpaths, no_download)
            downloaded.extend(local_files)
            if downloadonly:
                continue
            if not local_files:
                continue

            if res in ("hour", "hr"):
                timebuf, databuf, elemlist = _parse_hour(
                    local_files, relpaths, sl)
            else:
                timebuf, databuf, elemlist = _parse_min(
                    local_files, relpaths, sl)
            if timebuf is None:
                continue

            name, ytitle, ysub, labels = _make_var_meta(
                sl, elemlist, "hour" if res in ("hour", "hr") else "min", lv)
            _store(name, timebuf, databuf, elemlist, ytitle, ysub, labels,
                   notplot, loaded, suffix)

    if downloadonly:
        # unique, preserving order
        seen = set()
        out = []
        for f in downloaded:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out
    return loaded


def gmag_wdc_wp_index(trange=["2007-01-22", "2007-01-23"], no_download=False,
                      downloadonly=False, notplot=False, suffix=""):
    """Load the Wp index on its own.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'].
        Default: ['2007-01-22', '2007-01-23']
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
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created (``wdc_mag_Wp_index``,
        ``wdc_mag_Wp_nstn``). Empty list if no data were loaded. If
        ``downloadonly`` is set, the list of downloaded file paths is returned;
        if ``notplot`` is set, a dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gmag_wdc_wp_index(trange=['2007-01-22', '2007-01-23'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    loaded = {} if notplot else []
    downloaded = []
    _load_wp(trange, no_download, downloadonly, notplot, loaded, suffix,
             downloaded)
    if downloadonly:
        return downloaded
    return loaded


def gmag_wdc_qddays(trange=["2007-01-01", "2007-12-31"],
                    no_download=False, downloadonly=False):
    """Return the list of WDC Kyoto international quiet (5/10) and disturbed days.

    Reads the yearly files ``day/qddays/qdYYYY`` and extracts, from each line,
    year, month, the 5 quietest days (qd1) and the next 5 quietest days (qd2).

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'].
        Default: ['2007-01-01', '2007-12-31']
    no_download : bool
        If set, only load data already present in the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not parse them.
        Default: False

    Returns
    -------
    ndarray
        Int array of shape (n, 12); each row is
        [year, month, q1..q5, q6..q10]. If ``downloadonly`` is set, the list of
        local file paths is returned instead.

    Notes
    -----
    The international Q-Days/D-Days are derived from Kp by GFZ Potsdam.
    ref: http://wdc.kugi.kyoto-u.ac.jp/qddays/index.html

    Examples
    --------
    >>> import iugonet
    >>> qd = iugonet.gmag_wdc_qddays(trange=['2007-01-01', '2007-12-31'])
    """
    import numpy as np
    from pyspedas import time_double, time_string
    y0 = int(time_string(time_double(trange[0]))[:4])
    y1 = int(time_string(time_double(trange[1]))[:4])
    relpaths = ["day/qddays/qd%04d" % y for y in range(y0, y1 + 1)]
    files = _download_files(relpaths, no_download)
    if downloadonly:
        return files

    buf = []
    for f in sorted(set(files)):
        with open(f, errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    year = int(line[0:4])
                    month = int(line[5:7])
                    # qd1 = 5 fields of 2 chars from offset 8; qd2 = from offset 19
                    qd1 = [int(line[8 + i * 2:10 + i * 2]) for i in range(5)]
                    qd2 = [int(line[19 + i * 2:21 + i * 2]) for i in range(5)]
                except ValueError:
                    continue
                buf.append([year, month] + qd1 + qd2)
    return np.array(buf, dtype=int)
