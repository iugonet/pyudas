"""Load function for the MU radar (middle and upper atmosphere, Shigaraki, Japan) data.

A dispatcher that selects the observation mode via ``datatype``:

- ``troposphere`` : troposphere/lower stratosphere (standard observation).
  Three wind components plus per-beam pwr/wdt/dpl/pn.
- ``mesosphere``  : mesosphere echo (pwr/wdt/dpl/pn, level org/scr) plus
  1-hour averaged wind (uwnd/vwnd/wwnd).
- ``ionosphere``  : incoherent-scatter drift (1D) + pwr (2D) + teti (Ti/Te, 2D).
- ``meteor``      : meteor wind (uwnd/vwnd/uwndsig/vwndsig/mwnum, per parameter).
- ``rass``        : RASS (uwnd/vwnd/wwnd/temp, CSV).
- ``fai``         : field-aligned irregularities (pwr/wdt/dpl/snr/pn, per parameter).

The data are not CDF, so the common ``load()`` (cdf_to_tplot) cannot be used.
The .nc files are fetched with pyspedas ``download`` and parsed directly with
netCDF4 before calling ``store_data`` (the same pattern as meteor_rish.py /
ear.py). The server is www.rish.kyoto-u.ac.jp.

netCDF structure (confirmed from a sample troposphere file):
  dimensions: beam(5), range(118), time(144)
  time     (time,)          units='seconds since YYYY-M-DD HH:MM:SS +09:00' (LT)
  range, height_vw, height_mwzw (range,) [km]; height (beam,range) [km]
  zwind, mwind, vwind (time,range) [m/s]     (variable names are swapped, see below)
  pwr, width, dpl     (beam,time,range)       ; pnoise (beam,time) [dB]
  Fill value = 1e10 -> NaN. No value clipping (troposphere is not clipped).

Important variable correspondence for troposphere:
  netCDF ``zwind`` -> zonal wind uwnd (iug_mu_trop_uwnd, v=height_mwzw)
  netCDF ``mwind`` -> meridional wind vwnd (iug_mu_trop_vwnd, v=height_mwzw)
  netCDF ``vwind`` -> vertical wind wwnd (iug_mu_trop_wwnd, v=height_vw)
These swapped names are preserved to match the original UDAS output.

Notable behaviors specific to this dataset:
  - LT is +09:00, so the file-fetch window is shifted by 9 h.
  - Height right-justification: each file's (time, range) data is right-justified
    into a fixed 120-point array with ``st_num=120-range``, leaving the leading
    st_num points NaN (e.g. with 118 range points the first 2 points are NaN).
  - pwr/wdt/dpl/pn use ``height2 = height_vw`` for their height coordinate.
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, time_string, dailynames, download
from pyspedas.tplot_tools import degap

from iugonet.config import CONFIG
# Reuse the gap-filling (degap) and median helpers from the EAR FAI module so
# the gap handling matches the original output. ear.py is not modified
# (imported only).
from iugonet.ground.ear import _idl_xdegap, _idl_median

DATATYPE_ALL = ["troposphere", "mesosphere", "ionosphere", "meteor", "rass", "fai"]

# ------------------------------------------------------------------
# Remote server per observation mode. The www host responds to direct file
# GETs with 200 after the http->https 302 redirect (directory listing returns
# 403, but download fetches individual files so this is not an issue).
# ------------------------------------------------------------------
_MESO_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/mesosphere/data/netcdf/"
_METEOR_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/meteor/data/netcdf/"
_IONO_DRIFT_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/isdata/data/drift/netcdf/"
_IONO_PWR_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/isdata/data/pwr/netcdf/"
_IONO_TETI_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/isdata/data/teti/netcdf/"
_RASS_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/rass/data/csv/"
_FAI_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/fai/data/nc/"

# Levels for the mesosphere mode.
_MESO_LEVEL_ALL = ["org", "scr"]
# Parameters for the meteor mode.
_METEOR_PARAM_ALL = ["h1t60min00", "h1t60min30", "h2t60min00", "h2t60min30"]
# Parameters for the rass mode.
_RASS_PARAM_ALL = ["uwnd", "vwnd", "wwnd", "temp"]
# All FAI parameters.
_FAI_PARAM_ALL = (
    "ie2e4b ie2e4c ie2e4d ie2rea ie2mya ie2myb ie2rta ie2trb iecob3 "
    "ied101 ied103 ied108 ied110 ied201 ied202 ied203 iedb4a iedb4b "
    "iedb4c iedc4a iedc4b iedc4c iede4a iede4b iede4c iede4d iedp01 "
    "iedp02 iedp03 iedp08 iedp10 iedp11 iedp12 iedp13 iedp1s iedpaa "
    "iedpbb iedpcc iedpdd iedpee iedpff iedpgg iedphh iedpii iedpjj "
    "iedpkk iedpl2 iedpll iedpmm iedptt iedpyy iedpzz ieewb5 ieimga "
    "ieimgb ieimgm ieimgt ieis01 iefai1 iefdi2 ieggmt iemb5i iemcb3 "
    "iemdb3 iemdb5 iemdc3 iemy3a iemy3b iemy3c iemyb5 iensb5 iepbr1 "
    "iepbr2 iepbr3 iepbr4 iepbr5 iepbrt ieper1 ieper2 ieper3 ieper4 "
    "ieper5 ieper6 ieper7 ieper8 ieps3a ieps3b ieps3c ieps4a ieps4b "
    "ieps4c ieps4d ieps4e ieps5a ieps5b ieps5c ieps6a ieps6b iepsb3 "
    "iepsb4 iepsb5 iepsi1 iepsi5 iepsit iesp01 iess01 iess02 iess03 "
    "iess04 iess05 iess2l iess3l iess4l iess8c iessb5 iesst2 iesst3 "
    "iet101 iet102 ietest ietst2 ieto02 ieto03 ieto16 ietob3 ietob4 "
    "ietob5 iey4ch iey4ct ieyo4a ieyo4b ieyo4c ieyo4d ieyo4e ieyo4f "
    "ieyo4g ieyo5a ieyo5b ieyo5c ieyo5d ieyo5e ieyo5f ieyo5g ieyo5m "
    "ifco02 ifco03 ifco04 ifco16 if5bd1 if5bd2 if5bd3 if5bd4 if5bd5 "
    "if5be1 if5be2 if5be3 if5be4 if5be5 ifchk1 ifdp00 ifdp01 ifdp02 "
    "ifdp03 ifdp0a ifdp0b ifdp0c ifdp0d ifdp1u ifdp1s ifdp1t ifdpll "
    "ifdq01 ifdq02 ifim16 ifmb16 ifmc16 ifmd16 ifmf16 ifmy01 ifmy02 "
    "ifmy03 ifmy04 ifmy05 ifmy99 ifmyc1 ifmyc2 ifmyc3 ifmyc4 ifmyc5 "
    "ifmyc6 ifmyc7 ifmyca ifmycb ifmyt1 ifmyt2 ifmyt3 ifmyt4 ifmyt5 "
    "ifmyu1 ifmyu2 ifmyu3 ifmyu4 ifmyu5 ifmyv1 ifpsi1 ifpsit ifss02 "
    "iftes1 iftes2 iftes3 iftes5 iftes6 iftes7 iftes8 ifts01 ifts02 "
    "ifts03 ifts04 ifts05 ifts06 ifts07"
).split()

# MU = Shigaraki. time.units is referenced to LT (+09:00); the LT->UT fetch
# window shift is 9 h.
_LT_SHIFT = 9.0 * 3600.0
_MISSING = 1e10

# Right-justified fixed size (data_point=120).
_DATA_POINT = 120

_TROP_REMOTE = "http://www.rish.kyoto-u.ac.jp/mu/data/data/ver01.0807_1.02/"

# For dates in this list the netCDF height_vw/height_mwzw are used; for any
# other date the hard-coded heights (height_v/height_zm) below are used.
_F_LIST = ["19860317", "19860318", "19860319", "19860320", "19860321", "19910209"]

# Default height_mwzw (120 points).
_HEIGHT_ZM = np.array([
    1.998, 2.145, 2.293, 2.441, 2.589, 2.736, 2.884, 3.032, 3.179, 3.327,
    3.475, 3.623, 3.770, 3.918, 4.066, 4.213, 4.361, 4.509, 4.657, 4.804,
    4.952, 5.100, 5.248, 5.395, 5.543, 5.691, 5.838, 5.986, 6.134, 6.282,
    6.429, 6.577, 6.725, 6.872, 7.020, 7.168, 7.316, 7.463, 7.611, 7.759,
    7.907, 8.054, 8.202, 8.350, 8.497, 8.645, 8.793, 8.941, 9.088, 9.236,
    9.384, 9.531, 9.679, 9.827, 9.975, 10.122, 10.270, 10.418, 10.565,
    10.713, 10.861, 11.009, 11.156, 11.304, 11.452, 11.600, 11.747, 11.895,
    12.043, 12.190, 12.338, 12.486, 12.634, 12.781, 12.929, 13.077, 13.224,
    13.372, 13.520, 13.668, 13.815, 13.963, 14.111, 14.259, 14.406, 14.554,
    14.702, 14.849, 14.997, 15.145, 15.293, 15.440, 15.588, 15.736, 15.883,
    16.031, 16.179, 16.327, 16.474, 16.622, 16.770, 16.917, 17.065, 17.213,
    17.361, 17.508, 17.656, 17.804, 17.952, 18.099, 18.247, 18.395, 18.542,
    18.690, 18.838, 18.986, 19.133, 19.281, 19.429, 19.576,
], dtype=np.float64)

# Default height_vw (120 points).
_HEIGHT_V = np.array([
    2.025, 2.175, 2.325, 2.475, 2.625, 2.775, 2.925, 3.075, 3.225, 3.375,
    3.525, 3.675, 3.825, 3.975, 4.125, 4.275, 4.425, 4.575, 4.725, 4.875,
    5.025, 5.175, 5.325, 5.475, 5.625, 5.775, 5.925, 6.075, 6.225, 6.375,
    6.525, 6.675, 6.825, 6.975, 7.125, 7.275, 7.425, 7.575, 7.725, 7.875,
    8.025, 8.175, 8.325, 8.475, 8.625, 8.775, 8.925, 9.075, 9.225, 9.375,
    9.525, 9.675, 9.825, 9.975, 10.125, 10.275, 10.425, 10.575, 10.725,
    10.875, 11.025, 11.175, 11.325, 11.475, 11.625, 11.775, 11.925, 12.075,
    12.225, 12.375, 12.525, 12.675, 12.825, 12.975, 13.125, 13.275, 13.425,
    13.575, 13.725, 13.875, 14.025, 14.175, 14.325, 14.475, 14.625, 14.775,
    14.925, 15.075, 15.225, 15.375, 15.525, 15.675, 15.825, 15.975, 16.125,
    16.275, 16.425, 16.575, 16.725, 16.875, 17.025, 17.175, 17.325, 17.475,
    17.625, 17.775, 17.925, 18.075, 18.225, 18.375, 18.525, 18.675, 18.825,
    18.975, 19.125, 19.275, 19.425, 19.575, 19.725, 19.875,
], dtype=np.float64)

_UNIT_SCALE = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0, "days": 86400.0}


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order preserved, deduplicated)."""
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


