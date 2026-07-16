"""Load function for NIPR (National Institute of Polar Research) all-sky keogram (ASK) data.

The keograms ``keo_raw_ns`` / ``keo_raw_ew`` are ``[time, 480(pixels)]`` slices
cut out of the all-sky images along the N-S and E-W meridians, distributed as
standard GZIP CDF and read with the shared ``load()`` (cdf_to_tplot).

Not to be confused with :mod:`~iugonet.ground.asi_nipr`, which loads the
full 480x480 images from a different tree (``asi/``, hourly files).
"""
from pyspedas import get_data, options, store_data, ylim

from iugonet.load import load
from iugonet.tools.tdegap import tdegap

SITE_CODE_ALL = ["hus", "kil", "krn", "lyr", "mcm", "skb",
                 "sod", "spa", "syo", "tja", "tjo", "tro"]
# 0000 = white light, taken without a filter.
WAVELENGTH_ALL = ["0000", "4278", "5577", "6300"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"

# Number of pixels along a keogram cut; IDL fixes the y range to this.
_NPIXEL = 480


def _normalize(value, valid, default_all=True):
    """Normalize a site/wavelength input (str/list, 'all' accepted) to a list of valid codes.

    Preserves the input order and removes duplicates and invalid codes.
    """
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(v).lower() for v in value]
    if default_all and "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _is_timeseries(name):
    """True when the tplot variable is a real time series (an xarray DataArray).

    cdf_to_tplot returns NRV/metadata variables as plain dicts, which carry no
    time axis and cannot be passed to ylim/options.
    """
    import pyspedas.tplot_tools as tt
    import xarray as xr
    return isinstance(tt.data_quants.get(name), xr.DataArray)


def _print_ror(var):
    """Print the Rules of the Road / PI information.

    A failure to read the global attributes does not stop the data loading.
    """
    try:
        gatt = get_data(var, metadata=True)["CDF"]["GATT"]
        print("**************************************************************************")
        print(gatt["Logical_source_description"])
        print("")
        print(f'Information about {gatt["Station_code"]}')
        print(f'PI: {gatt["PI_name"]}')
        print("")
        print(f'Affiliations: {gatt["PI_affiliation"]}')
        print("")
        print("Rules of the Road for NIPR All-Sky Imager Data:")
        print("")
        print(gatt["TEXT"])
        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def ask_nipr(
    trange=["2012-01-22", "2012-01-23"],
    site="all",
    wavelength="0000",
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load NIPR all-sky keogram data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2012-01-22', '2012-01-23']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo tro') or a
        list (['syo', 'tro']) are both accepted. 'all' selects every available
        site. Valid sites: hus kil krn lyr mcm skb sod spa syo tja tjo tro.
        Default: 'all'
    wavelength : str or list of str
        Wavelength in Angstrom. Valid options: '0000' (white light, no filter)
        / '4278' / '5577' / '6300' / 'all'.
        Default: '0000'
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
        List of tplot variables created (``nipr_ask_{site}_{wavelength}_ns`` and
        ``_ew``). Empty list if no data were loaded. If ``downloadonly`` is set,
        the list of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Notes
    -----
    The keograms are gap-filled with ``tdegap(margin=6)``, as IDL does, so the
    output carries NaN rows wherever the camera was not running: a full day is
    8640 rows at the 10 s cadence even when the file holds far fewer samples
    (3960 for tro on 2012-01-22).

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.ask_nipr(trange=['2012-01-22', '2012-01-23'], site='tro')
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    wlens = _normalize(wavelength, WAVELENGTH_ALL)
    if not sites or not wlens:
        return {} if notplot else []

    # IDL loads with a temporary prefix and renames once the param is known.
    tmp_prefix = "niprtmp_"
    loaded = {} if notplot else []

    for st in sites:
        for wl in wlens:
            pathformat = f"ask/{st}/%Y/nipr_ask_{st}_{wl}_%Y%m%d_v??.cdf"

            res = load(
                trange=trange,
                pathformat=pathformat,
                file_res=24 * 3600.0,
                remote_path=REMOTE_DATA_DIR,
                local_path="nipr/",
                prefix=tmp_prefix,
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
            if not res:
                print(f"No tplot var loaded for {st}.")
                continue

            if ror:
                # res[0] is epoch_keo, a dict variable with no metadata; read the
                # global attributes off a real keogram instead.
                real = next((n for n in res if _is_timeseries(n)), None)
                if real is not None:
                    _print_ror(real)

            for tmp_name in list(res):
                # Only the keograms are real time series. epoch_keo is the time
                # axis (VAR_TYPE='data' in the CDF, but DEPEND_0 of the
                # keograms), and index_*/sensitivity_*/label_*/unit_* are NRV
                # metadata that pyspedas returns as broken dict variables when
                # get_metadata is set. IDL's cdf2tplot makes no tplot variable
                # for any of them, so drop them here too.
                if not _is_timeseries(tmp_name):
                    store_data(tmp_name, delete=True)
                    continue
                param = (tmp_name[len(tmp_prefix):] if tmp_name.startswith(tmp_prefix)
                         else tmp_name.split("_", 1)[-1])

                ylim(tmp_name, 0, _NPIXEL)
                # The camera does not run all day, so the file is sparse. IDL
                # fills the gaps before renaming; margin=6 is IDL's value.
                tdegap(tmp_name, margin=6, overwrite=True)

                if param == "keo_raw_ns":
                    new_name = f"nipr_ask_{st}_{wl}_ns" + suffix
                    options(tmp_name, "ytitle", f"{st} {wl}\nNS keogram")
                    options(tmp_name, "ysubtitle", "[pixels]")
                    options(tmp_name, "spec", 1)
                    options(tmp_name, "ztitle", "[counts]")
                elif param == "keo_raw_ew":
                    new_name = f"nipr_ask_{st}_{wl}_ew" + suffix
                    options(tmp_name, "ytitle", f"{st} {wl}\nEW keogram")
                    options(tmp_name, "ysubtitle", "[pixels]")
                    options(tmp_name, "spec", 1)
                    options(tmp_name, "ztitle", "[counts]")
                else:
                    new_name = f"nipr_ask_{st}_{wl}_{param}" + suffix

                store_data(tmp_name, newname=new_name)
                loaded.append(new_name)

    return loaded
