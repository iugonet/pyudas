"""Load function for Kyushu University GCM (Kyushu GCM) simulation data.

Distributed by the NIPR server ``http://iugonet0.nipr.ac.jp/data/`` (plain HTTP,
no authentication). The files are CDF (not netCDF), so they are read with the
shared ``load()`` (cdf_to_tplot).

CDF structure (confirmed with KyushuGCM_j3_T_20100101_v01.cdf):
  zVariables:
    Epoch_1hr        (24,)             CDF_EPOCH  hourly (beginning of interval)
    temperature      (24, 64,128,150)  float32    main data (datatype=T)
        DEPEND_0=Epoch_1hr DEPEND_1=glat DEPEND_2=glon DEPEND_3=alt
        FILLVAL=-1E+31
    glat             (64,)   float32  geographic latitude  [degree]  87.9..-87.9 (descending)
    glon             (128,)  float32  geographic longitude [degree]  0..357.1875
    pressure         (150,)  float32  pressure [hPa]  997.5..1.0e-9 (descending, top is upper atmosphere)
    alt              (150,)  float32  altitude. FIELDNAM is "altitude in km" but
        the values are in m (252.7..476743.7 -> /1000 gives 0.25..476.7 km), so /1000 is applied.
    label_/unit_*    metadata (scalar strings)
  The main data variable name depends on datatype (T=temperature, U=uwind,
  V=vwind, W=wwind etc.). Rather than hard-coding the name, the single tplot
  variable returned by cdf_to_tplot with a multidimensional .y (the
  record-varying data variable) is picked as the main data. glat/glon/pressure/
  alt are non-record-varying (NRV), so get_data returns them as bare ndarrays.

Axis order (important to match the original UDAS output):
  the cdf_to_tplot y is (time, glat, glon, alt_index) = (24, 64, 128, 150), the
  same order as the original, so
    store_data, 'kyushugcm_'+dt, data={x:d.x, y:d.y, v1:glat, v2:glon, v3:v3tmp}
  is reproduced as-is and y[i,a,b,c]==y[i,a,b,c] holds (verified).

v3 selection:
  altitude=True  -> v3 = alt/1000 (m->km).
  altitude=False -> v3 = pressure (hPa). (default)
  Note: yrange/ylog/spec are only set when the data are reduced to 1D in the
  original (not on the 4D main variable), so only ztitle/ytitle are set here.

fill value -1e31 -> NaN: cleared with clip(-1e5, 1e5).
"""
import numpy as np

from pyspedas import get_data, store_data, options, clip, tnames

from iugonet.load import load

DATATYPE_ALL = ["T", "U", "V", "W"]
# only j3 has actual data on the server
CALMETHOD_ALL = ["j3", "s1", "s2", "s3", "d1", "d2", "d3"]

REMOTE_DATA_DIR = "http://iugonet0.nipr.ac.jp/data/"

# temporary prefix
PREFIX_TMP = "niprtmp_"

# options per datatype (ztitle/ytitle, kept exact)
_OPTIONS = {
    "T": ("Temperature [K]", "Kyushu GCM!CTemperature!C"),
    "U": ("Zonal Wind [m/s]", "Kyushu GCM!CZonal Wind!C"),
    "V": ("Meridional Wind [m/s]", "Kyushu GCM!CMeridional Wind!C"),
    "W": ("Vertical Wind [m/s]", "Kyushu GCM!CVertical Wind!C"),
}


def _normalize_datatype(value):
    """Normalize a datatype input (str/list, 'all' accepted) to a list of valid values.

    The values are uppercased, with the input order kept and duplicates removed.
    'all' is expanded to every datatype.
    """
    if isinstance(value, str):
        items = value.upper().split()
    else:
        items = [str(v).upper() for v in value]
    if "ALL" in items:
        return list(DATATYPE_ALL)
    out = []
    for it in items:
        if it in DATATYPE_ALL and it not in out:
            out.append(it)
    return out


def _normalize_calmethod(value):
    """Normalize calmethod to a single valid value (only the first one is used)."""
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(v).lower() for v in value]
    for it in items:
        if it in CALMETHOD_ALL:
            return it
    return None