def _parse_time_units(units):
    """Parse a time.units '<unit> since YYYY-M-DD HH:MM:SS +TZ:TZ' string into (base_unix, tz_sec, scale).

    unix = time*scale + base_unix - tz_sec. A single-digit month ('3') is
    accepted by time_double.
    """
    parts = units.split()
    scale = _UNIT_SCALE.get(parts[0].lower(), 1.0)
    base_unix = float(time_double(parts[2] + "/" + parts[3]))
    tz_sec = 0.0
    if len(parts) >= 5 and parts[4]:
        tzstr = parts[4]
        sign = 1.0
        if tzstr[0] in "+-":
            sign = -1.0 if tzstr[0] == "-" else 1.0
            tzstr = tzstr[1:]
        hh, _, mm = tzstr.partition(":")
        tz_sec = sign * (int(hh) * 3600.0 + (int(mm) * 60.0 if mm else 0.0))
    return base_unix, tz_sec, scale


def _nan_missing(arr):
    """Replace the fill value 1e10 with NaN and return a float64 array."""
    a = np.asarray(np.ma.filled(np.ma.asarray(arr), fill_value=_MISSING), dtype=np.float64)
    return np.where(a == _MISSING, np.nan, a)


def _rj2d(arr2d):
    """Right-justify (time, range) into (time, 120), leaving the leading st_num=120-range points NaN.

    This right-justification is preserved to match the original output.
    """
    nt, nr = arr2d.shape
    st = _DATA_POINT - nr
    out = np.full((nt, _DATA_POINT), np.nan, dtype=np.float64)
    if st >= 0:
        out[:, st:st + nr] = arr2d
    else:
        # rare case where range exceeds 120: keep the last 120 points
        out[:, :] = arr2d[:, -_DATA_POINT:]
    return out


def _rj_height(h, npoint=_DATA_POINT):
    """Pad a height array (range points, e.g. 118) to 120 points to match the right-justified data (120 columns).

    Data column j (>=st_num) corresponds to real data point j-st_num, whose
    height is h[j-st_num]. The leading st_num columns (the right-justified NaN
    padding) are assigned heights extrapolated below h[0] at the same spacing,
    so the height coordinate v has the same length (120) as the data columns.
    This lets pyspedas draw the spectrogram (spec=1) against a height axis. The
    heights do not appear in the data values, so they do not affect the
    bit-for-bit comparison.
    """
    h = np.asarray(h, dtype=np.float64).ravel()
    nr = h.size
    st = npoint - nr
    if st <= 0:
        return h[-npoint:] if nr > npoint else h
    dh = (h[1] - h[0]) if nr >= 2 else 1.0
    pre = h[0] + dh * np.arange(-st, 0)        # [h0-st*dh, ..., h0-dh]
    return np.concatenate([pre, h])


