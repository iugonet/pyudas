"""Load function for NIPR (National Institute of Polar Research) fluxgate magnetometer data."""
import numpy as np

from pyspedas import get_data, store_data, options, clip, ylim, time_double

from iugonet.load import load

SITE_CODE_ALL = ["syo", "hus", "tjo", "aed", "isa",
                 "h57", "amb", "srm", "ihd", "skl", "h68"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"


def _normalize_sites(site):
    """Normalize the site input (str/list, 'all' accepted) to a list of valid station codes.

    Preserves the input order and removes duplicates and invalid codes.
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


def _resolve_tres(site, t0):
    """Resolve the logical datatype '1sec' to the actual resolution tres for a site and date.

    t0 is the unix time at the start of trange. The resolution varies by site
    and observation date (2sec / 1sec / 0.5sec '02hz').
    """
    if site == "syo":
        return "2sec" if t0 < time_double("1998-01-01") else "1sec"
    if site == "hus":
        return "2sec" if t0 < time_double("2001-09-08") else "02hz"
    if site == "tjo":
        return "2sec" if t0 < time_double("2001-09-12") else "02hz"
    if site == "aed":
        return "2sec" if t0 < time_double("2001-09-27") else "02hz"
    if site == "isa":
        return "2sec"
    # h57, amb, srm, ihd, skl, h68
    return "1sec"


def _print_ror(var):
    """Print the Rules of the Road / PI information.

    A failure to read the global attributes does not stop the data loading.
    """
    try:
        meta = get_data(var, metadata=True)
        gatt = meta["CDF"]["GATT"]
        print("**************************************************************************")
        print(gatt["Logical_source_description"])
        print("")
        print(f'Information about {gatt["Station_code"]}')
        print(f'PI: {gatt["PI_name"]}')
        print(f'Affiliations: {gatt["PI_affiliation"]}')
        print("")
        print("Rules of the Road for NIPR Fluxgate Magnetometer Data:")
        print("")
        print(gatt["TEXT"])
        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def gmag_nipr(
    trange=["2003-10-29", "2003-10-30"],
    site="all",
    datatype="1sec",
    fproton=False,
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load NIPR fluxgate magnetometer data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2003-10-29', '2003-10-30']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo hus') or a
        list (['syo', 'hus']) are both accepted. 'all' selects every available
        site. Valid sites: syo hus tjo aed isa h57 amb srm ihd skl h68.
        Default: 'all'
    datatype : str
        Logical time resolution. Only '1sec' is valid; the actual resolution is
        chosen automatically per site and date (2sec / 1sec / 0.5sec '02hz').
        Default: '1sec'
    fproton : bool
        If set, also load the total field F from the proton magnetometer
        (Syowa 2sec period only).
        Default: False
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
        List of tplot variables created (``nipr_mag_{site}_{tres}``). Empty list
        if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.gmag_nipr(trange=['2003-10-29', '2003-10-30'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    if str(datatype).lower() != "1sec":
        print("DATATYPE must be '1sec'.")
        return {} if notplot else []

    sites = _normalize_sites(site)
    if not sites:
        return {} if notplot else []

    t0 = time_double(trange[0])
    prefix = "nipr_"

    loaded = {} if notplot else []

    for st in sites:
        tres = _resolve_tres(st, t0)
        pathformat = f"fmag/{st}/{tres}/%Y/nipr_{tres}_fmag_{st}_%Y%m%d_v??.cdf"

        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=24 * 3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="nipr/",
            prefix=prefix,
            varformat="hdz_" + tres if not fproton else None,
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

        # ----- rename and post-process the H/D/Z variables -----
        tmp_name = prefix + "hdz_" + tres            # nipr_hdz_1sec
        new_name = f"nipr_mag_{st}_{tres}" + suffix  # nipr_mag_syo_1sec
        if tmp_name in res:
            d = get_data(tmp_name)
            if d is None:
                store_data(tmp_name, delete=True)
            else:
                if ror:
                    _print_ror(tmp_name)
                store_data(tmp_name, newname=new_name)
                # fill value -1e31 -> NaN
                clip(new_name, -1e5, 1e5)
                options(new_name, "legend_names", ["H", "D", "Z"])
                options(new_name, "Color", ["b", "g", "r"])
                options(new_name, "ytitle", st[:3].upper())
                options(new_name, "ysubtitle", "[nT]")
                loaded.append(new_name)
        else:
            print(f"No tplot var loaded for {st}.")

        # ----- fproton: total field F (Syowa 2sec period only) -----
        if fproton and st == "syo" and tres == "2sec":
            ftmp = prefix + "f_" + tres
            fnew = f"nipr_mag_{st}_{tres}_f" + suffix
            if ftmp in res:
                d = get_data(ftmp)
                if d is None:
                    store_data(ftmp, delete=True)
                else:
                    store_data(ftmp, newname=fnew)
                    clip(fnew, -1e5, 1e5)
                    options(fnew, "legend_names", ["F"])
                    options(fnew, "ytitle", st[:3].upper())
                    options(fnew, "ysubtitle", "[nT]")
                    ylim(fnew, 40000, 49000)
                    loaded.append(fnew)
        elif not fproton:
            # delete the F variable if it was loaded
            ftmp = prefix + "f_" + tres
            if ftmp in res:
                store_data(ftmp, delete=True)

    return loaded
