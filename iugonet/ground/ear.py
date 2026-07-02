"""Load function for Equatorial Atmosphere Radar (EAR) data (Kototabang, Indonesia).

``datatype`` selects the observation mode:

- ``troposphere`` : troposphere / lower stratosphere (standard observation);
  three-component wind plus per-beam pwr/wdt/dpl/pn.
- ``e_region`` / ``ef_region`` / ``v_region`` / ``f_region`` : FAI
  (field-aligned irregularities).

The data are not CDF, so the common load() (cdf_to_tplot) cannot be used; the
.nc files are fetched with the pyspedas ``download`` and parsed in-house with
netCDF4. The server is www.rish.kyoto-u.ac.jp.

netCDF structure (confirmed from the actual file 20011013.nc, troposphere):
  dimensions: beam(5), range(120), time(unlimited)
  time     (time,)          units='seconds since YYYY-MM-DD 00:00:00 +07:00' (LT base)
  range, height_vw, height_mwzw (range,) [km]; height (beam,range) [km]
  zwind, mwind, vwind (time,range) [m/s]     <- read with swapped names (below)
  pwr, width, dpl     (beam,time,range)       ; pnoise (beam,time) [dB]
  Missing value = 1e10 -> NaN. No value clipping (trop is not clipped).

Important variable correspondence (note the swap):
  netCDF ``zwind`` -> zonal wind uwnd (iug_ear_trop_uwnd, v=height_mwzw)
  netCDF ``mwind`` -> meridional wind vwnd (iug_ear_trop_vwnd, v=height_mwzw)
  netCDF ``vwind`` -> vertical wind wwnd (iug_ear_trop_wwnd, v=height_vw)
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, time_string, dailynames, download
from pyspedas.tplot_tools import degap

from iugonet.config import CONFIG

# All data types (default 'troposphere').
DATATYPE_ALL = ["troposphere", "e_region", "ef_region", "v_region", "f_region"]

# All FAI parameters.
PARAMETER_ALL = (
    "eb1p2a eb1p2b eb1p2c eb2p1a eb3p2a eb3p2b eb3p4a eb3p4b eb3p4c eb3p4d "
    "eb3p4e eb3p4f eb3p4g eb3p4h eb4p2c eb4p2d eb4p4 eb4p4a eb4p4b eb4p4d "
    "eb5p4a efb1p16 efb1p16a efb1p16b vb3p4a 150p8c8a 150p8c8b 150p8c8c "
    "150p8c8d 150p8c8e 150p8c8b2a 150p8c8b2b 150p8c8b2c 150p8c8b2d 150p8c8b2e "
    "150p8c8b2f fb1p16a fb1p16b fb1p16c fb1p16d fb1p16e fb1p16f fb1p16g "
    "fb1p16h fb1p16i fb1p16j1 fb1p16j2 fb1p16j3 fb1p16j4 fb1p16j5 fb1p16j6 "
    "fb1p16j7 fb1p16j8 fb1p16j9 fb1p16j10 fb1p16j11 fb1p16k1 fb1p16k2 fb1p16k3 "
    "fb1p16k4 fb1p16k5 fb1p16m2 fb1p16m3 fb1p16m4 fb8p16 fb8p16k1 fb8p16k2 "
    "fb8p16k3 fb8p16k4 fb8p16m1 fb8p16m2"
).split()

# EAR = Kototabang. time.units is based on LT (+07:00); LT->UT window shift = 7h.
_LT_SHIFT = 7.0 * 3600.0
_MISSING = 1e10

_TROP_REMOTE = "http://www.rish.kyoto-u.ac.jp/ear/data/data/ver02.0212/"

# Remote for FAI (e/ef/v/f_region). The www host now returns 404 for paths under
# data (redirects to WordPress) and does not serve .nc; the actual files exist
# only under the www2 Apache autoindex (Content-Type=application/x-netcdf).
# pathformat: YYYY/YYYYMMDD/YYYYMMDD.fai{parameter}.nc
_FAI_REMOTE = "https://www2.rish.kyoto-u.ac.jp/ear/data-fai/data/nc/"

# datatype -> local_data_dir subdirectory (e_region/ef_region/v_region/f_region).
# The server-side path and processing are common to all regions.
_FAI_SUBDIR = {
    "e_region": "e_region",
    "ef_region": "ef_region",
    "v_region": "v_region",
    "f_region": "f_region",
}

# Valid parameters per datatype.
_FAI_PARAMETER = {
    "e_region": (
        "eb1p2a eb1p2b eb1p2c eb2p1a eb3p2a eb3p2b eb3p4a eb3p4b eb3p4c eb3p4d eb3p4e "
        "eb3p4f eb3p4g eb3p4h eb4p2c eb4p2d eb4p4 eb4p4a eb4p4b eb4p4d eb5p4a"
    ).split(),
    "ef_region": "efb1p16 efb1p16a efb1p16b".split(),
    "v_region": (
        "vb3p4a 150p8c8a 150p8c8b 150p8c8c 150p8c8d 150p8c8e 150p8c8b2a 150p8c8b2b "
        "150p8c8b2c 150p8c8b2d 150p8c8b2e 150p8c8b2f"
    ).split(),
    "f_region": (
        "fb1p16a fb1p16b fb1p16c fb1p16d fb1p16e fb1p16f fb1p16g fb1p16h fb1p16i "
        "fb1p16j1 fb1p16j2 fb1p16j3 fb1p16j4 fb1p16j5 fb1p16j6 fb1p16j7 fb1p16j8 fb1p16j9 "
        "fb1p16j10 fb1p16j11 fb1p16k1 fb1p16k2 fb1p16k3 fb1p16k4 fb1p16k5 fb8p16 fb8p16k1 "
        "fb8p16k2 fb8p16k3 fb8p16k4 fb1p16m2 fb1p16m3 fb1p16m4 fb8p16m1 fb8p16m2"
    ).split(),
}

_ACK = (
    "The Equatorial Atmosphere Radar belongs to Research Institute for "
    "Sustainable Humanosphere (RISH), Kyoto University and is operated by "
    "RISH and National Institute of Aeronautics and Space (LAPAN) Indonesia. "
    "Distribution of the data has been partly supported by the IUGONET "
    "(Inter-university Upper atmosphere Global Observation NETwork) project "
    "(http://www.iugonet.org/) funded by the Ministry of Education, Culture, "
    "Sports, Science and Technology (MEXT), Japan."
)

_UNIT_SCALE = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0, "days": 86400.0}


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes.

    Preserves input order and removes duplicates.
    """
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
    """Parse time.units '<unit> since YYYY-MM-DD HH:MM:SS +TZ:TZ' to (base_unix, tz_sec, scale).

    unix = time*scale + base_unix - tz_sec.
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
    """Replace the missing value 1e10 with NaN and return a float64 array."""
    a = np.asarray(np.ma.filled(np.ma.asarray(arr), fill_value=_MISSING), dtype=np.float64)
    return np.where(a == _MISSING, np.nan, a)


def _read_ear_trop(path):
    """Read one EAR troposphere netCDF and return UT times and data arrays.

    Returns dict or None:
      time (Nt,) unix seconds UT, height_mwzw/height_vw (Nr,) km,
      height (Nbeam,Nr) km, beam (Nbeam,), uwnd/vwnd/wwnd (Nt,Nr),
      pwr/wdt/dpl (Nbeam,Nt,Nr), pn (Nbeam,Nt).
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
        return {
            "time": unix_time,
            "height_mwzw": np.asarray(ds.variables["height_mwzw"][:], dtype=np.float64).ravel(),
            "height_vw": np.asarray(ds.variables["height_vw"][:], dtype=np.float64).ravel(),
            "height": np.asarray(ds.variables["height"][:], dtype=np.float64),   # (beam, range)
            "beam": beam,
            # Name swap: zwind->uwnd, mwind->vwnd, vwind->wwnd
            "uwnd": _nan_missing(ds.variables["zwind"][:]),   # (time, range)
            "vwnd": _nan_missing(ds.variables["mwind"][:]),
            "wwnd": _nan_missing(ds.variables["vwind"][:]),
            "pwr": _nan_missing(ds.variables["pwr"][:]),      # (beam, time, range)
            "wdt": _nan_missing(ds.variables["width"][:]),
            "dpl": _nan_missing(ds.variables["dpl"][:]),
            "pn": _nan_missing(ds.variables["pnoise"][:]),    # (beam, time)
        }
    finally:
        ds.close()