def _read_mu_trop(path):
    """Read one MU troposphere netCDF file; return UT times and the data arrays.

    The data arrays are right-justified to (time, 120). pwr/wdt/dpl are
    (beam, time, 120); pn is (beam, time). The height arrays are kept as in the
    netCDF (range count, usually 118). ``date`` (str 'YYYYMMDD') is used for the
    f_list test. Returns a dict, or None.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        beam = np.asarray(ds.variables["beam"][:]).ravel()
        # 'YYYYMMDD' string compared against f_list
        date_str = str(int(np.asarray(ds.variables["date"][:]).ravel()[0]))

        # wind: right-justify netCDF (time, range) into (time, 120).
        # swapped names: zwind->uwnd, mwind->vwnd, vwind->wwnd
        uwnd = _rj2d(_nan_missing(ds.variables["zwind"][:]))
        vwnd = _rj2d(_nan_missing(ds.variables["mwind"][:]))
        wwnd = _rj2d(_nan_missing(ds.variables["vwind"][:]))

        # beam arrays: right-justify netCDF (beam, time, range) per beam -> (beam, time, 120)
        pwr_raw = _nan_missing(ds.variables["pwr"][:])      # (beam, time, range)
        wdt_raw = _nan_missing(ds.variables["width"][:])
        dpl_raw = _nan_missing(ds.variables["dpl"][:])
        pwr = np.stack([_rj2d(pwr_raw[l]) for l in range(beam.size)], axis=0)
        wdt = np.stack([_rj2d(wdt_raw[l]) for l in range(beam.size)], axis=0)
        dpl = np.stack([_rj2d(dpl_raw[l]) for l in range(beam.size)], axis=0)

        return {
            "time": unix_time,
            "date": date_str,
            "beam": beam,
            "height_mwzw": np.asarray(ds.variables["height_mwzw"][:], dtype=np.float64).ravel(),
            "height_vw": np.asarray(ds.variables["height_vw"][:], dtype=np.float64).ravel(),
            "uwnd": uwnd,
            "vwnd": vwnd,
            "wwnd": wwnd,
            "pwr": pwr,
            "wdt": wdt,
            "dpl": dpl,
            "pn": _nan_missing(ds.variables["pnoise"][:]),   # (beam, time)
        }
    finally:
        ds.close()


def _concat(arrs, axis=0):
    return np.concatenate(arrs, axis=axis)


def _win_trange(t0, t1):
    """Return the daily-file-name trange [t0, t1+9h].

    The end is extended by +9 h so that LT (+09) files are reliably included up
    to the end of the UT trange.
    """
    return [time_string(t0), time_string(t1 + _LT_SHIFT)]


# ==================================================================
# mesosphere (echo: pwr/wdt/dpl/pn)
# ==================================================================
def _read_mu_meso(path, level):
    """Read one MU mesosphere echo netCDF file.

    netCDF dims: time, range, beam. pwr/wdt/dpl/if_cond are (beam,range,time);
    pnoise is (beam,time). This function returns each beam as a (time, range)
    array (the transpose of the netCDF slice), stacked over beams.

    When level=='scr', points with if_cond>4 are set to NaN ('org' does
    nothing). No 1e10-style fill replacement is applied (echo uses only the
    if_cond screening).
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        beam = np.asarray(ds.variables["beam"][:]).ravel()
        nbeam = beam.size
        # (beam, range, time) -> transpose each beam to (time, range)
        pwr_raw = np.asarray(ds.variables["pwr"][:], dtype=np.float64)
        wdt_raw = np.asarray(ds.variables["wdt"][:], dtype=np.float64)
        dpl_raw = np.asarray(ds.variables["dpl"][:], dtype=np.float64)
        if level == "scr":
            ifc = np.asarray(ds.variables["if_cond"][:])    # (beam, range, time)
            bad = ifc > 4
            pwr_raw = np.where(bad, np.nan, pwr_raw)
            wdt_raw = np.where(bad, np.nan, wdt_raw)
            dpl_raw = np.where(bad, np.nan, dpl_raw)
        pwr = np.stack([pwr_raw[l].T for l in range(nbeam)], axis=0)   # (beam,time,range)
        wdt = np.stack([wdt_raw[l].T for l in range(nbeam)], axis=0)
        dpl = np.stack([dpl_raw[l].T for l in range(nbeam)], axis=0)
        pn = np.asarray(ds.variables["pnoise"][:], dtype=np.float64)   # (beam, time)

        return {
            "time": unix_time,
            "beam": beam,
            "height_v": np.asarray(ds.variables["height_v"][:], dtype=np.float64).ravel(),
            "height_mz": np.asarray(ds.variables["height_mz"][:], dtype=np.float64).ravel(),
            "pwr": pwr,
            "wdt": wdt,
            "dpl": dpl,
            "pn": pn,
        }
    finally:
        ds.close()


def _load_mu_meso(level, trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU mesosphere echo data and create tplot variables.

    Per level: iug_mu_meso_{pwr,wdt,dpl}{1-5}_{level} + _pn{1-5}_{level}.
    Heights: beam0=height_v, beam1-4=height_mz.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    file_format = "%Y/%Y%m/%Y%m%d.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "mesosphere", "nc")
    files = download(remote_file=remote_names, remote_path=_MESO_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))
    if downloadonly:
        return out_files

    loaded = {} if notplot else []
    for lev in level:
        recs = [d for d in (_read_mu_meso(f, lev) for f in out_files) if d is not None]
        if not recs:
            continue
        last = recs[-1]
        beam = last["beam"]
        nbeam = beam.size
        # height for beam 0 = height_v, beams 1..4 = height_mz
        height_v = last["height_v"]
        height_mz = last["height_mz"]

        mu_time = _concat([d["time"] for d in recs])
        pwr = _concat([d["pwr"] for d in recs], axis=1)   # (beam,time,range)
        wdt = _concat([d["wdt"] for d in recs], axis=1)
        dpl = _concat([d["dpl"] for d in recs], axis=1)
        pn = _concat([d["pn"] for d in recs], axis=1)     # (beam,time)

        tmask = (mu_time >= t0) & (mu_time <= t1)
        if not np.any(tmask):
            continue
        ct = mu_time[tmask]

        # The echo variables (pwr/wdt/dpl/pn) are degapped together with the
        # wind variables in the original processing, so the default-dt
        # (=median(diff)) xdegap is applied here to each echo variable to match
        # the original output.
        for l in range(nbeam):
            bn = str(int(round(beam[l])) + 1)
            hgt = height_v if l == 0 else height_mz
            for kind, arr, zt in (("pwr", pwr, "!C[dB]"), ("wdt", wdt, "!C[m/s]"),
                                  ("dpl", dpl, "!C[m/s]")):
                name = "iug_mu_meso_" + kind + bn + "_" + lev + suffix
                dt, dy = _idl_xdegap(ct, arr[l][tmask, :])
                if notplot:
                    loaded[name] = {"x": dt, "y": dy, "v": hgt}
                else:
                    store_data(name, data={"x": dt, "y": dy, "v": hgt})
                    options(name, "spec", 1)
                    options(name, "ytitle", "MUR-meso!CHeight!C[km]")
                    options(name, "ztitle", kind + bn + "-" + lev + zt)
                    loaded.append(name)
            pnname = "iug_mu_meso_pn" + bn + "_" + lev + suffix
            dt, dy = _idl_xdegap(ct, pn[l][tmask])
            if notplot:
                loaded[pnname] = {"x": dt, "y": dy}
            else:
                store_data(pnname, data={"x": dt, "y": dy})
                options(pnname, "ytitle", "MUR-meso!Cpn" + bn + "!C[dB]")
                loaded.append(pnname)

    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# mesosphere wind (1h avg)