def _print_ror(data_var):
    """Print the Rules of the Road / PI information.

    A failure to read the global attributes does not stop the data loading.
    """
    try:
        meta = get_data(data_var, metadata=True)
        gatt = meta["CDF"]["GATT"]
        print("**************************************************************************")
        print(gatt["Logical_source_description"])
        print("")
        print(f'PI: {gatt["PI_name"]}')
        print(f'Affiliations: {gatt["PI_affiliation"]}')
        print("")
        print("Rules of the Road for Kyushu GCM Simulation Data:")
        print("")
        print(gatt.get("Rules_of_use", ""))
        print(f'{gatt.get("LINK_TEXT", "")} {gatt.get("HTTP_LINK", "")}')
        print("**************************************************************************")
    except Exception:
        print("printing PI info and rules of the road failed")


def _find_data_var(tmp_vars):
    """Return the single main data variable among the niprtmp_* created by cdf_to_tplot.

    For the main data (record-varying, multidimensional) get_data returns a
    namedtuple (with .y). The NRV glat/glon/pressure/alt and metadata come back
    as bare ndarrays, so the variable that "has .y and a y of 2+ dimensions" is
    the main data (temperature/uwind/...), found without hard-coding its name.
    """
    for v in tmp_vars:
        d = get_data(v)
        if d is not None and hasattr(d, "y"):
            y = np.asarray(d.y)
            if y.ndim >= 2:
                return v
    return None


def _get_ndarray(var):
    """Return an NRV variable as an ndarray, or None if absent."""
    d = get_data(var)
    if d is None:
        return None
    if hasattr(d, "y"):
        d = d.y
    return np.asarray(d)


def _delete_remaining_tmp():
    """Delete the remaining niprtmp_* temporary variables."""
    for v in tnames(PREFIX_TMP + "*"):
        store_data(v, delete=True)


