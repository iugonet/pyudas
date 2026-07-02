"""Load function for Tohoku University IPRT / AMATERAS per-minute high-resolution (Level-1) solar radio data.

Fetches high-resolution FITS files per minute (one file per minute), converts
each file with ``fits_to_tplot`` into ``iprt_r`` / ``iprt_l``, and concatenates
them along time.

File name (file_dailynames, res=60s):
  high{08|16}/YYYY/YYYYMMDD/iprt_amt_l1_high_{08|16}bit_YYYYMMDD-hhmm_v{NN}.fits
  numbit=8 or 16 (default 8, both res=60s). version default 1 (-> 'v01').

Distribution: http://radio.gp.tohoku.ac.jp/db/IPRT-SUN/l1/

The data-unit handling follows fits_to_tplot (astropy's BZERO/BSCALE-applied
float32 is used directly; raw dB). subtract_bg is applied during each file's
conversion.
"""
import os

import numpy as np

from pyspedas import store_data, options, dailynames, download
from pyspedas.tplot_tools import zlim

from iugonet.config import CONFIG
from iugonet.ground.fits_to_tplot import fits_to_tplot

# Available datatypes.
DATATYPE_ALL = ["Sun"]

_REMOTE = "http://radio.gp.tohoku.ac.jp/db/IPRT-SUN/l1/"

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


def iprt_highres(
    trange=["2014-02-12/00:06:00", "2014-02-12/00:09:00"],
    datatype="Sun",
    numbit=8,
    version=1,
    subtract_bg=False,
    site="",
    no_update=False,
    downloadonly=False,
    notplot=False,
    verbose=False,
    ror=True,
    suffix="",
):
    """Load IPRT/AMATERAS per-minute high-resolution solar radio data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. Files are fetched per
        minute (res=60s). The high-resolution data are large (~78 MB per
        minute), so specify only the range you need.
        Default: ['2014-02-12/00:06:00', '2014-02-12/00:09:00']
    datatype : str
        Type of data to load. Valid options: Sun.
        Default: 'Sun'
    numbit : int
        Bit depth used in the file name and subdirectory. Valid options: 8, 16.
        Default: 8
    version : int
        Product version (e.g. 1 -> 'v01').
        Default: 1
    subtract_bg : bool
        If True, subtract the per-frequency background (time-axis minimum);
        propagated to fits_to_tplot. Valid options: True, False.
        Default: False
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
        List of tplot variables created (['iprt_r', 'iprt_l']). Empty list if
        no data were loaded. If ``downloadonly`` is set, the list of downloaded
        file paths is returned; if ``notplot`` is set, a dictionary of data is
        returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.iprt_highres(trange=['2014-02-12/00:06:00', '2014-02-12/00:09:00'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    if numbit not in (8, 16):
        print("The numbit must be 8 or 16.")
        return {} if notplot else []
    res = 60
    strbit = "%02d" % int(numbit)
    strver = "%02d" % int(version)

    # File name, e.g.
    # high08/YYYY/YYYYMMDD/iprt_amt_l1_high_08bit_YYYYMMDD-hhmm_v01.fits
    file_format = (
        "high" + strbit + "/%Y/%Y%m%d/iprt_amt_l1_high_" + strbit
        + "bit_%Y%m%d-%H%M_v" + strver + ".fits"
    )
    remote_names = sorted(set(
        dailynames(file_format=file_format, trange=trange, res=float(res))
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
        print("No IPRT highres data found in " + str(trange))
        return {} if notplot else []

    # ----- Convert each file with fits_to_tplot and concatenate along time -----
    # Use a dedicated suffix during conversion to avoid temporary-variable name
    # collisions, then aggregate at the end.
    from pyspedas import get_data

    xvec_r = []; yvec_r = []; vvec_r = None
    xvec_l = []; yvec_l = []; vvec_l = None
    for path in out_files:
        try:
            fits_to_tplot(path, subtract_bg=subtract_bg, suffix="_tmp_hr")
        except Exception as e:
            print("fits_to_tplot failed for " + path + ": " + str(e))
            continue
        dr = get_data("iprt_r_tmp_hr")
        dl = get_data("iprt_l_tmp_hr")
        if dr is None or dl is None:
            continue
        xvec_r.append(np.asarray(dr.times, dtype=np.float64))
        yvec_r.append(np.asarray(dr.y, dtype=np.float64))
        vvec_r = np.asarray(dr.v, dtype=np.float64)
        xvec_l.append(np.asarray(dl.times, dtype=np.float64))
        yvec_l.append(np.asarray(dl.y, dtype=np.float64))
        vvec_l = np.asarray(dl.v, dtype=np.float64)

    # Clean up the temporary variables.
    try:
        from pyspedas import del_data
    except ImportError:
        from pyspedas.tplot_tools import del_data
    del_data("iprt_r_tmp_hr")
    del_data("iprt_l_tmp_hr")

    if not xvec_r:
        print("No valid IPRT highres data parsed in " + str(trange))
        return {} if notplot else []

    x_r = np.concatenate(xvec_r); y_r = np.concatenate(yvec_r, axis=0)
    x_l = np.concatenate(xvec_l); y_l = np.concatenate(yvec_l, axis=0)

    name_r = "iprt_r" + suffix
    name_l = "iprt_l" + suffix

    if notplot:
        if ror:
            _print_ack()
        return {
            name_r: {"x": x_r, "y": y_r, "v": vvec_r},
            name_l: {"x": x_l, "y": y_l, "v": vvec_l},
        }

    store_data(name_r, data={"x": x_r, "y": y_r, "v": vvec_r})
    store_data(name_l, data={"x": x_l, "y": y_l, "v": vvec_l})

    # ----- options (re-applied after concatenation) -----
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

    if ror:
        _print_ack()

    return [name_r, name_l]


def _print_ack():
    print("****************************************************************")
    print("Acknowledgement")
    print("****************************************************************")
    print(_ACK)
