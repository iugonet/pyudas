"""Convert a single IPRT/AMATERAS high-resolution FITS file into tplot variables.

Opens a single high-resolution .fits (one-minute file) with astropy and stores
the RH/LH polarization dynamic spectra as ``iprt_r`` / ``iprt_l``. ``iprt_highres``
calls this per file and concatenates the returned ``iprt_r`` / ``iprt_l`` along
time.

FITS structure:
  Single Primary HDU, BITPIX=8 (uint8), NAXIS=(NAXIS1,NAXIS2,2).
  astropy returns data in the order data[axis3, axis2, axis1] = (pol, freq,
  time), i.e. the axes are reversed relative to the original data[time, freq,
  pol].
  BZERO=0.0, BSCALE=0.1 (8bit) -> astropy by default rescales to float32
  (raw_uint8 * 0.1). This matches the original behavior, in which the scaling
  is applied once and the header BSCALE/BZERO are then reset to 1.0/0.0 (so the
  subsequent BZERO + float(data)*BSCALE does not double-apply and the values
  remain raw*0.1). Therefore astropy's float32-rescaled data can be used
  directly (raw dB; not divided by 10).

Time:
  Build start/end Julian days from DATE-OBS/TIME-OBS and DATE-END/TIME-END, and
  convert to unix seconds td0, td1. delta_t = (td1-td0)/NAXIS1.
  td_data[i] = td0 + i*delta_t  (i=0..NAXIS1-1). CDELT1 is not used for the time
  calculation.

Frequency axis: y = CRVAL2 + (arange(NAXIS2) + CRPIX2) * CDELT2  [MHz].

subtract_bg: subtract the time-axis minimum per frequency (column i),
  separately for R/L. In the astropy (freq, time) layout, subtract the axis=1
  minimum from each row.
"""
import numpy as np

from pyspedas import store_data, options
from pyspedas.tplot_tools import zlim


