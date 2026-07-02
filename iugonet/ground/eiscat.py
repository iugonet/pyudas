"""Load function for NIPR EISCAT radar data.

The EISCAT CDF files use a compression format that cdflib does not support, so
pyspedas' ``cdf_to_tplot`` cannot read them. Here they are read with
``spacepy.pycdf`` (the NASA CDF library) instead.
"""
import numpy as np
import spacepy.pycdf as pycdf

from pyspedas import store_data, options, time_double
from pyspedas import time_clip as tclip

from iugonet.load import load

SITE_CODE_ALL = ["esr_32m", "esr_42m", "tro_vhf", "tro_uhf", "kir_uhf", "sod_uhf"]
YDATATYPE_ALL = ["alt", "lat", "long"]
REMOTE_DATA_DIR = "http://pc115.seg20.nipr.ac.jp/www/eiscatdata/cdf/basic/"

# paramstr rename table
PARAM_RENAME = {
    "pulse_code_id": "pulse", "int_time_nominal": "inttim", "ne_err": "neerr",
    "te_err": "teerr", "ti_err": "tierr", "vi_err": "vierr", "composition": "comp",
    "quality": "q", "quality_flag": "qflag", "collision_freq": "colf",
    "int_time_real": "inttimr", "elev_angle": "elev", "number_gate": "ngate",
    "txpower": "txpow", "mconst": "mcnst", "heating": "heat",
}
# params that get a v (y axis) and are displayed as spectrograms (spec=1)
SPEC_PARAMS = {"lat", "long", "alt", "range", "ne", "ne_err", "te", "te_err",
               "ti", "ti_err", "vi", "vi_err", "collision_freq", "composition",
               "quality", "quality_flag"}

# Axis labels set per param to match the original UDAS output.
# key = paramstr of the tplot variable name (after PARAM_RENAME),
# value = (ytitle label, ysubtitle, ztitle). ytitle is "{site}!C{label}".
# The original labels are reproduced verbatim (including the typo "Rnage" and
# superscripts like !E-3!N) to match the original UDAS output.
_AXIS_LABELS = {
    "pulse":  ("Pulse code ID", None, None),
    "inttim": ("Int. time", "[s]", None),
    "lat":    ("Latitude", "Altitude [km]", "Latitude [deg]"),
    "long":   ("Longitude", "Altitude [km]", "Longitude [deg]"),
    "alt":    ("Altitude", "Altitude [km]", "Altitude [km]"),
    "range":  ("Rnage", "Altitude [km]", "Range [km]"),
    "ne":     ("Ne", "Altitude [km]", "Ne [m!E-3!N]"),
    "neerr":  ("Ne err.", "Altitude [km]", "Ne err. [m!E-3!N]"),
    "te":     ("Te", "Altitude [km]", "Te [K]"),
    "teerr":  ("Te err.", "Altitude [km]", "Te err. [K]"),
    "ti":     ("Ti", "Altitude [km]", "Ti [K]"),
    "tierr":  ("Ti err.", "Altitude [km]", "Ti err. [K]"),
    "vi":     ("Vi", "Altitude [km]", "Vi [m/s]"),
    "vierr":  ("Vi err.", "Altitude [km]", "Vi err. [m/s]"),
    "colf":   ("Col.freq.", "Altitude [km]", "Col.freq. [s!E-1!N]"),
    "comp":   ("Composition", "Altitude [km]", "Composition [%]"),
    "q":      ("Quality", None, "Quality"),
    "qflag":  ("Quality flag", None, "Quality flag"),
}


def _normalize_sites(site):
    if isinstance(site, str):
        items = site.lower().split()
    else:
        items = [str(s).lower() for s in site]
    if "all" in items:
        return list(SITE_CODE_ALL)
    return [it for it in items if it in SITE_CODE_ALL]


