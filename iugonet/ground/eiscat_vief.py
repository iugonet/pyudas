"""Load function for EISCAT vector Vi / E field (vief) data.

The "vief" CDF files use GZIP compression that cdflib supports, so unlike
``eiscat.py`` (basic data) they can be read directly with pyspedas' standard
``cdf_to_tplot``. Variables are 1D time series; Vi / E / quality etc. are
3-component vectors ([e, n, u] = [eastward, northward, upward]).

Data are downloaded from the NIPR EISCAT server pc115.seg20.nipr.ac.jp (the
same host as eiscat.py). ``verify_cdf=False`` is passed because the pyspedas
download CDF verification can fail on this compression and delete the files.
"""
import numpy as np

from pyspedas import get_data, store_data, options, clip, ylim

from iugonet.load import load

# 'kst' = Kiruna, Sodankyla, Tromso (combined tristatic analysis data).
SITE_CODE_ALL = ["kst"]

REMOTE_DATA_DIR = "http://pc115.seg20.nipr.ac.jp/www/eiscatdata/cdf/"

# paramstr rename table.
PARAM_RENAME = {
    "pulse_code_id": "pulse",
    "int_time_nominal": "inttim",
    "vi_err": "vierr",
    "E_err": "Eerr",
    "quality": "q",
    "int_time_real": "inttimr",
}


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


def _print_ror(var):
    """Print the Rules of the Road / PI information.

    A failure to read the global attributes does not stop the data loading.
    """
    try:
        meta = get_data(var, metadata=True)
        gatt = meta["CDF"]["GATT"]
        print("**************************************************************************")
        print("Information about EISCAT radar data")
        print(gatt["Logical_source_description"])
        print("")
        print(f'PI: {gatt["PI_name"]}')
        print(f'Affiliations: {gatt["PI_affiliation"]}')
        print("")
        print("Rules of the Road for EISCAT Radar Data:")
        print("")
        print(gatt["Rules_of_use"])
        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def _set_options(new_name, param, site):
    """Set options / clip / ylim per param.

    ytitle uses a ``site\n`` newline (equivalent to the original ``site+'!C'``).
    The original colors=[2,4,6] (blue/green/red in the spedas color table) are
    set as Color=['b','g','r'] to match the original UDAS output.
    """
    head = site + "\n"
    if param == "pulse_code_id":
        options(new_name, "legend_names", "Pulse code ID")
        options(new_name, "ytitle", head + "Pulse code ID")
    elif param == "int_time_nominal":
        options(new_name, "legend_names", "int.time\n(nominal)")
        options(new_name, "ytitle", head + "Int. time (nominal)")
        options(new_name, "ysubtitle", "[s]")
        clip(new_name, 0, 1e4)
        ylim(new_name, -50, 350)
    elif param == "lat":
        options(new_name, "legend_names", "Lat")
        options(new_name, "ytitle", head + "Latitude")
        options(new_name, "ysubtitle", "[deg]")
    elif param == "long":
        options(new_name, "legend_names", "Lon")
        options(new_name, "ytitle", head + "Longitude")
        options(new_name, "ysubtitle", "[deg]")
    elif param == "alt":
        options(new_name, "legend_names", "Alt")
        options(new_name, "ytitle", head + "Altitude")
        options(new_name, "ysubtitle", "[km]")
    elif param == "vi":
        options(new_name, "legend_names", ["Ve", "Vn", "Vu"])
        options(new_name, "ytitle", head + "Vi")
        options(new_name, "ysubtitle", "[m/s]")
        options(new_name, "Color", ["b", "g", "r"])
        ylim(new_name, -1000.0, 1000.0)
    elif param == "vi_err":
        options(new_name, "legend_names", ["Ve_err", "Vn_err", "Vu_err"])
        options(new_name, "ytitle", head + "Vi err.")
        options(new_name, "ysubtitle", "[m/s]")
        options(new_name, "Color", ["b", "g", "r"])
        ylim(new_name, 0.0, 1000.0)
    elif param == "E":
        options(new_name, "legend_names", ["Ee", "En", "Eu"])
        options(new_name, "ytitle", head + "E")
        options(new_name, "ysubtitle", "[mV/m]")
        options(new_name, "Color", ["b", "g", "r"])
        ylim(new_name, -50.0, 50.0)
    elif param == "E_err":
        options(new_name, "legend_names", ["Ee_err", "En_err", "Eu_err"])
        options(new_name, "ytitle", head + "E err.")
        options(new_name, "ysubtitle", "[mV/m]")
        options(new_name, "Color", ["b", "g", "r"])
        ylim(new_name, 0.0, 50.0)
    elif param == "quality":
        options(new_name, "legend_names", ["q1", "q2", "q3"])
        options(new_name, "ytitle", head + "Quality")
    elif param == "int_time_real":
        options(new_name, "legend_names", "int.time\n   (real)")
        options(new_name, "ytitle", head + "Int. time (real)")
        options(new_name, "ysubtitle", "[s]")
        clip(new_name, 0, 1e4)
        ylim(new_name, -50, 350)
    # else: no options are set for other params


def eiscat_vief(
    trange=["2011-02-04", "2011-02-08"],
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
    """Load EISCAT vector Vi / E field data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2011-02-04', '2011-02-08']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are both
        accepted. 'all' selects every available site.
        Valid sites: 'kst' (Kiruna, Sodankyla, Tromso).
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
        be loaded into tplot (e.g. int_time_real -> inttimr).
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
        List of tplot variables created (``eiscat_{site}_{paramstr}``).
        Vi / E / quality are 3-component vectors ([e, n, u]); the others are 1D
        scalar time series. Empty list if no data were loaded. If
        ``downloadonly`` is set, the list of downloaded file paths is returned;
        if ``notplot`` is set, a dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.eiscat_vief(trange=['2011-02-04', '2011-02-08'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        return {} if notplot else []

    prefix = "eiscat_"
    loaded = {} if notplot else []
    ack_done = False

    for st in sites:
        pathformat = f"vief/{st}/%Y/eiscat_kn_{st}_vief_%Y%m%d_v??.cdf"

        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=24 * 3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="nipr/eiscat/",
            prefix=prefix,
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

        if not res:
            print(f"No tplot var loaded for {st}.")
            continue

        # ----- print the Rules of the Road only once -----
        if ror and not ack_done:
            _print_ror(res[0])
            ack_done = True

        # ----- rename each tplot variable and set its options -----
        for cur in res:
            if get_data(cur) is None:
                store_data(cur, delete=True)
                continue
            # param = the part with the prefix and trailing '_0' removed
            if not (cur.startswith(prefix) and cur.endswith("_0")):
                continue
            param = cur[len(prefix):-2]
            # Epoch is the time axis itself. pyspedas turns Epoch_0 into a
            # variable when get_support_data=True, so exclude it from renaming
            # to match the original UDAS output (which makes no such variable).
            if param == "Epoch":
                store_data(cur, delete=True)
                continue
            paramstr = PARAM_RENAME.get(param, param)
            new_name = f"eiscat_{st}_{paramstr}" + suffix

            store_data(cur, newname=new_name)
            _set_options(new_name, param, st)
            loaded.append(new_name)

    return loaded