def _jd_to_unix(year, month, day, hour, minute, second):
    """Convert a calendar date/time (UT) to unix seconds via a Julian day.

    Uses the standard Gregorian-calendar (post-1582) Julian-day algorithm and
    subtracts the unix epoch JD (1970-01-01T00:00:00 = JD 2440587.5). The
    difference of integer offsets avoids floating-point precision loss. The
    second may be fractional and is added directly.
    """
    igreg = 15 + 31 * (10 + 12 * 1582)
    jy = year
    jm = month
    if jm > 2:
        jm = jm + 1
    else:
        jy = jy - 1
        jm = jm + 13
    jd_int = int(np.floor(365.25 * jy)) + int(np.floor(30.6001 * jm)) + day + 1720995
    if (day + 31 * (month + 12 * year)) >= igreg:
        ja = int(jy // 100)
        jd_int = jd_int + 2 - ja + int(ja // 4)
    # With time of day: jd = jd_int + (hh-12)/24 + mn/1440 + ss/86400.
    jd = (jd_int + (hour - 12) / 24.0 + minute / 1440.0 + second / 86400.0)
    # unix epoch JD = 2440587.5.
    return (jd - 2440587.5) * 86400.0


def _parse_fits_datetime(date_str, time_str):
    """Extract (yy, mm, dd, hh, mn, ss) from 'YYYY-MM-DD' and 'hh:mm:ss[.fff]'.

    The seconds may be fractional, but they are truncated to an integer to match
    the original output bit-for-bit.
    """
    dparts = date_str.replace("T", "-").replace(":", "-").split("-")
    tparts = time_str.replace("T", "-").replace(":", "-").split("-")
    yy = int(dparts[0]); mm = int(dparts[1]); dd = int(dparts[2])
    hh = int(float(tparts[0]))
    mn = int(float(tparts[1])) if len(tparts) > 1 else 0
    ss = int(float(tparts[2])) if len(tparts) > 2 else 0
    return yy, mm, dd, hh, mn, ss


def fits_to_tplot(file_in, subtract_bg=False, suffix=""):
    """Convert one high-resolution IPRT FITS file into the iprt_r/iprt_l tplot variables.

    Called by ``iprt_highres`` for each .fits file. astropy's
    BZERO/BSCALE-applied float32 data are used directly (raw dB; not divided by
    10).

    Parameters
    ----------
    file_in : str
        Path to the high-resolution .fits file.
    subtract_bg : bool
        If True, subtract the time-axis minimum per frequency. Valid options:
        True, False.
        Default: False
    suffix : str
        The tplot variable names will be given this suffix (passed from
        iprt_highres; empty by default).
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created (['iprt_r'+suffix, 'iprt_l'+suffix]).

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.fits_to_tplot('iprt_amt_l1_high_08bit_20140212-0006_v01.fits')
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    from astropy.io import fits

    with fits.open(file_in) as hdul:
        hd = hdul[0].header
        # astropy applies BZERO/BSCALE and rescales to float32 by default.
        # Layout is (pol, freq, time), with axes reversed relative to the
        # original (time, freq, pol).
        data = np.asarray(hdul[0].data)   # (2, NAXIS2, NAXIS1) float32

    # ----- Time information -----
    date_obs = str(hd["DATE-OBS"]).strip()
    date_end = str(hd["DATE-END"]).strip()
    time_obs = str(hd["TIME-OBS"]).strip()
    time_end = str(hd["TIME-END"]).strip()
    ys, ms, ds_, hs, mns, ss_ = _parse_fits_datetime(date_obs, time_obs)
    ye, me, de, he, mne, se_ = _parse_fits_datetime(date_end, time_end)
    td0 = _jd_to_unix(ys, ms, ds_, hs, mns, ss_)   # start unix seconds
    td1 = _jd_to_unix(ye, me, de, he, mne, se_)    # end unix seconds

    # ----- Axis information -----
    crpix2 = float(hd["CRPIX2"])
    crval2 = float(hd["CRVAL2"])
    cdelt2 = float(hd["CDELT2"])
    m = int(hd["NAXIS1"])   # time
    n = int(hd["NAXIS2"])   # freq
    # y = CRVAL2 + (arange(n) + CRPIX2) * CDELT2  [MHz]
    y = crval2 + (np.arange(n, dtype=np.float64) + crpix2) * cdelt2

    # ----- Use the float32-rescaled (raw*0.1) data directly -----
    # astropy's data[0] is (freq, time); the float32-rescaled data match the
    # original output, so no further scaling is applied here.
    data_r = np.asarray(data[0], dtype=np.float32)   # (freq, time)
    data_l = np.asarray(data[1], dtype=np.float32)   # (freq, time)

    # ----- subtract_bg: subtract the time-axis minimum per frequency -----
    if subtract_bg:
        # In the (freq, time) layout, axis=1 is time; subtract the minimum of
        # each row (frequency). Keep float32 to match the original output.
        data_r = (data_r - data_r.min(axis=1, keepdims=True)).astype(np.float32)
        data_l = (data_l - data_l.min(axis=1, keepdims=True)).astype(np.float32)

    # tplot expects y=[time, freq], so transpose.
    y_r = data_r.T   # (time, freq)
    y_l = data_l.T

    # ----- Time array -----
    delta_t = (td1 - td0) / float(m)
    td_data = td0 + np.arange(m, dtype=np.float64) * delta_t

    name_r = "iprt_r" + suffix
    name_l = "iprt_l" + suffix
    store_data(name_r, data={"x": td_data, "y": y_r, "v": y})
    store_data(name_l, data={"x": td_data, "y": y_l, "v": y})

    # ----- options -----
    tvar = [name_r, name_l]
    for nm in tvar:
        options(nm, "spec", 1)
        options(nm, "charsize", 1.2)
        options(nm, "ysubtitle", "Frequency [MHz]")
    if not subtract_bg:
        for nm in tvar:
            options(nm, "ztitle", "[dB] from quiet Sun level")
        options(name_r, "ytitle", "IPRT RH")
        options(name_l, "ytitle", "IPRT LH")
        zlim(tvar, 0, 25.0, 0)
    else:
        for nm in tvar:
            options(nm, "ztitle", "[dB] from background")
        options(name_r, "ytitle", "IPRT LH (subtract bg)")
        options(name_l, "ytitle", "IPRT LH (subtract bg)")
        zlim(tvar, 0, 10.0, 0)

    return [name_r, name_l]
