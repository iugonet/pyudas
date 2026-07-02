"""Load function for Tohoku University LF-band radio phase/amplitude (LFRTO) data.

LFRTO = Low Frequency Radio Transmitter Observation. At a receiving station
(site), the LF standard radio signals from each transmitter (trans) are
observed, recording the amplitude (power) and phase as 30-second 1D time series.

There are two receiving stations:
  ath ... Athabasca (Canada)
  nal ... Ny-Alesund (Svalbard)
The transmitters (trans) observed differ by receiving station:
  ath: wwvb ndk nlk npm nau nrk nwc
  nal: msf dcf nrk gbz
One file holds (site, trans, one day), containing both the amplitude and phase
variables (``lf_power_30sec`` / ``lf_phase_30sec``).

The CDF files are assumed to be standard GZIP/uncompressed, so the shared
``load()`` (cdf_to_tplot) is used directly. Each variable is read with
``varformat='lf_'+param+'_30sec'`` and renamed to
``lfrto_{site}_{trans}_{pow30s|pha30s}``.
"""
from pyspedas import get_data, store_data, options

from iugonet.load import load

SITE_CODE_ALL = ["ath", "nal"]

# transmitter list per receiving station
TRANS_CODE_ALL = {
    "ath": ["wwvb", "ndk", "nlk", "npm", "nau", "nrk", "nwc"],
    "nal": ["msf", "dcf", "nrk", "gbz"],
}

# datatype '30s' is normalized to '30sec'
TRES_ALL = ["30sec"]

# 'pow'/'pha' are normalized to 'power'/'phase'
PARAM_ALL = ["power", "phase"]

# {site}/ is appended per site
REMOTE_DATA_DIR = "http://iprt.gp.tohoku.ac.jp/lf/cdf/"

# short names: (param, tres) -> suffix
PTR = {("power", "30sec"): "pow30s", ("phase", "30sec"): "pha30s"}