# ==================================================================
def _read_mu_meso_wind(path, level):
    """Read one MU mesosphere wind netCDF file.

    uwnd/vwnd/wwnd are netCDF (range,time) -> (time,range). Fill value 999.0 ->
    NaN. Flag screening also applies: org->flg=2, scr->flg=1; points with
    flg_* >= flg are set to NaN.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        # netCDF (range, time) -> (time, range)
        uwnd = np.asarray(ds.variables["uwnd"][:], dtype=np.float64).T
        vwnd = np.asarray(ds.variables["vwnd"][:], dtype=np.float64).T
        wwnd = np.asarray(ds.variables["wwnd"][:], dtype=np.float64).T
        fu = np.asarray(ds.variables["flg_uwnd"][:]).T
        fv = np.asarray(ds.variables["flg_vwnd"][:]).T
        fw = np.asarray(ds.variables["flg_wwnd"][:]).T

        uwnd = np.where(uwnd == 999.0, np.nan, uwnd)
        vwnd = np.where(vwnd == 999.0, np.nan, vwnd)
        wwnd = np.where(wwnd == 999.0, np.nan, wwnd)
        flg = 2 if level == "org" else 1
        uwnd = np.where(fu >= flg, np.nan, uwnd)
        vwnd = np.where(fv >= flg, np.nan, vwnd)
        wwnd = np.where(fw >= flg, np.nan, wwnd)

        return {
            "time": unix_time,
            "height_v": np.asarray(ds.variables["height_v"][:], dtype=np.float64).ravel(),
            "height_mz": np.asarray(ds.variables["height_mz"][:], dtype=np.float64).ravel(),
            "uwnd": uwnd,
            "vwnd": vwnd,
            "wwnd": wwnd,
        }
    finally:
        ds.close()


def _load_mu_meso_wind(level, trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU mesosphere wind data and create tplot variables.

    iug_mu_meso_{uwnd,vwnd}_{level} use height_mz; wwnd uses height_v.
    Degapped with the default dt.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    file_format = "%Y/%Y%m/%Y%m%d.wnd.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "mesosphere", "nc")
    files = download(remote_file=remote_names, remote_path=_MESO_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))
    if downloadonly:
        return out_files

    loaded = {} if notplot else []
    for lev in level:
        recs = [d for d in (_read_mu_meso_wind(f, lev) for f in out_files) if d is not None]
        if not recs:
            continue
        last = recs[-1]
        height_v = last["height_v"]
        height_mz = last["height_mz"]
        mu_time = _concat([d["time"] for d in recs])
        uwnd = _concat([d["uwnd"] for d in recs])
        vwnd = _concat([d["vwnd"] for d in recs])
        wwnd = _concat([d["wwnd"] for d in recs])

        tmask = (mu_time >= t0) & (mu_time <= t1)
        if not np.any(tmask):
            continue
        ct = mu_time[tmask]

        for kind, arr, hgt, zt in (
                ("uwnd", uwnd, height_mz, "Zonal wind!C[m/s]"),
                ("vwnd", vwnd, height_mz, "Meridional wind!C[m/s]"),
                ("wwnd", wwnd, height_v, "Vertical wind!C[m/s]")):
            name = "iug_mu_meso_" + kind + "_" + lev + suffix
            y = arr[tmask, :]
            # degap with the default dt = median(diff)
            dt, dy = _idl_xdegap(ct, y)
            if notplot:
                loaded[name] = {"x": dt, "y": dy, "v": hgt}
            else:
                store_data(name, data={"x": dt, "y": dy, "v": hgt})
                options(name, "spec", 1)
                options(name, "ytitle", "MUR-meso!CHeight!C[km]")
                options(name, "ztitle", zt)
                loaded.append(name)

    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# meteor wind
# ==================================================================
def _read_mu_meteor(path):
    """Read one MU meteor netCDF file.

    netCDF dims: time, range, station(1). uwind/vwind/sig_*/num are
    (time,range,station). This function returns (time, range) arrays (station 0).
    Fill value -9999 -> NaN. Height = range/1000 [km].
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        rng = np.asarray(ds.variables["range"][:], dtype=np.float64).ravel()
        height = rng / 1000.0   # height = range/1000 [km]

        def _rd(name):
            a = np.asarray(ds.variables[name][:], dtype=np.float64)  # (time,range,station)
            a = a[:, :, 0]                                            # station 0 -> (time,range)
            return np.where(a == -9999.0, np.nan, a)

        return {
            "time": unix_time,
            "height": height,
            "uwnd": _rd("uwind"),
            "vwnd": _rd("vwind"),
            "uwndsig": _rd("sig_uwind"),
            "vwndsig": _rd("sig_vwind"),
            "mwnum": _rd("num"),
        }
    finally:
        ds.close()


def _load_mu_meteor(parameters, length, trange, no_update, downloadonly,
                    ror, suffix, notplot):
    """Read MU meteor data and create tplot variables.

    The server subdirectory is param[:2]+'km_'+param[2:] (e.g.
    h1t60min00 -> h1km_t60min00). Variables:
    iug_mu_meteor_{uwnd,vwnd,uwndsig,vwndsig,mwnum}_<param>.
    Degapped with dt=3600 s, then clipped (uwnd/vwnd -400..400, sig 0..800,
    mwnum 0..1200). Height labels are in [km].
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)

    loaded = {} if notplot else []
    dl_files = []

    for param in parameters:
        site_dir = param[:2] + "km_" + param[2:]
        if length == "1_month":
            file_format = "%Y/W%Y%m." + param + ".nc"
        else:
            file_format = "%Y/W%Y%m%d." + param + ".nc"
        remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                             res=24 * 3600.0)))
        remote_path = _METEOR_REMOTE + length + "/" + site_dir + "/"
        local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                                 "mu", "meteor", "nc", length, site_dir)
        files = download(remote_file=remote_names, remote_path=remote_path,
                         local_path=local_dir, no_download=no_update, last_version=True)
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))
        dl_files += out_files
        if downloadonly:
            continue

        recs = [d for d in (_read_mu_meteor(f) for f in out_files) if d is not None]
        if not recs:
            continue
        height = recs[-1]["height"]
        mu_time = _concat([d["time"] for d in recs])
        data = {k: _concat([d[k] for d in recs])
                for k in ("uwnd", "vwnd", "uwndsig", "vwndsig", "mwnum")}

        tmask = (mu_time >= t0) & (mu_time <= t1)
        if not np.any(tmask):
            continue
        ct = mu_time[tmask]

        # clip ranges
        clip = {"uwnd": (-400.0, 400.0), "vwnd": (-400.0, 400.0),
                "uwndsig": (0.0, 800.0), "vwndsig": (0.0, 800.0),
                "mwnum": (0.0, 1200.0)}
        for kind in ("uwnd", "vwnd", "uwndsig", "vwndsig", "mwnum"):
            name = "iug_mu_meteor_" + kind + "_" + param + suffix
            y = data[kind][tmask, :].copy()
            # degap with dt=3600 s, then clip to lo..hi
            dt, dy = _idl_xdegap(ct, y, dt=3600.0)
            lo, hi = clip[kind]
            dy = np.where((dy < lo) | (dy > hi), np.nan, dy)
            if notplot:
                loaded[name] = {"x": dt, "y": dy, "v": height}
            else:
                store_data(name, data={"x": dt, "y": dy, "v": height})
                options(name, "spec", 1)
                options(name, "ytitle", "MU-meteor!CHeight!C[km]")
                zt = kind if kind == "mwnum" else kind + "!C[m/s]"
                options(name, "ztitle", zt)
                loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# ionosphere drift
# ==================================================================
def _read_mu_iono_drift(path):
    """Read one MU ionosphere drift netCDF file (1D time series; Vd_b is per beam).

    Vperp_e/n, Vpara_u, Vz_ns, Vz_ew are (time,); Vd_b is (beam,time) ->
    (time,beam). The units come from the time variable. Fill value 999.0 -> NaN.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        def _rd1(name):
            a = np.asarray(ds.variables[name][:], dtype=np.float64).ravel()
            return np.where(a == 999.0, np.nan, a)

        vdb = np.asarray(ds.variables["Vd_b"][:], dtype=np.float64).T  # (time, beam)
        vdb = np.where(vdb == 999.0, np.nan, vdb)
        return {
            "time": unix_time,
            "Vperp_e": _rd1("Vperp_e"),
            "Vperp_n": _rd1("Vperp_n"),
            "Vpara_u": _rd1("Vpara_u"),
            "Vz_ns": _rd1("Vz_ns"),
            "Vz_ew": _rd1("Vz_ew"),
            "Vd_b": vdb,
        }
    finally:
        ds.close()