def _concat_time(arrs, axis=0):
    return np.concatenate(arrs, axis=axis)


# xdegap / idl_median live in iugonet.tools.tdegap (strict tdegap port).
# Re-exported under the old names for internal use and import from mu.py.
from iugonet.tools.tdegap import xdegap as _idl_xdegap, idl_median as _idl_median


def _load_ear_trop(trange, no_update, downloadonly, time_clip, ror, suffix, notplot):
    """Load EAR troposphere data and create tplot variables."""
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    day_org = (t1 - t0) / 86400.0
    day_mod = day_org + 1.0
    # Widen the file window toward LT by shifting the start earlier by 7h.
    win_start = t0 - _LT_SHIFT
    win_trange = [time_string(win_start), time_string(win_start + day_mod * 86400.0)]

    file_format = "%Y%m/%Y%m%d/%Y%m%d.nc"
    remote_names = sorted(set(dailynames(file_format=file_format, trange=win_trange,
                                         res=24 * 3600.0)))
    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "ktb",
                             "ear", "troposphere", "nc")
    files = download(remote_file=remote_names, remote_path=_TROP_REMOTE,
                     local_path=local_dir, no_download=no_update, last_version=True)
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files
    if not out_files:
        print("No EAR troposphere data found in " + str(trange))
        return {} if notplot else []

    # ===== read all files and concatenate along time =====
    recs = [d for d in (_read_ear_trop(f) for f in out_files) if d is not None]
    if not recs:
        print("No valid EAR troposphere data parsed in " + str(trange))
        return {} if notplot else []

    last = recs[-1]                       # use the height arrays of the last file
    height_mwzw = last["height_mwzw"]
    height_vw = last["height_vw"]
    height_beam = last["height"]          # (beam, range)
    beam = last["beam"]
    nbeam = beam.size

    ear_time = _concat_time([d["time"] for d in recs])
    zon = _concat_time([d["uwnd"] for d in recs])
    mer = _concat_time([d["vwnd"] for d in recs])
    ver = _concat_time([d["wwnd"] for d in recs])
    # Beam arrays (beam, time, range) are concatenated along the time axis (axis=1).
    pwr = _concat_time([d["pwr"] for d in recs], axis=1)
    wdt = _concat_time([d["wdt"] for d in recs], axis=1)
    dpl = _concat_time([d["dpl"] for d in recs], axis=1)
    pn = _concat_time([d["pn"] for d in recs], axis=1)   # (beam, time)

    # ===== edge-clip (UT [t0, t1]) =====
    tmask = (ear_time >= t0) & (ear_time <= t1)
    if not np.any(tmask):
        print("No EAR troposphere data within trange " + str(trange))
        return {} if notplot else []
    ct = ear_time[tmask]

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
            options(name, "ytitle", "EAR-trop!CHeight!C[km]")
            options(name, "ztitle", ztitle)
        else:
            options(name, "ytitle", pn_title)
        loaded.append(name) if not notplot else None

    # ----- three wind components (uwnd/vwnd=height_mwzw, wwnd=height_vw) -----
    _store("iug_ear_trop_uwnd" + suffix, zon[tmask, :], height_mwzw, "uwnd!C[m/s]")
    _store("iug_ear_trop_vwnd" + suffix, mer[tmask, :], height_mwzw, "vwnd!C[m/s]")
    _store("iug_ear_trop_wwnd" + suffix, ver[tmask, :], height_vw, "wwnd!C[m/s]")

    # ----- per-beam pwr/wdt/dpl (2D spec) and pn (1D) -----
    for l in range(nbeam):
        bn = str(int(round(beam[l])) + 1)            # tplot name uses beam+1
        hb = height_beam[l, :]                        # (range,) height of beam l
        _store("iug_ear_trop_pwr" + bn + suffix, pwr[l][tmask, :], hb, "pwr" + bn + "!C[dB]")
        _store("iug_ear_trop_wdt" + bn + suffix, wdt[l][tmask, :], hb, "wdt" + bn + "!C[m/s]")
        _store("iug_ear_trop_dpl" + bn + suffix, dpl[l][tmask, :], hb, "dpl" + bn + "!C[dB]")
        _store("iug_ear_trop_pn" + bn + suffix, pn[l][tmask], None, None,
               spec=False, pn_title="pn" + bn + "!C[dB]")

    if ror:
        _print_ack()
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


