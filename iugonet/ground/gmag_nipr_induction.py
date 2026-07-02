"""Load function for NIPR (National Institute of Polar Research) induction magnetometer data."""
from pyspedas import get_data, store_data, options, clip, time_double

from iugonet.load import load

SITE_CODE_ALL = ["syo", "hus", "tjo", "aed", "isa"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"


def _normalize_sites(site):
    """Normalize the site input (str/list, 'all' accepted) to a list of valid station codes."""
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


def _resolve_tres(site, t0):
    """Resolve the actual time resolution tres for a site and date.

    Unlike the fluxgate, the current resolution at syo is 20hz.
    """
    if site == "syo":
        return "2sec" if t0 < time_double("1998-01-01") else "20hz"
    if site == "hus":
        return "2sec" if t0 < time_double("2001-09-08") else "02hz"
    if site == "tjo":
        return "2sec" if t0 < time_double("2001-09-12") else "02hz"
    if site == "aed":
        return "2sec" if t0 < time_double("2001-09-27") else "02hz"
    # isa is always 2sec
    return "2sec"


def _print_ror(var):
    """Print the Rules of the Road / PI information."""
    try:
        gatt = get_data(var, metadata=True)["CDF"]["GATT"]
        print("**************************************************************************")
        print(gatt.get("Logical_source_description"))
        print("")
        print(f'PI: {gatt.get("PI_name")}')
        print(f'Affiliation: {gatt.get("PI_affiliation")}')
        print("")
        print("Rules of the Road for NIPR Induction Magnetometer Data Use:")
        print(gatt.get("Rules_of_use"))
        print(f'{gatt.get("LINK_TEXT")} {gatt.get("HTTP_LINK")}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def gmag_nipr_induction(
    trange=["2006-04-17", "2006-04-18"],
    site="all",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load NIPR induction magnetometer data (dB/dt).

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2006-04-17', '2006-04-18']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo hus') or a
        list (['syo', 'hus']) are both accepted. 'all' selects every available
        site. Valid sites: syo hus tjo aed isa.
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
        List of tplot variables created (``nipr_imag_{site}_{tres}``). The
        resolution tres is chosen automatically per site and date (currently
        syo=20hz, hus/tjo/aed=02hz, isa=2sec). Empty list if no data were
        loaded. If ``downloadonly`` is set, the list of downloaded file paths
        is returned; if ``notplot`` is set, a dictionary of data is returned
        instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gmag_nipr_induction(trange=['2006-04-17', '2006-04-18'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        return {} if notplot else []

    t0 = time_double(trange[0])
    loaded = {} if notplot else []

    for st in sites:
        tres = _resolve_tres(st, t0)
        pathformat = f"imag/{st}/{tres}/%Y/nipr_{tres}_imag_{st}_%Y%m%d_v??.cdf"

        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=24 * 3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="nipr/",
            prefix="nipr_imag_",
            suffix="_" + st,
            varformat="db_dt",
            downloadonly=downloadonly,
            get_support_data=get_support_data,
            get_metadata=ror,
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

        # delete the unneeded GPS time-pulse variable
        gps = f"nipr_imag_gps_1pps_time_pulse_{st}"
        if gps in res:
            store_data(gps, delete=True)

        # rename and post-process the db_dt variable
        tmp_name = f"nipr_imag_db_dt_{st}"
        new_name = f"nipr_imag_{st}_{tres}" + suffix
        if tmp_name in res:
            d = get_data(tmp_name)
            if d is None:
                store_data(tmp_name, delete=True)
            else:
                if ror:
                    _print_ror(tmp_name)
                store_data(tmp_name, newname=new_name)
                clip(new_name, -1e5, 1e5)
                options(new_name, "legend_names", ["dH/dt", "dD/dt", "dZ/dt"])
                loaded.append(new_name)
        else:
            print(f"No tplot var loaded for {st}.")

    return loaded