def _load_mu_iono_drift(trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU ionosphere drift data and create tplot variables.

    iug_mu_iono_{Vperp_e,Vperp_n,Vpara_u,Vz_ns,Vz_ew,Vd_b}, all 1D. Degapped
    with dt=3600 s. To match the original output, a bug is reproduced
    intentionally: Vz_ew is overwritten by the (clipped) Vd_b, while Vd_b itself
    is left un-clipped.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    file_format = "%Y/%Y%m%d_drift.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "ionosphere", "drift", "nc")
    files = download(remote_file=remote_names, remote_path=_IONO_DRIFT_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))
    if downloadonly:
        return out_files

    recs = [d for d in (_read_mu_iono_drift(f) for f in out_files) if d is not None]
    if not recs:
        return {} if notplot else []
    mu_time = _concat([d["time"] for d in recs])
    series = {k: _concat([d[k] for d in recs])
              for k in ("Vperp_e", "Vperp_n", "Vpara_u", "Vz_ns")}
    vdb = _concat([d["Vd_b"] for d in recs])     # (time, beam) 2D

    tmask = (mu_time >= t0) & (mu_time <= t1)
    if not np.any(tmask):
        return {} if notplot else []
    ct = mu_time[tmask]

    loaded = {} if notplot else []

    def _emit(name, x, y, title):
        # degap with dt=3600 s
        dt, dy = _idl_xdegap(x, y, dt=3600.0)
        if notplot:
            loaded[name] = {"x": dt, "y": dy}
        else:
            store_data(name, data={"x": dt, "y": dy})
            options(name, "ytitle", title)
            loaded.append(name)

    _emit("iug_mu_iono_Vperp_e" + suffix, ct, series["Vperp_e"][tmask], "MU-iono!CVperp_e!C[m/s]")
    _emit("iug_mu_iono_Vperp_n" + suffix, ct, series["Vperp_n"][tmask], "MU-iono!CVperp_n!C[m/s]")
    _emit("iug_mu_iono_Vpara_u" + suffix, ct, series["Vpara_u"][tmask], "MU-iono!CVpara_u!C[m/s]")
    _emit("iug_mu_iono_Vz_ns" + suffix, ct, series["Vz_ns"][tmask], "MU-iono!CVz_ns!C[m/s]")
    # Bug reproduced to match the original output:
    #   store iug_mu_iono_Vd_b = the 2D (time x beam) Vd_b without time clipping
    #   then time-clip it into iug_mu_iono_Vz_ew, overwriting Vz_ew
    # so Vz_ew = the clipped 2D Vd_b, and Vd_b = the un-clipped 2D Vd_b. Both
    # are degapped with dt=3600 s.
    _emit("iug_mu_iono_Vz_ew" + suffix, ct, vdb[tmask], "MU-iono!CVz_ew!C[m/s]")
    _emit("iug_mu_iono_Vd_b" + suffix, mu_time, vdb, "MU-iono!CVd_b!C[m/s]")

    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# ionosphere pwr
# ==================================================================
def _read_mu_iono_pwr(path):
    """Read one MU ionosphere pwr netCDF file (2D: time x height).

    pwr is (beam,time,height); height is (beam,height). The time center is
    (stime+etime)/2 and the units come from stime. Fill value -999.0 -> NaN.
    Since netCDF pwr is (beam,time,height), the (time,height) slice for beam l
    is simply pwr[l].
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        svar = ds.variables["stime"]
        stime = np.asarray(svar[:], dtype=np.float64)
        etime = np.asarray(ds.variables["etime"][:], dtype=np.float64)
        if stime.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(svar.units)
        center = (stime + etime) / 2.0
        unix_time = center * scale + base_unix - tz_sec

        pwr = np.asarray(ds.variables["pwr"][:], dtype=np.float64)   # (beam,time,height)
        pwr = np.where(pwr == -999.0, np.nan, pwr)
        height = np.asarray(ds.variables["height"][:], dtype=np.float64)  # (beam,height)
        return {"time": unix_time, "pwr": pwr, "height": height}
    finally:
        ds.close()


def _load_mu_iono_pwr(trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU ionosphere pwr data and create tplot variables.

    iug_mu_iono_pwr1..4 (2D spectrogram, v=height[beam]). Degapped with
    dt=3600 s.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    file_format = "%Y/%Y%m%d_pwr.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "ionosphere", "pwr", "nc")
    files = download(remote_file=remote_names, remote_path=_IONO_PWR_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))
    if downloadonly:
        return out_files

    recs = [d for d in (_read_mu_iono_pwr(f) for f in out_files) if d is not None]
    if not recs:
        return {} if notplot else []
    last = recs[-1]
    height = last["height"]                          # (beam, height)
    nbeam = min(4, height.shape[0])
    mu_time = _concat([d["time"] for d in recs])
    pwr = _concat([d["pwr"] for d in recs], axis=1)  # (beam, time, height)

    tmask = (mu_time >= t0) & (mu_time <= t1)
    if not np.any(tmask):
        return {} if notplot else []
    ct = mu_time[tmask]

    loaded = {} if notplot else []
    for l in range(nbeam):
        name = "iug_mu_iono_pwr" + str(l + 1) + suffix
        y = pwr[l][tmask, :]
        dt, dy = _idl_xdegap(ct, y, dt=3600.0)
        hgt = height[l, :]
        if notplot:
            loaded[name] = {"x": dt, "y": dy, "v": hgt}
        else:
            store_data(name, data={"x": dt, "y": dy, "v": hgt})
            options(name, "spec", 1)
            options(name, "ytitle", "MU-iono!CHeight!C[km]")
            options(name, "ztitle", "pwr" + str(l + 1) + "!C[dB]")
            loaded.append(name)

    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# ionosphere teti (Ti/Te etc.)
# ==================================================================
def _read_mu_iono_teti(path):
    """Read one MU ionosphere teti netCDF file (2D: time x height).

    Ti/Te/icon/er_ti/er_te/er_tr/snr are (time,height); height is 1D. The time
    center is (stime+etime)/2 and the units come from stime.
    Mask: -999.0 or icon==3 -> NaN.
    To match the original output, a bug is reproduced intentionally: er_tr
    itself is left raw (not NaN-masked), and snr is overwritten by the masked
    er_tr (not the actual snr).
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        svar = ds.variables["stime"]
        stime = np.asarray(svar[:], dtype=np.float64)
        etime = np.asarray(ds.variables["etime"][:], dtype=np.float64)
        if stime.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(svar.units)
        center = (stime + etime) / 2.0
        unix_time = center * scale + base_unix - tz_sec

        ti = np.asarray(ds.variables["Ti"][:], dtype=np.float64)     # (time,height)
        te = np.asarray(ds.variables["Te"][:], dtype=np.float64)
        icon = np.asarray(ds.variables["icon"][:])
        er_ti = np.asarray(ds.variables["er_ti"][:], dtype=np.float64)
        er_te = np.asarray(ds.variables["er_te"][:], dtype=np.float64)
        er_tr = np.asarray(ds.variables["er_tr"][:], dtype=np.float64)

        bad_icon = (icon == 3)
        ti = np.where((ti == -999.0) | bad_icon, np.nan, ti)
        te = np.where((te == -999.0) | bad_icon, np.nan, te)
        er_ti = np.where((er_ti == -999.0) | bad_icon, np.nan, er_ti)
        er_te = np.where((er_te == -999.0) | bad_icon, np.nan, er_te)
        # snr = masked er_tr (the actual snr is unused); er_tr itself is unmasked.
        snr = np.where((er_tr == -999.0) | bad_icon, np.nan, er_tr)

        height = np.asarray(ds.variables["height"][:], dtype=np.float64).ravel()
        return {"time": unix_time, "ti": ti, "te": te, "er_ti": er_ti,
                "er_te": er_te, "er_tr": er_tr, "snr": snr, "height": height}
    finally:
        ds.close()


