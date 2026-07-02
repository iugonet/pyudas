"""Load function for NIPR (National Institute of Polar Research) all-sky imager (ASI) data."""
import contextlib
import logging

import numpy as np

from pyspedas import get_data, store_data, options, clip, time_double

from iugonet.load import load


@contextlib.contextmanager
def _quiet_store_data():
    """Suppress the coordinate warning store_data emits for >3D variables with equal-length axes.

    azel/pos_cen/pos_cor carry v1..v4, but the pyspedas xarray store_data
    treats equal-length axes (e.g. nx==ny) as ambiguous and cannot attach the
    coordinates (spec_bins/vN_dim), emitting a warning. The data body (y) is
    stored correctly in the right order, so only the warning is silenced.
    """
    prev = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        yield
    finally:
        logging.disable(prev)

# Use CDFAstropy when available (faster unix conversion).
try:
    from cdflib.epochs_astropy import CDFAstropy as cdfepoch
except Exception:
    from cdflib.epochs import CDFepoch as cdfepoch

SITE_CODE_ALL = ["hus", "kil", "krn", "lyr", "mcm", "skb",
                 "sod", "spa", "syo", "tja", "tjo", "tro"]
# 0000 = unfiltered white light.
WAVELENGTH_ALL = ["0000", "4278", "5577", "6300"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"


def _normalize_list(value, valid):
    """Normalize a site / wavelength input (str/list, 'all' accepted) to a list of valid values.

    Preserves the input order and removes duplicates and invalid values. A
    string is split on whitespace ('syo hus' and ['syo','hus'] both accepted).
    """
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(s).lower() for s in value]
    if "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def _format_wavelength(value):
    """Format wavelength to a 4-digit zero-padded string.

    Numeric 5577 / '5577' / 0 are all normalized to '0000', '5577', etc.,
    then normalized against WAVELENGTH_ALL.
    """
    if isinstance(value, str):
        items = value.lower().split()
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    out = []
    for it in items:
        s = str(it).lower()
        if s == "all":
            out.append("all")
            continue
        try:
            out.append(f"{int(it):04d}")
        except (ValueError, TypeError):
            out.append(s)
    return _normalize_list(out, WAVELENGTH_ALL)


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
        print("Rules of the Road for NIPR All-Sky Imager Data:")
        print("")
        print(gatt["TEXT"])
        print(f'{gatt["LINK_TEXT"]} {gatt["HTTP_LINK"]}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def asi_nipr(
    trange=["2012-01-22/20:30", "2012-01-22/21:00"],
    site="all",
    wavelength="0000",
    no_update=False,
    downloadonly=False,
    get_support_data=True,
    notplot=False,
    time_clip=False,
    version=None,
    ror=True,
    suffix="",
):
    """Load NIPR all-sky imager (ASI) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Files are hourly
        (file_res=3600).
        Default: ['2012-01-22/20:30', '2012-01-22/21:00']
    site : str or list of str
        Observatory/station code(s). A space-separated string ('syo hus') or a
        list (['syo', 'hus']) are both accepted. 'all' selects every available
        site. Valid sites: hus kil krn lyr mcm skb sod spa syo tja tjo tro.
        Default: 'all'
    wavelength : str, int or list
        Wavelength [Angstrom]. Valid options: '0000' (unfiltered white light) /
        '4278' / '5577' / '6300'. A numeric value such as 5577 is also accepted
        (zero-padded to 4 digits); 'all' is accepted.
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
        Default: True
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
        List of tplot variables created. Main variables:
          - ``nipr_asi_{site}_{wlen}``        : all-sky image (time, 480, 480)
          - ``nipr_asi_{site}_{wlen}_azel``   : azimuth/elevation
          - ``nipr_asi_{site}_{wlen}_pos_cen``: geographic lat/lon of pixel centers (per altitude)
          - ``nipr_asi_{site}_{wlen}_pos_cor``: geographic lat/lon of pixel corners (per altitude)
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.asi_nipr(trange=['2012-01-22/20:30', '2012-01-22/21:00'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize_list(site, SITE_CODE_ALL)
    wlens = _format_wavelength(wavelength)
    if not sites or not wlens:
        return {} if notplot else []

    prefix_tmp = "niprtmp_"
    instr = "asi"

    loaded = {} if notplot else []

    for st in sites:
        for wl in wlens:
            pathformat = (
                f"{instr}/{st}/%Y/%m/%d/"
                f"nipr_{instr}_{st}_{wl}_%Y%m%d%H_v??.cdf"
            )

            res = load(
                trange=trange,
                pathformat=pathformat,
                file_res=3600.0,
                remote_path=REMOTE_DATA_DIR,
                local_path="nipr/",
                prefix=prefix_tmp,
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

            base = f"nipr_{instr}_{st}_{wl}" + suffix  # nipr_asi_hus_0000

            # ----- rename image_raw to the main variable name -----
            img_tmp = prefix_tmp + "image_raw"
            if img_tmp in res:
                d = get_data(img_tmp)
                if d is None:
                    store_data(img_tmp, delete=True)
                else:
                    if ror:
                        _print_ror(img_tmp)
                    store_data(img_tmp, newname=base)
                    # fill value -1e31 -> NaN
                    clip(base, -1e5, 1e5)
                    options(base, "spec", 0)
                    options(base, "Colormap", "rainbow")
                    options(base, "ytitle", st.upper())
                    options(base, "ysubtitle", "[count]")
                    loaded.append(base)

            # ----- read the position support variables and build derived variables -----
            # NRV (non-record-varying) variables come back from get_data as a
            # bare ndarray under cdf_to_tplot.
            az = _get_ndarray(prefix_tmp + "azimuth_angle")
            el = _get_ndarray(prefix_tmp + "elevation_angle")
            glatcen = _get_ndarray(prefix_tmp + "glat_center")
            gloncen = _get_ndarray(prefix_tmp + "glon_center")
            glatcor = _get_ndarray(prefix_tmp + "glat_corner")
            gloncor = _get_ndarray(prefix_tmp + "glon_corner")
            alt = _get_ndarray(prefix_tmp + "altitude")
            time2 = _epoch_two_point(prefix_tmp + "epoch_image", base)

            have_pos = all(a is not None for a in
                           (az, el, glatcen, gloncen, glatcor, gloncor, alt)) \
                and time2 is not None

            if have_pos:
                # dim of glatcen => [nalt, nx, ny]
                nalt, nx, ny = glatcen.shape
                v1 = np.array([0, 1])
                vx = np.arange(nx)
                vy = np.arange(ny)
                vx2 = np.arange(nx + 1)
                vy2 = np.arange(ny + 1)

                # --- azel ---
                # shape (2, nx, ny, 2); v1=[0,1], v2=vx, v3=vy
                azel = np.zeros((2, nx, ny, 2), dtype=np.float32)
                azel[0, :, :, 0] = az
                azel[0, :, :, 1] = az
                azel[1, :, :, 0] = el
                azel[1, :, :, 1] = el

                # --- pos_cen ---
                # shape (2, nalt, nx, ny, 2); v1=[0,1], v2=alt, v3=vx, v4=vy
                pos_cen = np.zeros((2, nalt, nx, ny, 2), dtype=np.float32)
                pos_cen[0, :, :, :, 0] = glatcen
                pos_cen[0, :, :, :, 1] = glatcen
                pos_cen[1, :, :, :, 0] = gloncen
                pos_cen[1, :, :, :, 1] = gloncen

                # --- pos_cor ---
                # shape (2, nalt, nx+1, ny+1, 2); v1=[0,1], v2=alt, v3=vx2, v4=vy2
                pos_cor = np.zeros((2, nalt, nx + 1, ny + 1, 2), dtype=np.float32)
                pos_cor[0, :, :, :, 0] = glatcor
                pos_cor[0, :, :, :, 1] = glatcor
                pos_cor[1, :, :, :, 0] = gloncor
                pos_cor[1, :, :, :, 1] = gloncor

                name_azel = base + "_azel"
                name_cen = base + "_pos_cen"
                name_cor = base + "_pos_cor"
                # store with the original y order while suppressing the equal-length-axis warning
                with _quiet_store_data():
                    store_data(name_azel,
                               data={"x": time2, "y": azel,
                                     "v1": v1, "v2": vx, "v3": vy})
                    store_data(name_cen,
                               data={"x": time2, "y": pos_cen,
                                     "v1": v1, "v2": alt, "v3": vx, "v4": vy})
                    store_data(name_cor,
                               data={"x": time2, "y": pos_cor,
                                     "v1": v1, "v2": alt, "v3": vx2, "v4": vy2})

                for nm in (name_azel, name_cen, name_cor):
                    clip(nm, -1e5, 1e5)
                    options(nm, "Colormap", "rainbow")
                    options(nm, "ytitle", st.upper())
                    loaded.append(nm)

            # ----- delete the unneeded temporary tplot variables -----
            # clean up the remaining niprtmp_* (mlat_center/mlon_center/time_image etc.)
            _delete_remaining_tmp(prefix_tmp)

    return loaded


def _get_ndarray(var):
    """Return an NRV variable as an ndarray, or None if absent."""
    d = get_data(var)
    if d is None:
        return None
    return np.asarray(d, dtype=np.float32)


def _epoch_two_point(epoch_var, image_var):
    """Return a 2-element time [t0, t_last] in unix seconds for the derived variables.

    epoch_image (CDF_EPOCH, ms) is converted via cdfepoch.unixtime(time_double(...)).
    Falls back to the endpoints of image_raw's times if it cannot be read.
    """
    ep = get_data(epoch_var)
    if ep is not None:
        ep = np.asarray(ep)
        if ep.size >= 1:
            return np.asarray(cdfepoch.unixtime(time_double([ep[0], ep[-1]])))
    img = get_data(image_var)
    if img is not None and hasattr(img, "times") and len(img.times) >= 1:
        return np.array([img.times[0], img.times[-1]], dtype=float)
    return None


def _delete_remaining_tmp(prefix_tmp):
    """Delete the remaining niprtmp_* temporary variables."""
    from pyspedas import tnames
    for v in tnames(prefix_tmp + "*"):
        store_data(v, delete=True)
