"""Load function for Hokudai (Hokkaido University) ELF magnetic-field waveform data (Syowa)."""
from pyspedas import get_data, options, tnames

from iugonet.load import load

SITE_CODE_ALL = ["syo"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"


def _normalize_sites(site):
    """Normalize the site input (str/list, 'all' accepted) to a list of valid station codes.

    Preserves the input order and removes duplicates and invalid codes. A string
    is split on whitespace ('syo' and ['syo'] both accepted).
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


def _print_ror(var):
    """Print the Rules of the Road / PI information.

    A failure to read the global attributes does not stop the data loading.
    """
    try:
        gatt = get_data(var, metadata=True)["CDF"]["GATT"]
        print("**************************************************************************")
        print(gatt.get("Logical_source_description"))
        print("")
        print(f'Information about {gatt.get("Station_code")}')
        print(f'PI: {gatt.get("PI_name")}')
        print(f'Affiliations: {gatt.get("PI_affiliation")}')
        print("")
        print("Rules of the Road for Hokudai Induction Magnetometer Data:")
        print("")
        text = gatt.get("TEXT")
        if isinstance(text, (list, tuple)):
            for line in text:
                print(line)
        else:
            print(text)
        print(f'{gatt.get("LINK_TEXT")} {gatt.get("HTTP_LINK")}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def elf_hokudai(
    trange=["2010-04-01", "2010-04-01/01:00:00"],
    site="all",
    datatype="elf",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
    verbose=False,
):
    """Load Hokudai ELF magnetic-field waveform data (Syowa).

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Files are hourly
        (file_res=3600). ELF is 400 Hz x 2 components (1.44M points per file),
        so a short time window (with time_clip) is recommended.
        Default: ['2010-04-01', '2010-04-01/01:00:00']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo') or a list
        (['syo']) are both accepted. 'all' selects every available site.
        Valid sites: syo (Syowa only).
        Default: 'all'
    datatype : str
        Instrument type. Valid options: 'elf'.
        Default: 'elf'
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
    verbose : bool
        Verbosity level for diagnostic messages.
        Default: False

    Returns
    -------
    list of str
        List of tplot variables created. Main variables:
          - ``hokudai_elf_{site}``       : ELF magnetic-field waveform (time, 2) = H/D components [pT]
          - ``hokudai_irig_code_{site}`` : GPS IRIG-E time code (time, 1) [V]
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.elf_hokudai(trange=['2010-04-01', '2010-04-01/01:00:00'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        return {} if notplot else []

    # datatype is kept as the instrument name
    instr = "elf"

    loaded = {} if notplot else []

    for st in sites:
        #   'elf/syo/YYYY/MM/YYYYMMDD/geon_elf_syo_YYYYMMDD_hh_v??.cdf'
        pathformat = (
            f"{instr}/{st}/%Y/%m/%Y%m%d/"
            f"geon_{instr}_{st}_%Y%m%d_%H_v??.cdf"
        )

        prefix = "hokudai_"
        var_suffix = "_" + st + suffix

        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="hokudai/",
            prefix=prefix,
            suffix=var_suffix,
            get_support_data=get_support_data,
            get_metadata=ror,
            downloadonly=downloadonly,
            notplot=notplot,
            no_update=no_update,
            time_clip=time_clip,
        )

        if downloadonly:
            loaded += res
            continue
        if notplot:
            loaded.update(res)
            continue

        if not res:
            print(f"No tplot var loaded for {st}.")
            continue

        # ----- Rules of the Road / PI information -----
        elf_name = f"{prefix}{instr}{var_suffix}"  # hokudai_elf_syo
        if ror and elf_name in res:
            _print_ror(elf_name)

        # ----- Labels -----
        # The original sets labels=['H-comp.','D-comp.'], labflag=1, colors=[2,4].
        # labflag=1 has no pyspedas equivalent and is omitted (display-only).
        # The fill-value clip (-1e31 -> NaN) is commented out in the original, so
        # the data are left unmodified here too (to keep them bit-identical).
        for v in tnames(f"{prefix}{instr}*"):
            options(v, "legend_names", ["H-comp.", "D-comp."])
            options(v, "Color", ["b", "g"])  # colors=[2,4] (2=blue, 4=green) to match the original UDAS output

        # return all created variables (no variables are deleted)
        loaded += [v for v in res if v not in loaded]

    return loaded