def _load_mu_iono_teti(trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU ionosphere teti data and create tplot variables.

    iug_mu_iono_{ti,te,er_ti,er_te,er_tr,snr} (2D spectrogram, v=height).
    Degapped with dt=3600 s.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    file_format = "%Y/%Y%m%d_teti.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "ionosphere", "teti", "nc")
    files = download(remote_file=remote_names, remote_path=_IONO_TETI_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))
    if downloadonly:
        return out_files

    recs = [d for d in (_read_mu_iono_teti(f) for f in out_files) if d is not None]
    if not recs:
        return {} if notplot else []
    height = recs[-1]["height"]
    mu_time = _concat([d["time"] for d in recs])
    data = {k: _concat([d[k] for d in recs])
            for k in ("ti", "te", "er_ti", "er_te", "er_tr", "snr")}

    tmask = (mu_time >= t0) & (mu_time <= t1)
    if not np.any(tmask):
        return {} if notplot else []
    ct = mu_time[tmask]

    loaded = {} if notplot else []
    titles = {"ti": "Ion temp.!C[K]", "te": "Electron temp.!C[K]",
              "er_ti": "Ion temp. Error!C[K]", "er_te": "Electron temp. Error!C[K]",
              "er_tr": "Te/Ti Error!C[K]", "snr": "SNR!C[dB]"}
    for kind in ("ti", "te", "er_ti", "er_te", "er_tr", "snr"):
        name = "iug_mu_iono_" + kind + suffix
        y = data[kind][tmask, :]
        dt, dy = _idl_xdegap(ct, y, dt=3600.0)
        if notplot:
            loaded[name] = {"x": dt, "y": dy, "v": height}
        else:
            store_data(name, data={"x": dt, "y": dy, "v": height})
            options(name, "spec", 1)
            options(name, "ytitle", "MU-iono!CHeight!C[km]")
            options(name, "ztitle", titles[kind])
            loaded.append(name)

    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# rass (CSV)
# ==================================================================
_MONTH_MAP = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05",
              "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10",
              "NOV": "11", "DEC": "12"}


def _parse_mu_rass_csv(path):
    """Read one MU rass CSV file; return (unix_time[Nt], data[Nt,Nh], altitude[Nh]).

    Line 1: the height header (the first field excluded, in [m]). Lines starting
    with '[' are skipped. Data rows are 'DD-MON-YYYY HH:MM[:SS]' (LT) followed
    by the per-height values. Fill value 999 -> NaN. LT->UT subtracts 9 h. The
    altitude is divided by 1000 [km] at store time.
    """
    try:
        with open(path, "r", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None
    # Empty tokens are dropped (e.g. the trailing blank from a line-ending
    # comma) to match the original splitting behavior.
    def _split(s):
        return [tok for tok in s.split(",") if tok != ""]
    header = _split(lines[0])
    if len(header) < 2:
        return None
    # altitude and the data are float32. The CSV text values are cast to float32
    # to match the original output bit-for-bit.
    altitude = np.array([np.float32(h) for h in header[1:]], dtype=np.float32)
    nh = altitude.size

    times = []
    rows = []
    for ln in lines[1:]:
        if not ln:
            continue
        if ln[:1] == "[":
            continue
        d = _split(ln)
        if len(d) < 2:
            continue
        u = d[0].strip().split()
        if len(u) < 2:
            continue
        datepart = u[0].split("-")     # DD-MON-YYYY
        if len(datepart) < 3:
            continue
        day, mon, year = datepart[0], datepart[1].upper(), datepart[2]
        mon = _MONTH_MAP.get(mon, mon)
        date_str = year + "-" + mon + "-" + day + "/" + u[1]
        lt = float(time_double(date_str))
        ut = lt - 9.0 * 3600.0
        row = np.full(nh, np.nan, dtype=np.float32)
        for j in range(nh):
            if j + 1 < len(d):
                try:
                    fv = np.float32(d[j + 1])
                except ValueError:
                    continue
                row[j] = np.nan if fv == np.float32(999.0) else fv
        times.append(ut)
        rows.append(row)

    if not times:
        return None
    return (np.array(times, dtype=np.float64),
            np.array(rows, dtype=np.float64), altitude)


def _load_mu_rass(parameters, trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU rass (CSV) data and create tplot variables.

    iug_mu_rass_<param> (2D spectrogram, v=altitude/1000 [km]). Degapped with
    dt=600 s. The local path is rish/misc/mu/rass/csv (no sgk subdirectory) to
    match the original layout.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)

    loaded = {} if notplot else []
    dl_files = []

    for param in parameters:
        file_format = "%Y/%Y%m%d/%Y%m%d." + param + ".csv"
        remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                             res=24 * 3600.0)))
        # local path rish/misc/mu/rass/csv (no sgk subdirectory)
        local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc",
                                 "mu", "rass", "csv")
        files = download(remote_file=remote_names, remote_path=_RASS_REMOTE,
                         local_path=local_dir, no_download=no_update, last_version=True)
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))
        dl_files += out_files
        if downloadonly:
            continue

        xs, ys, altitude = [], [], None
        for f in out_files:
            res = _parse_mu_rass_csv(f)
            if res is None:
                continue
            x, y, alt = res
            if altitude is not None and y.shape[1] != altitude.size:
                continue
            altitude = alt
            xs.append(x)
            ys.append(y)
        if not xs:
            continue
        x = _concat(xs)
        y = _concat(ys)

        tmask = (x >= t0) & (x <= t1)
        if not np.any(tmask):
            continue
        ct = x[tmask]
        cy = y[tmask]
        # degap with dt=600 s
        dt, dy = _idl_xdegap(ct, cy, dt=600.0)
        name = "iug_mu_rass_" + param + suffix
        unit = "degree" if param.startswith("temp") else "m/s"
        if notplot:
            loaded[name] = {"x": dt, "y": dy, "v": altitude / 1000.0}
        else:
            store_data(name, data={"x": dt, "y": dy, "v": altitude / 1000.0})
            options(name, "spec", 1)
            options(name, "ytitle", "MU-rass!CHeight!C[km]")
            options(name, "ztitle", param + "!C[" + unit + "]")
            loaded.append(name)

    if downloadonly:
        return sorted(set(dl_files))
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


# ==================================================================
# fai  (same shape as EAR FAI; reuses the SNR/degap helpers)
# ==================================================================
def _read_mu_fai(path):
    """Read one MU FAI netCDF file.

    netCDF dims: beam, range, time. pwr/width/dpl are (beam,time,range); pnoise
    is (beam,time). If a height (beam,range) variable is present it is used as
    the range. SNR uses ndata (a scalar): snr = pwr-(pnoise+log10(ndata)).
    Fill value 1e10 -> NaN.
    """
    import netCDF4
    try:
        ds = netCDF4.Dataset(path, "r")
    except OSError:
        return None
    try:
        tvar = ds.variables["time"]
        tvals = np.asarray(tvar[:], dtype=np.float64)
        if tvals.size == 0:
            return None
        base_unix, tz_sec, scale = _parse_time_units(tvar.units)
        unix_time = tvals * scale + base_unix - tz_sec

        beam = np.asarray(ds.variables["beam"][:]).ravel()
        ndata = int(np.asarray(ds.variables["ndata"][:]).ravel()[0])
        # use the 2D height (beam,range) as the range when present
        if "height" in ds.variables:
            height = np.asarray(ds.variables["height"][:], dtype=np.float64)  # (beam,range)
        else:
            rng = np.asarray(ds.variables["range"][:], dtype=np.float64).ravel()
            height = np.tile(rng, (beam.size, 1))
        return {
            "time": unix_time,
            "beam": beam,
            "ndata": ndata,
            "height": height,
            "pwr": _nan_missing(ds.variables["pwr"][:]),     # (beam,time,range)
            "wdt": _nan_missing(ds.variables["width"][:]),
            "dpl": _nan_missing(ds.variables["dpl"][:]),
            "pn": _nan_missing(ds.variables["pnoise"][:]),   # (beam,time)
        }
    finally:
        ds.close()


