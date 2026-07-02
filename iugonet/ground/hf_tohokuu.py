"""Load function for Tohoku University Iitate HF-band solar/Jupiter radio spectrum data.

Data are HF-band wideband dynamic spectra from the Iitate observatory (iit)
(15-40 MHz, 700 points along the frequency axis, 1 s resolution). There are two
polarizations, RH (right-hand) and LH (left-hand), each forming a 2D
frequency x time spectrogram (spec=1, y=Frequency[Hz] log, z=[dB]).

The CDF files are standard GZIP/uncompressed and readable by cdflib, so the
shared ``load()`` (cdf_to_tplot) is used directly. ``DISPLAY_TYPE=spectrogram``
and Frequency's ``SCALETYP=log`` make cdf_to_tplot set spec / ylog / y_range /
ysubtitle automatically, matching the original display settings.
"""
from pyspedas import get_data, store_data, options

from iugonet.load import load

SITE_CODE_ALL = ["iit"]
PARAM_ALL = ["rh", "lh"]

REMOTE_DATA_DIR = "http://ariel.gp.tohoku.ac.jp/~jupiter/it_hf/cdf/"

# rename: rh -> iug_iit_hf_R, lh -> iug_iit_hf_L
PARAM_NEWNAME = {"rh": "iug_iit_hf_R", "lh": "iug_iit_hf_L"}


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order kept, dups removed)."""
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


def _print_ror(var):
    """Print the Rules of the Road / PI information. A failure does not stop the loading."""
    try:
        gatt = get_data(var, metadata=True)["CDF"]["GATT"]
        def _g(k):
            v = gatt.get(k, "")
            return v[0] if isinstance(v, (list, tuple)) and v else v
        print("**********************************************************************")
        print(_g("Logical_source_description"))
        print("")
        print(f'PI and Host PI(s): {_g("PI_name")}')
        print(f'Affiliations: {_g("PI_affiliation")}')
        print("")
        print("Rules of the Road for HF Data Use:")
        print(_g("Rules_of_use"))
        print("**********************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def hf_tohokuu(
    trange=["2004-01-09", "2004-01-10"],
    site="iit",
    parameter="all",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load Tohoku University Iitate HF-band solar/Jupiter radio dynamic spectrum data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2004-01-09', '2004-01-10']
    site : str or list of str
        Observatory/station code(s). Currently only 'iit' (Iitate) is valid.
        Default: 'iit'
    parameter : str or list
        Polarization. Valid options: 'RH' (right-hand) / 'LH' (left-hand) /
        'all' (both). A space-separated string ('RH LH') or a list
        (['RH', 'LH']) are both accepted.
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
        List of tplot variables created. RH -> ``iug_iit_hf_R``,
        LH -> ``iug_iit_hf_L``. Both are 2D frequency x time spectrograms
        (x=time, y(=v)=Frequency[Hz] 700 points log, z=[dB], spec=1). Empty list
        if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.hf_tohokuu(trange=['2004-01-09', '2004-01-10'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    params = _normalize(parameter, PARAM_ALL)
    if not sites or not params:
        return {} if notplot else []

    # only site=iit; one daily file holds both RH and LH
    pathformat = "it_h1_hf_%Y%m%d_v0?.cdf"
    # cdf_to_tplot varformat is uppercase ('RH'/'LH')
    varformat = " ".join(p.upper() for p in params)
    prefix = "iit_hf_"

    loaded = {} if notplot else []
    ror_done = False

    for _st in sites:  # only 'iit' for now
        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=24 * 3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="tohokuu/radio_obs/iit/hfspec/",
            prefix=prefix,
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

        # ----- rename RH/LH -----
        # cdf_to_tplot has already set spec=1 (DISPLAY_TYPE=spectrogram) and
        # ylog/y_range/ysubtitle([Hz]) (Frequency SCALETYP=log), matching the
        # original display settings; rename carries the attributes over.
        for pr in params:
            tmp = prefix + pr.upper()                      # iit_hf_RH
            new = PARAM_NEWNAME[pr] + suffix               # iug_iit_hf_R
            if tmp not in res:
                continue
            if get_data(tmp) is None:
                store_data(tmp, delete=True)
                continue
            if ror and not ror_done:
                _print_ror(tmp)
                ror_done = True
            store_data(tmp, newname=new)
            # consistent with the original display settings (spec/ylog/ysubtitle from cdf_to_tplot)
            options(new, "spec", 1)
            options(new, "ztitle", "[dB]")
            loaded.append(new)

    return loaded
