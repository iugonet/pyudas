"""Load function for Tohoku University IPRT (Iitate Planetary Radio Telescope / AMATERAS) daily low-resolution solar radio data.

Reads daily low-resolution FITS files (one per day) with astropy and stores the
RH/LH polarization dynamic spectra as ``iprt_sun_R`` / ``iprt_sun_L``. Because the
data are FITS rather than CDF, the shared loader is not used; .fits files are
fetched with pyspedas ``download`` and parsed locally.

FITS structure:
  Single Primary HDU, BITPIX=8 (uint8), NAXIS=(NAXIS1=time, NAXIS2=freq, 2=pol).
  astropy returns data in the order data[pol, freq, time] (axes reversed
  relative to the original data[time, freq, pol]).
  BZERO=0.0, BSCALE=1.0 -> no scaling (kept as uint8).
  BUNIT='10*(dB from Quiet SUN)' -> values are 10x dB, so divide by 10 at the
  end.
  CTYPE1='Time in UT', CTYPE2='Frequency in MHz'.
  CRVAL1=0, CRPIX1=0, CDELT1~0.99968s (time axis), CRVAL2=100, CRPIX2=0,
  CDELT2=1 -> 100-509 MHz (410 points).
  DATE-OBS/TIME-OBS mark the observation start, which can fall on the day
  before the file-name date (e.g. file 20101103 has DATE-OBS='2010-11-02'
  TIME-OBS='23:43:06').

Time and axes:
  date_start = time_double(DATE-OBS + '/' + TIME-OBS)
  time = date_start + CRVAL1 + (arange(NAXIS1) - CRPIX1) * CDELT1
  freq = CRVAL2 + (arange(NAXIS2) - CRPIX2) * CDELT2

Data:
  data[*,*,0] is RH, data[*,*,1] is LH. astropy's data[0] is (freq, time), so
  it is transposed to y=[time, freq]. Finally each is divided by 10 (10*dB ->
  dB).

Distribution: http://radio.gp.tohoku.ac.jp/db/IPRT-SUN/DATA2/  YYYY/YYYYMMDD_IPRT.fits
"""
import os

import numpy as np

from pyspedas import store_data, options, time_double, dailynames, download

from iugonet.config import CONFIG

# Available datatypes.
DATATYPE_ALL = ["Sun"]

_REMOTE = "http://radio.gp.tohoku.ac.jp/db/IPRT-SUN/DATA2/"

_ACK = (
    'We would like to present the following two guidelines. The 1st one '
    'concerns what we would like you to do when you use the data. 1. Tell us '
    'what you are working on. This is partly because to protect potential Ph.D. '
    'thesis projects. Also, if your project coincides with one that team members '
    'are working on, that can lead to a fruitful collaboration. The 2nd one '
    'concerns what you do when you make any presentations and publications using '
    'the data. 2. Co-authorship: When the data forms an important part of your '
    'work, we would like you to offer us co-authorship. 3. Acknowledgements: All '
    'presentations and publications should carry the following sentence: '
    '"IPRT(Iitate Planetary Radio Telescope) is a Japanese radio telescope '
    'developed and operated by Tohoku University." 4. Entry to publication list: '
    'When your publication is accepted, or when you make a presentation at a '
    'conference on your result, please let us know by sending email to PI. '
    'Contact person & PI: Dr. Hiroaki Misawa (misawa@pparc.gp.tohoku.ac.jp)'
)


def _read_iprt_fits(path):
    """Read one daily IPRT FITS file and return time, frequency, and RH/LH data.

    Returns dict or None:
      time (Nt,) unix seconds UT, freq (Nf,) MHz,
      data_r/data_l (Nt, Nf) float64 derived from uint8 (not yet divided by 10).
    """
    from astropy.io import fits

    try:
        hdul = fits.open(path, do_not_scale_image_data=True)
    except (OSError, ValueError):
        return None
    try:
        hd = hdul[0].header
        # astropy layout (pol, freq, time). BZERO=0/BSCALE=1 keeps it as uint8.
        data = np.asarray(hdul[0].data)   # (2, NAXIS2, NAXIS1) uint8
    finally:
        hdul.close()

    n1 = int(hd["NAXIS1"])   # time
    n2 = int(hd["NAXIS2"])   # freq
    crval1 = float(hd["CRVAL1"]); crpix1 = float(hd["CRPIX1"]); cdelt1 = float(hd["CDELT1"])
    crval2 = float(hd["CRVAL2"]); crpix2 = float(hd["CRPIX2"]); cdelt2 = float(hd["CDELT2"])

    date_obs = str(hd["DATE-OBS"]).strip()
    time_obs = str(hd["TIME-OBS"]).strip()
    date_start = float(time_double(date_obs + "/" + time_obs))

    timearr = date_start + crval1 + (np.arange(n1, dtype=np.float64) - crpix1) * cdelt1
    freq = crval2 + (np.arange(n2, dtype=np.float64) - crpix2) * cdelt2

    # data[*,*,0]=R, data[*,*,1]=L. astropy's data[0] is (freq, time); transpose
    # to (time, freq).
    data_r = np.asarray(data[0], dtype=np.float64).T   # (time, freq)
    data_l = np.asarray(data[1], dtype=np.float64).T

    return {"time": timearr, "freq": freq, "data_r": data_r, "data_l": data_l}