def _load_mu_fai(parameters, trange, no_update, downloadonly, ror, suffix, notplot):
    """Read MU FAI data and create tplot variables.

    iug_mu_fai_<param>_{pwr,wdt,dpl,snr}B (2D spectrogram) + _pnB (1D).
    SNR=pwr-(pn+log10(ndata)) is computed in float32. Degapped with the default
    dt. As in the EAR FAI loader, the pnoise row-count bug (only up to the time
    count of the last file is filled; the rest are 0) is reproduced to match the
    original output.
    """
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    win = _win_trange(t0, t1)
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "fai", "nc")

    loaded = {} if notplot else []
    dl_files = []

    for param in parameters:
        file_format = "%Y/%Y%m%d/%Y%m%d." + param + ".nc"
        remote_names = sorted(set(dailynames(file_format=file_format, trange=win,
                                             res=24 * 3600.0)))
        files = download(remote_file=remote_names, remote_path=_FAI_REMOTE,
                         local_path=local_dir, no_download=no_update, last_version=True)
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))
        dl_files += out_files
        if downloadonly:
            continue

        recs = [d for d in (_read_mu_fai(f) for f in out_files) if d is not None]
        if not recs:
            continue
        last = recs[-1]
        beam = last["beam"]
        nbeam = beam.size
        height_beam = last["height"]          # (beam, range)
        ndata = last["ndata"]

        mu_time = _concat([d["time"] for d in recs])
        pwr = _concat([d["pwr"] for d in recs], axis=1)   # (beam,time,range)
        wdt = _concat([d["wdt"] for d in recs], axis=1)
        dpl = _concat([d["dpl"] for d in recs], axis=1)
        pn = _concat([d["pn"] for d in recs], axis=1)     # (beam,time)

        # SNR = pwr - (pnoise + log10(ndata)) computed in float32
        log_n = np.float32(np.log10(np.float32(ndata)))
        snr = (pwr.astype(np.float32)
               - (pn.astype(np.float32)[:, :, None] + log_n)).astype(np.float32)

        # pnoise row-count bug (filled only up to the last file's time count; 0 after)
        nt_last = int(recs[-1]["time"].size)
        pn_buggy = pn.astype(np.float64).copy()
        if nt_last < pn_buggy.shape[1]:
            pn_buggy[:, nt_last:] = 0.0

        tmask = (mu_time >= t0) & (mu_time <= t1)
        if not np.any(tmask):
            continue
        ct = mu_time[tmask]

        base = "iug_mu_fai_" + param
        for l in range(nbeam):
            bn = str(int(round(beam[l])) + 1)
            hb = height_beam[l, :]
            for kind, arr, zt in (("pwr", pwr, "pwr" + bn + "!C[dB]"),
                                  ("wdt", wdt, "wdt" + bn + "!C[m/s]"),
                                  ("dpl", dpl, "dpl" + bn + "!C[m/s]"),
                                  ("snr", snr, "snr" + bn + "!C[dB]")):
                name = base + "_" + kind + bn + suffix
                # degap with the default dt
                dt, dy = _idl_xdegap(ct, arr[l][tmask, :])
                if notplot:
                    loaded[name] = {"x": dt, "y": dy, "v": hb}
                else:
                    store_data(name, data={"x": dt, "y": dy, "v": hb})
                    options(name, "spec", 1)
                    options(name, "ytitle", "MU-FAI!CHeight!C[km]")
                    options(name, "ztitle", zt)
                    loaded.append(name)
            pnname = base + "_pn" + bn + suffix
            dt, dy = _idl_xdegap(ct, pn_buggy[l][tmask])
            if notplot:
                loaded[pnname] = {"x": dt, "y": dy}
            else:
                store_data(pnname, data={"x": dt, "y": dy})
                options(pnname, "ytitle", "pn" + bn + "!C[dB]")
                loaded.append(pnname)

    if downloadonly:
        return sorted(set(dl_files))
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


