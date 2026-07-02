"""Load function for NIPR (National Institute of Polar Research) imaging riometer data.

The main imaging-riometer variable ``cna`` (Cosmic Noise Absorption) is a 3D
beam array ``[time, 8(N-S), 8(E-W)]`` distributed as standard GZIP CDF, so it is
read with the shared ``load()`` (cdf_to_tplot).
"""
import numpy as np

from pyspedas import get_data, store_data, options, tnames
from pyspedas import time_clip as tclip

from iugonet.load import load

SITE_CODE_ALL = ["syo", "hus", "tjo", "zho"]
# observation frequency [MHz]
DATATYPE_ALL = ["30", "38"]

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


def _resolve_datatypes(site, datatype, t0):
    """Determine the valid datatypes for a site and date.

      hus -> '38' only / tjo, zho -> '30' only
      syo -> '30' only before 2007-01-01, both '30' and '38' afterwards
    Intersected with the user-requested datatype (default 'all').
    """
    if site == "hus":
        site_dt = ["38"]
    elif site in ("tjo", "zho"):
        site_dt = ["30"]
    else:  # syo
        if t0 < _time_double("2007-01-01"):
            site_dt = ["30"]
        else:
            site_dt = ["30", "38"]

    if isinstance(datatype, str):
        req = datatype.lower().split()
    else:
        req = [str(d).lower() for d in datatype]
    if "all" in req:
        return list(site_dt)
    # keep the site_dt order while restricting to the user request
    return [d for d in site_dt if d in req]


def _time_double(s):
    # thin wrapper to avoid import-order dependence at test time
    from pyspedas import time_double
    return time_double(s)


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
        print("Rules of the Road for NIPR Imaging Riometer Data:")
        print("")
        print(gatt["TEXT"])
        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def _make_keogram(name):
    """Expand the 3D cna variable (time, 8(NS), 8(EW)) into 16 keograms.

      fixed EW=iew, all NS    -> ``{name}_N0-7E{iew}``  (y is [time, 8])
      fixed NS=ins, all EW    -> ``{name}_N{ins}E0-7``
    Both have spec=1, ztitle='[dB]'. v (the y axis) is the beam number 0..7.
    """
    out = []
    d = get_data(name)
    if d is None:
        return out
    t = d[0]
    y = np.asarray(d[1])  # expected shape (ntime, 8, 8)
    if y.ndim != 3:
        # cannot build keograms unless 3D (unexpected structure)
        return out
    beam_no = np.arange(y.shape[1], dtype=float)

    # fix the NS direction, EW on the y axis -> _N{ins}E0-7
    for ins in range(y.shape[1]):
        dns = y[:, ins, :]
        new = f"{name}_N{ins}E0-7"
        store_data(new, data={"x": t, "y": dns, "v": beam_no})
        options(new, "spec", 1)
        options(new, "ztitle", "[dB]")
        options(new, "ysubtitle", "")
        out.append(new)

    # fix the EW direction, NS on the y axis -> _N0-7E{iew}
    for iew in range(y.shape[2]):
        dew = y[:, :, iew]
        new = f"{name}_N0-7E{iew}"
        store_data(new, data={"x": t, "y": dew, "v": beam_no})
        options(new, "spec", 1)
        options(new, "ztitle", "[dB]")
        options(new, "ysubtitle", "")
        out.append(new)

    return out


def _load_positions(files, dt, site):
    """Read azimuth/zenith angles from the first file and build the az/ze variables.

    azimuth_angle / zenith_angle (2D [8,8]) are replicated at two times (first
    and last) and stored as ``..._az`` / ``..._ze``. They are read directly with
    cdflib rather than through cdf_to_tplot (support data, NRV).
    """
    out = []
    try:
        import cdflib
    except Exception:
        return out
    try:
        cdf = cdflib.CDF(files[0])
        info = cdf.cdf_info()
        all_vars = list(getattr(info, "zVariables", [])) + list(getattr(info, "rVariables", []))

        def _find(substr):
            for v in all_vars:
                if substr in v:
                    return v
            return None

        tmvn = _find("epoch_1sec")
        azvn = _find("azimuth_angle")
        zevn = _find("zenith_angle")
        if tmvn is None or azvn is None or zevn is None:
            return out

        epoch = np.asarray(cdf.varget(tmvn))
        aztmp = np.asarray(cdf.varget(azvn), dtype=float)
        zetmp = np.asarray(cdf.varget(zevn), dtype=float)

        # time = [first, last] converted epoch -> unix
        t2 = _time_double([
            cdflib.cdfepoch.encode(epoch[0]),
            cdflib.cdfepoch.encode(epoch[-1]),
        ])

        # replicate az/ze to (2(time), 8, 8) with the time axis first
        az = np.stack([aztmp, aztmp], axis=0)
        ze = np.stack([zetmp, zetmp], axis=0)

        name_az = f"nipr_irio{dt}_{site}_az"
        name_ze = f"nipr_irio{dt}_{site}_ze"
        store_data(name_az, data={"x": np.asarray(t2), "y": az})
        store_data(name_ze, data={"x": np.asarray(t2), "y": ze})
        out += [name_az, name_ze]
    except Exception:
        pass
    return out