def iprt(
    trange=["2010-11-03", "2010-11-04"],
    datatype="Sun",
    site="",
    no_update=False,
    downloadonly=False,
    notplot=False,
    verbose=False,
    ror=True,
    suffix="",
):
    """Load IPRT/AMATERAS daily low-resolution solar radio data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss'] (UT). Daily files are
        fetched; a full day is read even for a sub-day range.
        Default: ['2010-11-03', '2010-11-04']
    datatype : str
        Type of data to load. Valid options: Sun.
        Default: 'Sun'
    site : str
        Unused; accepted for interface compatibility.
        Default: ''
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
    verbose : bool
        Verbosity level for diagnostic messages.
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
        List of tplot variables created (['iprt_sun_R', 'iprt_sun_L']). Empty
        list if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.iprt(trange=['2010-11-03', '2010-11-04'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    file_format = "%Y/%Y%m%d_IPRT.fits"
    remote_names = sorted(set(
        dailynames(file_format=file_format, trange=trange, res=24 * 3600.0)
    ))

    local_dir = os.path.join(CONFIG["local_data_dir"], "tohokuU", "iit")
    files = download(
        remote_file=remote_names,
        remote_path=_REMOTE,
        local_path=local_dir,
        no_download=no_update,
        last_version=True,
    )
    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files
    if not out_files:
        print("No IPRT data found in " + str(trange))
        return {} if notplot else []

    # ----- Read all files and concatenate along time -----
    recs = [d for d in (_read_iprt_fits(f) for f in out_files) if d is not None]
    if not recs:
        print("No valid IPRT data parsed in " + str(trange))
        return {} if notplot else []

    timebuf = np.concatenate([d["time"] for d in recs])
    databufR = np.concatenate([d["data_r"] for d in recs], axis=0)   # (time, freq)
    databufL = np.concatenate([d["data_l"] for d in recs], axis=0)
    freq = recs[-1]["freq"]   # use the freq of the last file read

    # ----- Unit conversion 10*dB -> dB -----
    # The division by 10 promotes the byte data to float32; keep float32 to
    # match the original output bit-for-bit.
    databufR = (databufR / 10.0).astype(np.float32)
    databufL = (databufL / 10.0).astype(np.float32)

    name_r = "iprt_sun_R" + suffix
    name_l = "iprt_sun_L" + suffix

    if notplot:
        if ror:
            _print_ack()
        return {
            name_l: {"x": timebuf, "y": databufL, "v": freq},
            name_r: {"x": timebuf, "y": databufR, "v": freq},
        }

    store_data(name_l, data={"x": timebuf, "y": databufL, "v": freq})
    store_data(name_r, data={"x": timebuf, "y": databufR, "v": freq})

    # ----- options -----
    # ytitle is taken from CTYPE2 = 'Frequency in MHz'.
    ctype2 = "Frequency in MHz"
    for nm, sub, lab in ((name_l, "LCP", "IPRT_SUN_LCP"),
                         (name_r, "RCP", "IPRT_SUN_RCP")):
        options(nm, "spec", 1)
        options(nm, "labels", [lab])
        options(nm, "ytitle", ctype2)
        options(nm, "ysubtitle", sub)
        options(nm, "ztitle", "dB from background")
        options(nm, "datagap", 10)

    if ror:
        _print_ack()

    print("******************************")
    print("Data loading is successful!!")
    print("******************************")

    return [name_r, name_l]


def _print_ack():
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(_ACK)