def _load_mu_trop(trange, no_update, downloadonly, time_clip, ror, suffix, notplot):
    """Read MU troposphere data and create tplot variables."""
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    # daily file names over [t0, t1+9h]
    win_trange = [time_string(t0), time_string(t1 + _LT_SHIFT)]

    file_format = "%Y%m/%Y%m%d/%Y%m%d.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win_trange,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "sgk",
                             "mu", "troposphere", "nc")
    files = download(remote_file=remote_names, remote_path=_TROP_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files
    if not out_files:
        print("No MU troposphere data found in " + str(trange))
        return {} if notplot else []

    # ===== read all files and concatenate along time =====
    recs = [d for d in (_read_mu_trop(f) for f in out_files) if d is not None]
    if not recs:
        print("No valid MU troposphere data parsed in " + str(trange))
        return {} if notplot else []

    last = recs[-1]                       # use the last file's height arrays/beam
    beam = last["beam"]
    nbeam = beam.size
    last_date = last["date"]

    # ===== determine the heights (f_list test) =====
    # date in f_list -> use the netCDF height_vw/height_mwzw.
    # otherwise -> use the hard-coded height_v(120)/height_zm(120).
    # The last file's height is used for all store_data calls.
    if last_date in _F_LIST:
        # pad the netCDF height (range points, usually 118) to 120 points to
        # match the right-justified data (needed for the spectrogram; the height
        # axis must match the 120 data columns).
        height_mwzw = _rj_height(last["height_mwzw"])
        height_vw = _rj_height(last["height_vw"])
    else:
        height_mwzw = _HEIGHT_ZM           # the hard-coded arrays are already 120 points
        height_vw = _HEIGHT_V
    height2 = height_vw                    # pwr/wdt/dpl/pn height = height_vw

    mu_time = _concat([d["time"] for d in recs])
    zon = _concat([d["uwnd"] for d in recs])   # (time, 120)
    mer = _concat([d["vwnd"] for d in recs])
    ver = _concat([d["wwnd"] for d in recs])
    pwr = _concat([d["pwr"] for d in recs], axis=1)   # (beam, time, 120)
    wdt = _concat([d["wdt"] for d in recs], axis=1)
    dpl = _concat([d["dpl"] for d in recs], axis=1)
    pn = _concat([d["pn"] for d in recs], axis=1)     # (beam, time)

    # ===== edge cut on the closed UT interval [t0, t1] =====
    tmask = (mu_time >= t0) & (mu_time <= t1)
    if not np.any(tmask):
        print("No MU troposphere data within trange " + str(trange))
        return {} if notplot else []
    ct = mu_time[tmask]

    loaded = {} if notplot else []

    def _store(name, y, v, ztitle, spec=True, pn_title=None):
        if notplot:
            loaded[name] = {"x": ct, "y": y, "v": v} if v is not None else {"x": ct, "y": y}
            return
        if v is not None:
            store_data(name, data={"x": ct, "y": y, "v": v})
        else:
            store_data(name, data={"x": ct, "y": y})
        try:
            degap(name)
        except Exception:
            pass
        if spec:
            options(name, "spec", 1)
            options(name, "ytitle", "MUR-trop!CHeight!C[km]")
            options(name, "ztitle", ztitle)
        else:
            options(name, "ytitle", pn_title)
        loaded.append(name)

    # ----- three wind components (uwnd/vwnd=height_mwzw, wwnd=height_vw) -----
    _store("iug_mu_trop_uwnd" + suffix, zon[tmask, :], height_mwzw, "uwnd!C[m/s]")
    _store("iug_mu_trop_vwnd" + suffix, mer[tmask, :], height_mwzw, "vwnd!C[m/s]")
    _store("iug_mu_trop_wwnd" + suffix, ver[tmask, :], height_vw, "wwnd!C[m/s]")

    # ----- per-beam pwr/wdt/dpl (2D spectrogram) and pn (1D) -----
    for l in range(nbeam):
        bn = str(int(round(beam[l])) + 1)            # beam number (beam[l]+1)
        _store("iug_mu_trop_pwr" + bn + suffix, pwr[l][tmask, :], height2, "pwr" + bn + "!C[dB]")
        _store("iug_mu_trop_wdt" + bn + suffix, wdt[l][tmask, :], height2, "wdt" + bn + "!C[m/s]")
        _store("iug_mu_trop_dpl" + bn + suffix, dpl[l][tmask, :], height2, "dpl" + bn + "!C[m/s]")
        _store("iug_mu_trop_pn" + bn + suffix, pn[l][tmask], None, None,
               spec=False, pn_title="pn" + bn + "!C[dB]")

    if ror:
        _print_ack()
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


def mu(
    trange=["1986-03-17", "1986-03-18"],
    site="",
    datatype="troposphere",
    parameter="all",
    level="",
    length="1_day",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    ror=True,
    suffix="",
):
    """Load MU (middle and upper atmosphere) radar data from RISH, Kyoto University.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A full day is read even
        if the range spans less than a day; files are fetched accounting for the
        LT(+09)->UT offset and then edge-cut in UT.
        Default: ['1986-03-17', '1986-03-18']
    site : str
        Observatory code. The MU radar has a single site (Shigaraki), so this is
        unused.
        Default: ''
    datatype : str or list of str
        Observation mode. 'all' selects every mode. Valid options: troposphere,
        mesosphere, ionosphere, meteor, rass, fai.
        Default: 'troposphere'
    parameter : str or list of str
        Physical parameter(s) to load. 'all' loads every parameter. Used for the
        meteor, rass and fai modes; ignored for troposphere/mesosphere/
        ionosphere. Valid options: for meteor, h1t60min00 / h1t60min30 /
        h2t60min00 / h2t60min30; for rass, uwnd / vwnd / wwnd / temp; for fai,
        one of the FAI parameter codes (e.g. iemdc3).
        Default: 'all'
    level : str
        Data processing level for the mesosphere mode. Valid options: org, scr.
        Ignored for the other modes.
        Default: ''
    length : str
        File aggregation length for the meteor mode. Valid options: 1_day,
        1_month. Ignored for the other modes.
        Default: '1_day'
    no_update : bool
        If set, only load data already present in the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    ror : bool
        If set, print the Rules of the Road and acknowledgement information for
        the dataset.
        Default: True
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created. Empty list if no data were loaded. The
        names depend on the mode:
        troposphere : iug_mu_trop_{uwnd,vwnd,wwnd,pwr1-5,wdt1-5,dpl1-5,pn1-5};
        mesosphere  : iug_mu_meso_{pwr,wdt,dpl}{1-5}_{level}, _pn{1-5}_{level},
                      _{uwnd,vwnd,wwnd}_{level};
        ionosphere  : iug_mu_iono_{Vperp_e,Vperp_n,Vpara_u,Vz_ns,Vz_ew,Vd_b},
                      _pwr1-4, _{ti,te,er_ti,er_te,er_tr,snr};
        meteor      : iug_mu_meteor_{uwnd,vwnd,uwndsig,vwndsig,mwnum}_<param>;
        rass        : iug_mu_rass_<param>;
        fai         : iug_mu_fai_<param>_{pwr,wdt,dpl,snr,pn}{beam}.
        If ``downloadonly`` is set, the list of downloaded file paths is
        returned; if ``notplot`` is set, a dictionary of data is returned
        instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.mu(trange=['1986-03-17', '1986-03-18'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    datatypes = _normalize(datatype, DATATYPE_ALL)
    if not datatypes:
        print("This datatype is not valid. Please input: all, troposphere, "
              "mesosphere, ionosphere, meteor, rass, fai.")
        return {} if notplot else []

    loaded = {} if notplot else []
    dl = []
    for dt in datatypes:
        if dt == "troposphere":
            res = _load_mu_trop(trange, no_update, downloadonly, time_clip,
                                ror, suffix, notplot)
        elif dt == "mesosphere":
            # normalize the levels, then load the echo and wind data in turn
            levels = _normalize(level if level else "all", _MESO_LEVEL_ALL)
            if not levels:
                levels = list(_MESO_LEVEL_ALL)
            if downloadonly:
                res = (_load_mu_meso(levels, trange, no_update, True, ror, suffix, notplot)
                       + _load_mu_meso_wind(levels, trange, no_update, True, ror, suffix, notplot))
            elif notplot:
                res = {}
                res.update(_load_mu_meso(levels, trange, no_update, False, ror, suffix, notplot))
                res.update(_load_mu_meso_wind(levels, trange, no_update, False, ror, suffix, notplot))
            else:
                res = (_load_mu_meso(levels, trange, no_update, False, ror, suffix, notplot)
                       + _load_mu_meso_wind(levels, trange, no_update, False, ror, suffix, notplot))
        elif dt == "ionosphere":
            # load drift, then pwr, then teti (no parameter/level)
            if downloadonly:
                res = (_load_mu_iono_drift(trange, no_update, True, ror, suffix, notplot)
                       + _load_mu_iono_pwr(trange, no_update, True, ror, suffix, notplot)
                       + _load_mu_iono_teti(trange, no_update, True, ror, suffix, notplot))
            elif notplot:
                res = {}
                res.update(_load_mu_iono_drift(trange, no_update, False, ror, suffix, notplot))
                res.update(_load_mu_iono_pwr(trange, no_update, False, ror, suffix, notplot))
                res.update(_load_mu_iono_teti(trange, no_update, False, ror, suffix, notplot))
            else:
                res = (_load_mu_iono_drift(trange, no_update, False, ror, suffix, notplot)
                       + _load_mu_iono_pwr(trange, no_update, False, ror, suffix, notplot)
                       + _load_mu_iono_teti(trange, no_update, False, ror, suffix, notplot))
        elif dt == "meteor":
            params = _normalize(parameter, _METEOR_PARAM_ALL)
            if not params:
                params = list(_METEOR_PARAM_ALL)
            res = _load_mu_meteor(params, length or "1_day", trange, no_update,
                                  downloadonly, ror, suffix, notplot)
        elif dt == "rass":
            params = _normalize(parameter, _RASS_PARAM_ALL)
            if not params:
                params = list(_RASS_PARAM_ALL)
            res = _load_mu_rass(params, trange, no_update, downloadonly,
                                ror, suffix, notplot)
        elif dt == "fai":
            params = _normalize(parameter, _FAI_PARAM_ALL)
            if not params:
                print("No valid MU FAI parameter.")
                continue
            res = _load_mu_fai(params, trange, no_update, downloadonly,
                               ror, suffix, notplot)
        else:
            print(f"MU datatype '{dt}' is not yet implemented.")
            continue
        if downloadonly:
            dl += res
        elif notplot:
            loaded.update(res)
        else:
            loaded += res

    # The acknowledgement (ror) is printed at the end of each mode. troposphere
    # already calls _print_ack() internally; for the other modes it is printed
    # once here (a cosmetic output that does not affect the CSV/tplot data).
    if ror and not downloadonly and any(d != "troposphere" for d in datatypes) \
            and ((notplot and loaded) or (not notplot and loaded)):
        _print_ack()
    if downloadonly:
        return sorted(set(dl))
    return loaded


def _print_ack():
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print("If you acquire the middle and upper atmosphere (MU) radar data,")
    print("we ask that you acknowledge us in your use of the data.")
    print("This may be done by including text such as MU data provided")
    print("by Research Institute for Sustainable Humanosphere of Kyoto University.")
    print("We would also appreciate receiving a copy of the relevant publications.")
    print("The distribution of MU radar data has been partly supported by the IUGONET")
    print("(Inter-university Upper atmosphere Global Observation NETwork) project")
    print("(http://www.iugonet.org/) funded by the Ministry of Education, Culture,")
    print("Sports, Science and Technology (MEXT), Japan.")