def irio_nipr(
    trange=["2003-02-09", "2003-02-10"],
    site="all",
    datatype="all",
    keogram=False,
    no_update=False,
    downloadonly=False,
    get_support_data=False,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load NIPR imaging riometer data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'].
        Default: ['2003-02-09', '2003-02-10']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo hus') or a
        list (['syo', 'hus']) are both accepted. 'all' selects every available
        site. Valid sites: syo hus tjo zho.
        Default: 'all'
    datatype : str or list
        Observation frequency [MHz]. Valid options: '30' / '38' / 'all'. The
        valid values are restricted by site and date (hus:38, tjo/zho:30,
        syo:30 only before 2007).
        Default: 'all'
    keogram : bool
        Build keograms (16 time x beam spectrograms) from the 3D cna.
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
        List of tplot variables created
        (``nipr_irio{dt}_{site}_cna`` / ``_qdc`` / ``_az`` / ``_ze``; when
        keogram is set, ``_cna_N{i}E0-7`` / ``_cna_N0-7E{i}`` are added). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.irio_nipr(trange=['2003-02-09', '2003-02-10'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_sites(site)
    if not sites:
        return {} if notplot else []

    t0 = _time_double(trange[0])
    # load with a temporary niprtmp_ prefix, then rename after extracting param
    tmp_prefix = "niprtmp_"

    loaded = {} if notplot else []

    for st in sites:
        dts = _resolve_datatypes(st, datatype, t0)
        for dt in dts:
            pathformat = f"irio/{st}/%Y/nipr_h0_irio{dt}_{st}_%Y%m%d_v??.cdf"

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
                _print_ror(res[0])

            site_dt_vars = []
            # ----- niprtmp_{param} -> nipr_irio{dt}_{site}_{param} -----
            for tmp_name in list(res):
                # param is the remainder after stripping the niprtmp_ prefix
                # (cna, qdc, epoch_1min, ...).
                if tmp_name.startswith(tmp_prefix):
                    param = tmp_name[len(tmp_prefix):]
                else:
                    param = tmp_name.split("_", 1)[-1]
                # epoch_1min/epoch_1sec have VAR_TYPE='data' in the CDF but are
                # really the time axis. cdf_to_tplot makes them as broken (dict)
                # variables, so drop them (no tplot variable for the time axis).
                if param.startswith("epoch"):
                    store_data(tmp_name, delete=True)
                    continue
                new_name = f"nipr_irio{dt}_{st}_{param}" + suffix
                d = get_data(tmp_name)
                if d is None:
                    store_data(tmp_name, delete=True)
                    continue
                store_data(tmp_name, newname=new_name)
                # fill value -1e31 -> NaN
                _clip_inplace(new_name)

                if param == "cna":
                    options(new_name, "ytitle", st[:3].upper())
                    options(new_name, "ysubtitle", "[dB]")
                    options(new_name, "spec", 0)
                    options(new_name, "ztitle", "[dB]")
                    site_dt_vars.append(new_name)
                    if keogram:
                        site_dt_vars += _make_keogram(new_name)
                elif param == "qdc":
                    options(new_name, "ytitle", "QDC")
                    options(new_name, "spec", 0)
                    site_dt_vars.append(new_name)
                else:
                    site_dt_vars.append(new_name)

            # ----- azimuth/zenith angles az/ze -----
            # read from the first file of the same trange/site/dt
            files = load(
                trange=trange,
                pathformat=pathformat,
                file_res=24 * 3600.0,
                remote_path=REMOTE_DATA_DIR,
                local_path="nipr/",
                downloadonly=True,
                no_update=True,  # already downloaded: do not re-download
            )
            if files:
                site_dt_vars += _load_positions(files, dt, st)

            loaded += site_dt_vars

    return loaded


def _clip_inplace(name):
    """Replace fill values (-1e31 etc.) with NaN.

    pyspedas' clip sets out-of-range values to NaN, updating the tplot variable
    in place. It also works on 3D data (cna is (n,8,8)) via xarray broadcasting.
    Degenerate variables that are not a DataArray (e.g. dict) cannot be clipped
    and are skipped.
    """
    from pyspedas import clip
    import pyspedas.tplot_tools as tt
    import xarray as xr
    q = tt.data_quants.get(name)
    if not isinstance(q, xr.DataArray):
        return
    clip(name, -1e5, 1e5)