def kyushugcm(
    trange=["2010-01-01", "2010-01-02"],
    datatype="all",
    calmethod="j3",
    altitude=False,
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    ror=True,
    suffix="",
):
    """Load Kyushu University GCM (Kyushu GCM) simulation data.

    Distributed by NIPR (iugonet0.nipr.ac.jp, plain HTTP, no authentication).
    One daily file in CDF format; note that each file is large (~100 MB).

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Daily files (YYYYMMDD).
        Default: ['2010-01-01', '2010-01-02']
    datatype : str or list
        Output physical quantity. Valid options: 'T' (temperature [K]),
        'U' (zonal wind [m/s]), 'V' (meridional wind [m/s]),
        'W' (vertical wind [m/s]), 'all' (all of them). A space-separated string
        ('T U') or a list are both accepted.
        Default: 'all'
    calmethod : str
        Calculation method option. Valid options: j3 s1 s2 s3 d1 d2 d3; only the
        first valid value is used. Currently only 'j3' (JRA boundary condition,
        altitude grid 150) has actual data on the server.
        Default: 'j3'
    altitude : bool
        If True, the third axis (v3) is altitude [km] (the CDF alt[m] divided by
        1000); if False, it is pressure [hPa] (the CDF pressure).
        Default: False
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables
        (with the tags {x,y,v1,v2,v3}).
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
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
        List of tplot variables created (``kyushugcm_{T,U,V,W}``). Each variable
        has
          y  = a 4D array (time, glat, glon, alt_or_pressure_index),
          v1 = glat [degree] (64), v2 = glon [degree] (128),
          v3 = altitude [km] (altitude=True) or pressure [hPa] (default) (150).
        Empty list if no data were loaded. If ``downloadonly`` is set, the list
        of downloaded file paths is returned; if ``notplot`` is set, a
        dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.kyushugcm(trange=['2010-01-01', '2010-01-02'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    datatypes = _normalize_datatype(datatype)
    cm = _normalize_calmethod(calmethod)
    if not datatypes or cm is None:
        return {} if notplot else []

    loaded = {} if notplot else []
    dl_files = []

    for dt in datatypes:
        pathformat = (
            f"gcm/{cm}/{dt}/%Y/"
            f"KyushuGCM_{cm}_{dt}_%Y%m%d_v??.cdf"
        )

        res = load(
            trange=trange,
            pathformat=pathformat,
            file_res=24 * 3600.0,
            remote_path=REMOTE_DATA_DIR,
            local_path="nipr/",
            prefix=PREFIX_TMP,
            get_support_data=True,   # glat/glon/pressure/alt have VAR_TYPE=support_data
            get_metadata=ror,
            downloadonly=downloadonly,
            notplot=notplot,
            no_update=no_update,
            time_clip=time_clip,
        )

        if downloadonly:
            dl_files += res
            continue

        if notplot:
            # format into the {x,y,v1,v2,v3} tags and return
            _store_notplot(res, dt, altitude, loaded, suffix)
            _delete_remaining_tmp()
            continue

        if not res:
            print(f"No tplot var loaded for {dt}.")
            _delete_remaining_tmp()
            continue

        tmp_vars = tnames(PREFIX_TMP + "*")
        data_var = _find_data_var(tmp_vars)
        if data_var is None:
            print(f"No tplot var loaded for {dt}.")
            _delete_remaining_tmp()
            continue

        if ror:
            _print_ror(data_var)

        # ----- get the main data and coordinates -----
        d = get_data(data_var)
        glat = _get_ndarray(PREFIX_TMP + "glat")
        glon = _get_ndarray(PREFIX_TMP + "glon")
        if altitude:
            alt = _get_ndarray(PREFIX_TMP + "alt")
            v3 = alt / 1000.0 if alt is not None else None  # m --> km
        else:
            v3 = _get_ndarray(PREFIX_TMP + "pressure")

        # ----- build kyushugcm_{dt} -----
        name = "kyushugcm_" + dt + suffix
        store_data(
            name,
            data={"x": np.asarray(d.times), "y": np.asarray(d.y),
                  "v1": glat, "v2": glon, "v3": v3},
        )

        # ----- fill value -1e31 -> NaN -----
        clip(name, -1e5, 1e5)

        # ----- options -----
        ztitle, ytitle = _OPTIONS.get(dt, ("", ""))
        options(name, "ztitle", ztitle)
        options(name, "ytitle", ytitle)

        loaded.append(name)

        # clean up the remaining temporaries (glat/glon/pressure/alt/Epoch_1hr/label_/unit_)
        _delete_remaining_tmp()

    if downloadonly:
        return sorted(set(dl_files))

    return loaded


def _store_notplot(res, dt, altitude, loaded, suffix):
    """Build and store a {x,y,v1,v2,v3} dictionary when notplot=True.

    res is the {varname: {...}} dictionary returned by cdf_to_tplot(notplot=True).
    The main data variable (multidimensional y) is selected, and glat/glon/
    (alt|pressure) are assigned to v1/v2/v3.
    """
    def _arr(key):
        e = res.get(key)
        if e is None:
            return None
        a = e.get("y", None)
        return None if a is None else np.asarray(a)

    # find the main data variable (y.ndim>=2)
    data_key = None
    for k, e in res.items():
        a = e.get("y", None)
        if a is not None and np.asarray(a).ndim >= 2:
            data_key = k
            break
    if data_key is None:
        return

    e = res[data_key]
    glat = _arr(PREFIX_TMP + "glat")
    glon = _arr(PREFIX_TMP + "glon")
    if altitude:
        alt = _arr(PREFIX_TMP + "alt")
        v3 = alt / 1000.0 if alt is not None else None
    else:
        v3 = _arr(PREFIX_TMP + "pressure")

    x = np.asarray(e.get("x"))
    y = np.asarray(e.get("y"))
    # fill value -> NaN (equivalent to clip)
    y = np.where((y < -1e5) | (y > 1e5), np.nan, y)
    name = "kyushugcm_" + dt + suffix
    loaded[name] = {"x": x, "y": y, "v1": glat, "v2": glon, "v3": v3}