def _download_eiscat(stn, ant, trange, no_update):
    """Download the EISCAT CDF files.

    The EISCAT CDF files use compression that cdflib does not support, so the
    download CDF verification would treat them as corrupt and delete them.
    Passing ``verify_cdf=False`` replaces that check with a plain existence
    check to avoid this.
    """
    pathformat = f"{stn}/{ant}/%Y/eiscat_kn_{stn}_{ant}_%Y%m%d_v??.cdf"
    return load(
        trange=trange,
        pathformat=pathformat,
        file_res=24 * 3600.0,
        remote_path=REMOTE_DATA_DIR,
        local_path="nipr/eiscat/",
        downloadonly=True,
        no_update=no_update,
        verify_cdf=False,
    )


def _epoch_to_unix(epoch_arr):
    """Convert a spacepy datetime array to unix seconds, via time_double to match spedas."""
    return np.array([time_double(e.strftime("%Y-%m-%d %H:%M:%S.%f"))
                     for e in epoch_arr])


def eiscat(
    trange=["2010-01-18", "2010-01-19"],
    site="all",
    ydatatype="alt",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load EISCAT radar ionospheric data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2010-01-18', '2010-01-19']
    site : str or list of str
        Observatory_antenna code(s). A space-separated string or a list are both
        accepted. 'all' selects every available site. Valid sites:
        esr_32m esr_42m tro_vhf tro_uhf kir_uhf sod_uhf.
        Default: 'all'
    ydatatype : str
        Physical quantity used for the y axis. Valid options: 'alt' / 'lat' / 'long'.
        Default: 'alt'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    get_support_data : bool
        Data with an attribute "VAR_TYPE" with a value of "support_data" will
        be loaded into tplot.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    version : str or None
        If set, load a specific data file version instead of the latest.
        Default: None
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
        List of tplot variables created (``eiscat_{stn}{ant}_{paramstr}``).
        Physical quantities (ne/te/ti/vi etc.) are 2D spectrograms
        (time x alt, spec=1). Empty list if no data were loaded. If
        ``downloadonly`` is set, the list of downloaded file paths is returned.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.eiscat(trange=['2010-01-18', '2010-01-19'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        return []

    ytype = ydatatype.lower()
    if ytype == "lon":
        ytype = "long"
    if ytype not in YDATATYPE_ALL:
        ytype = "alt"

    loaded = []
    for st in sites:
        stn, ant = st.split("_")
        files = _download_eiscat(stn, ant, trange, no_update)
        if downloadonly:
            loaded += files
            continue

        for f in files:
            with pycdf.CDF(f) as cdf:
                t = _epoch_to_unix(cdf["Epoch_0"][...])
                yvar = ytype + "_0"
                vdat = np.array(cdf[yvar][...], dtype=float) if yvar in cdf else None

                for var in [v for v in cdf.keys()
                            if v.endswith("_0") and v != "Epoch_0"]:
                    # with get_support_data=False, skip support_data variables
                    vtype = str(cdf[var].attrs.get("VAR_TYPE", "data"))
                    if not get_support_data and vtype != "data":
                        continue
                    param = var[:-2]
                    y = np.array(cdf[var][...], dtype=float)
                    if y.shape[0] != len(t):
                        continue  # skip NRV (rgate_no etc.) that does not match the time dimension
                    paramstr = PARAM_RENAME.get(param, param)
                    new = f"eiscat_{stn}{ant}_{paramstr}" + suffix

                    if param in SPEC_PARAMS and vdat is not None and y.ndim == 2:
                        store_data(new, data={"x": t, "y": y, "v": vdat})
                        options(new, "spec", 1)
                    else:
                        store_data(new, data={"x": t, "y": y})

                    # axis labels (ytitle="{site}!C{label}")
                    lab = _AXIS_LABELS.get(paramstr)
                    if lab is not None:
                        yt, ys, zt = lab
                        options(new, "ytitle", st + "!C" + yt)
                        if ys is not None:
                            options(new, "ysubtitle", ys)
                        if zt is not None:
                            options(new, "ztitle", zt)

                    if time_clip:
                        tclip(new, trange[0], trange[1], suffix="")
                    loaded.append(new)

    return loaded