def _read_ear_fai(path):
    """Read one EAR FAI netCDF and return UT times and data arrays.

    All FAI regions (e/ef/v/f) share the same reading logic.
    netCDF dimensions: beam, range, time(unlimited).
      time   (time,)               units='seconds since YYYY-MM-DD HH:MM:SS +07:00' (LT)
      beam   (beam,) int           0-based (tplot variable name uses beam+1)
      range  (range,) km
      height (beam, range) km
      pwr/width/dpl (beam, time, range)  ; missing 1e10 -> NaN
      pnoise (beam, time) [dB]           ; missing 1e10 -> NaN
      nfft   () int                a scalar used in the SNR calculation

    Returns dict or None:
      time (Nt,) unix seconds UT, beam (Nbeam,), height (Nbeam,Nr) km,
      pwr/wdt/dpl (Nbeam,Nt,Nr), pn (Nbeam,Nt), nfft (int).
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
        nfft = int(np.asarray(ds.variables["nfft"][:]).ravel()[0])
        return {
            "time": unix_time,
            "beam": beam,
            "nfft": nfft,
            "height": np.asarray(ds.variables["height"][:], dtype=np.float64),  # (beam, range)
            "pwr": _nan_missing(ds.variables["pwr"][:]),     # (beam, time, range)
            "wdt": _nan_missing(ds.variables["width"][:]),
            "dpl": _nan_missing(ds.variables["dpl"][:]),
            "pn": _nan_missing(ds.variables["pnoise"][:]),   # (beam, time)
        }
    finally:
        ds.close()


def _load_ear_fai(datatype, parameters, trange, no_update, downloadonly,
                  time_clip, ror, suffix, notplot):
    """Load EAR FAI data and create tplot variables.

    datatype is e_region/ef_region/v_region/f_region. The pathformat and
    processing are common to all regions, and the server-side .nc files live in
    the same directory regardless of datatype; only the local storage directory
    is split per region (fai/<region>/nc).

    Created variables (parameter=P, beam number=B):
      iug_ear_faiP_pwrB / _wdtB / _dplB / _snrB  (2D spec, v=height(beam))
      iug_ear_faiP_pnB                            (1D, noise level)
    """
    subdir = _FAI_SUBDIR[datatype]
    t0 = time_double(trange[0])
    t1 = time_double(trange[1])
    # The daily file names use the range [t0, t1+7h] (the window shift only
    # affects the global timespan, not the daily-name listing). The trop loader
    # is the same, but for FAI the pn row-count quirk (below) depends on the file
    # set, so the day set must match the original exactly.
    win_trange = [time_string(t0), time_string(t1 + _LT_SHIFT)]

    local_dir = os.path.join(CONFIG["local_data_dir"], "rish", "misc", "ktb",
                             "ear", "fai", subdir, "nc")

    loaded = {} if notplot else []
    dl_files = []

    for param in parameters:
        # pathformat: 'YYYY/YYYYMMDD/YYYYMMDD.fai'+param+'.nc'
        file_format = "%Y/%Y%m%d/%Y%m%d.fai" + param + ".nc"
        remote_names = sorted(set(dailynames(file_format=file_format, trange=win_trange,
                                             res=24 * 3600.0)))
        # The www2 certificate cannot be verified (CERTIFICATE_VERIFY_FAILED),
        # so SSL verification is disabled with verify=False (www returns 404 for
        # paths under data and cannot be used).
        files = download(remote_file=remote_names, remote_path=_FAI_REMOTE,
                         local_path=local_dir, no_download=no_update, last_version=True,
                         verify=False)
        out_files = sorted(f for f in (files or []) if os.path.isfile(f))
        dl_files += out_files

        if downloadonly:
            continue
        if not out_files:
            continue

        recs = [d for d in (_read_ear_fai(f) for f in out_files) if d is not None]
        if not recs:
            continue

        last = recs[-1]                       # use the beam/height of the last file
        beam = last["beam"]
        nbeam = beam.size
        height_beam = last["height"]          # (beam, range)
        nfft = last["nfft"]

        ear_time = _concat_time([d["time"] for d in recs])
        # Beam arrays (beam, time, range) are concatenated along the time axis (axis=1).
        pwr = _concat_time([d["pwr"] for d in recs], axis=1)
        wdt = _concat_time([d["wdt"] for d in recs], axis=1)
        dpl = _concat_time([d["dpl"] for d in recs], axis=1)
        pn = _concat_time([d["pn"] for d in recs], axis=1)   # (beam, time)

        # ===== SNR = pwr - (pnoise + alog10(nfft)), beam x time x range =====
        # Computed in float32 to match the original bit-for-bit. SNR uses the
        # complete (pre-clip) pwr/pn concatenation (every row has a value), so
        # the pn row-count quirk (pn_buggy below) does not affect SNR.
        log_nfft = np.float32(np.log10(np.float32(nfft)))
        snr = (pwr.astype(np.float32)
               - (pn.astype(np.float32)[:, :, None] + log_nfft)).astype(np.float32)

        # ===== reproduce the pn row-count quirk of the original =====
        # The original fills the store-time pn into an array of length
        # n_elements(ear_time) but loops only up to the time count of the LAST
        # file read (nt_last); the tail of the longer concatenated array
        # (index >= nt_last) stays 0. pwr/wdt/dpl/snr loop over the full length,
        # so they are not affected.
        nt_last = int(recs[-1]["time"].size)
        pn_buggy = pn.astype(np.float64).copy()        # (beam, time_concat)
        if nt_last < pn_buggy.shape[1]:
            pn_buggy[:, nt_last:] = 0.0

        # ===== edge-clip (UT [t0, t1]) =====
        tmask = (ear_time >= t0) & (ear_time <= t1)
        if not np.any(tmask):
            continue
        ct = ear_time[tmask]

        def _store(name, y, v, ztitle, spec=True, pn_title=None):
            # store_data then gap-fill. The gap fill adds rows to x,y only; the
            # 1D v(height) has a different dimension from y and is left as-is.
            dt, dy = _idl_xdegap(ct, y)
            if notplot:
                loaded[name] = ({"x": dt, "y": dy, "v": v} if v is not None
                                else {"x": dt, "y": dy})
                return
            if v is not None:
                store_data(name, data={"x": dt, "y": dy, "v": v})
            else:
                store_data(name, data={"x": dt, "y": dy})
            if spec:
                options(name, "spec", 1)
                options(name, "ytitle", "EAR-iono!CHeight!C[km]")
                options(name, "ztitle", ztitle)
            else:
                options(name, "ytitle", pn_title)
            loaded.append(name)

        base = "iug_ear_fai" + param
        for l in range(nbeam):
            bn = str(int(round(beam[l])) + 1)        # tplot name uses beam+1
            hb = height_beam[l, :]                    # (range,) height of beam l
            _store(base + "_pwr" + bn + suffix, pwr[l][tmask, :], hb,
                   "pwr" + bn + "!C[dB]")
            _store(base + "_wdt" + bn + suffix, wdt[l][tmask, :], hb,
                   "wdt" + bn + "!C[m/s]")
            _store(base + "_dpl" + bn + suffix, dpl[l][tmask, :], hb,
                   "dpl" + bn + "!C[m/s]")
            _store(base + "_snr" + bn + suffix, snr[l][tmask, :], hb,
                   "snr" + bn + "!C[dB]")
            _store(base + "_pn" + bn + suffix, pn_buggy[l][tmask], None, None,
                   spec=False, pn_title="pn" + bn + "!C[dB]")

    if downloadonly:
        return sorted(set(dl_files))

    if ror and ((notplot and loaded) or (not notplot and loaded)):
        _print_ack()
    if (not notplot) and loaded:
        print("**********************************************************************")
        print("Data loading is successful!!")
        print("**********************************************************************")
    return loaded


def ear(
    trange=["2001-10-13", "2001-10-14"],
    site="",
    datatype="troposphere",
    parameter="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    ror=True,
    suffix="",
):
    """Load Equatorial Atmosphere Radar (EAR) data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] (UT) with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. A sub-day range still
        loads a full day. Files are fetched accounting for the LT(+07)->UT
        offset, then edge-clipped to the UT range.
        Default: ['2001-10-13', '2001-10-14']
    site : str
        Accepted for compatibility; the only EAR site is Kototabang.
        Default: ''
    datatype : str or list of str
        Observation mode. 'all' selects every mode. Valid options:
        troposphere / e_region / ef_region / v_region / f_region.
        Default: 'troposphere'
    parameter : str or list of str
        FAI-mode parameter(s) (ignored for troposphere). 'all' loads every
        parameter.
        Default: 'all'
    no_update : bool
        If set, only load data from the local cache.
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
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created. Empty list if no data were loaded. For
        troposphere these are
        ``iug_ear_trop_{uwnd,vwnd,wwnd,pwr1-5,wdt1-5,dpl1-5,pn1-5}``. If
        ``downloadonly`` is set, the list of downloaded file paths is returned;
        if ``notplot`` is set, a dictionary of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.ear(trange=['2001-10-13', '2001-10-14'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    datatypes = _normalize(datatype, DATATYPE_ALL)
    if not datatypes:
        print("This datatype is not valid. Please input: all, troposphere, "
              "e_region, ef_region, v_region, f_region.")
        return {} if notplot else []

    loaded = {} if notplot else []
    dl = []
    for dt in datatypes:
        if dt == "troposphere":
            res = _load_ear_trop(trange, no_update, downloadonly, time_clip,
                                 ror, suffix, notplot)
        else:
            # FAI (e/ef/v/f_region): normalize against the per-datatype parameters.
            params = _normalize(parameter, _FAI_PARAMETER[dt])
            if not params:
                print(f"No valid EAR FAI parameter for datatype '{dt}'.")
                continue
            res = _load_ear_fai(dt, params, trange, no_update, downloadonly,
                                time_clip, ror, suffix, notplot)
        if downloadonly:
            dl += res
        elif notplot:
            loaded.update(res)
        else:
            loaded += res

    if downloadonly:
        return sorted(set(dl))
    return loaded


def _print_ack():
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(_ACK)