def _normalize(value, valid, aliases=None):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order kept, dups removed).

    aliases is {alias: canonical} (e.g. {'pow':'power','30s':'30sec'}).
    Codes not in valid are discarded.
    """
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(v).lower() for v in value]
    if aliases:
        items = [aliases.get(it, it) for it in items]
    if "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _normalize_trans(trans):
    """Normalize the trans input to 'all' or a lowercase list of user-requested codes.

    The input is lowercased (order kept, dups removed); the per-site filtering
    is done in _trans_for_site. Returns 'all' if 'all' is present.
    """
    if isinstance(trans, str):
        items = trans.lower().split()
    else:
        items = [str(v).lower() for v in trans]
    if "all" in items:
        return "all"
    out = []
    for it in items:
        if it not in out:
            out.append(it)
    return out


def _trans_for_site(site, trans_norm):
    """List of transmitters actually read for a site.

    If trans_norm == 'all', all transmitters of the site; otherwise only the
    user-requested ones that are valid for the site. Preserves the input order.
    """
    valid = TRANS_CODE_ALL[site]
    if trans_norm == "all":
        return list(valid)
    return [t for t in trans_norm if t in valid]


def _print_ror(var):
    """Print the Rules of the Road / PI information. A failure does not stop the loading."""
    try:
        gatt = get_data(var, metadata=True)["CDF"]["GATT"]

        def _g(k):
            v = gatt.get(k, "")
            return v[0] if isinstance(v, (list, tuple)) and v else v

        print("**********************************************************************")
        print(_g("project"))
        print("")
        print(f'PI and Host PI(s): {_g("PI_name")}')
        print("Affiliations: PPARC, Tohoku University")
        print("")
        print("Rules of the Road for LFRTO Data Use:")
        print(_g("text"))
        print("")
        print(f'{_g("LINK_TEXT")} {_g("HTTP_LINK")}')
        print("**********************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def lfrto(
    trange=["2010-05-29/04:00:00", "2010-05-29/13:00:00"],
    site="all",
    trans="all",
    parameter="all",
    datatype="all",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load Tohoku University LF-band radio phase/amplitude (LFRTO) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2010-05-29/04:00:00', '2010-05-29/13:00:00']
    site : str or list of str
        Receiving station code(s). A space-separated string ('ath nal') or a
        list (['ath', 'nal']) are both accepted. 'all' selects every available
        site. Valid sites: ath nal.
        Default: 'all'
    trans : str or list
        Transmitter code(s). The valid transmitters differ by receiving station:
        ath -> wwvb ndk nlk npm nau nrk nwc, nal -> msf dcf nrk gbz. Only the
        requested transmitters that are valid for a station are used. 'all'
        selects every transmitter of the station.
        Default: 'all'
    parameter : str or list
        Physical quantity. Valid options: 'power'/'pow' (amplitude),
        'phase'/'pha' (phase), 'all' (both).
        Default: 'all'
    datatype : str or list
        Time resolution. Valid options: '30sec'/'30s' / 'all'.
        Default: 'all'
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
        List of tplot variables created. Names are
        ``lfrto_{site}_{trans}_{pow30s|pha30s}``
        (e.g. ``lfrto_nal_msf_pow30s``, ``lfrto_nal_msf_pha30s``). Both are 1D
        time series (x=time, y=amplitude or phase). Empty list if no data were
        loaded. If ``downloadonly`` is set, the list of downloaded file paths is
        returned; if ``notplot`` is set, a dictionary of data is returned
        instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.lfrto(trange=['2010-05-29/04:00:00', '2010-05-29/13:00:00'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    trans_norm = _normalize_trans(trans)
    params = _normalize(parameter, PARAM_ALL, aliases={"pow": "power", "pha": "phase"})
    tres_list = _normalize(datatype, TRES_ALL, aliases={"30s": "30sec"})
    if not sites or not params or not tres_list:
        return {} if notplot else []

    loaded = {} if notplot else []
    ror_done = False

    for st in sites:
        trans_list = _trans_for_site(st, trans_norm)
        remote = REMOTE_DATA_DIR + st + "/"

        for tr in trans_list:
            for tres in tres_list:
                #   filemonth/lfrto_{tres}_{site}_{trans}_{filedate}_v01.cdf
                pathformat = (
                    f"%Y%m/lfrto_{tres}_{st}_{tr}_%Y%m%d_v01.cdf"
                )
                # one file holds both params, so load them together and rename
                # individually later. Read the CDF variable names as-is
                # (lf_power_30sec etc.), so no prefix is added.
                varformat = " ".join(f"lf_{p}_{tres}" for p in params)

                res = load(
                    trange=trange,
                    pathformat=pathformat,
                    file_res=24 * 3600.0,
                    remote_path=remote,
                    local_path=f"tohokuu/radio_obs/{st}/lf/",
                    varformat=varformat,
                    get_support_data=get_support_data,
                    get_metadata=ror,
                    downloadonly=downloadonly,
                    notplot=notplot,
                    no_update=no_update,
                    time_clip=time_clip,
                    verify_cdf=False,
                )

                if downloadonly:
                    loaded += res
                    continue
                if notplot:
                    loaded.update(res)
                    continue

                # ----- rename amplitude/phase -----
                for p in params:
                    tmp = f"lf_{p}_{tres}"               # lf_power_30sec
                    ptr = PTR.get((p, tres))
                    if ptr is None:
                        continue
                    new = f"lfrto_{st}_{tr}_{ptr}" + suffix  # lfrto_nal_msf_pow30s
                    if tmp not in res:
                        continue
                    if get_data(tmp) is None:
                        store_data(tmp, delete=True)
                        continue
                    if ror and not ror_done:
                        _print_ror(tmp)
                        ror_done = True
                    store_data(tmp, newname=new)
                    if p == "phase":
                        # phase is +/-180 degrees
                        options(new, "yrange", [-180, 180])
                    loaded.append(new)

    return loaded
