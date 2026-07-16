"""S-transform power spectrum of a tplot variable.

Port of ``iugonet/tools/statistical_package/ustrans_pwrspc.pro``.
"""
import numpy as np

from iugonet.tools.s_trans import s_trans
from iugonet.tools.tdeflag import tdeflag

__all__ = ["ustrans_pwrspc"]


def ustrans_pwrspc(varname, factor=1, newname=None, trange=None,
                   samplingrate=None, maxfreq=None, minfreq=None,
                   freqsamplingrate=None, power=False, abs=False,
                   removeedge=False, maskedges=None, verbose=False):
    """IDL ``ustrans_pwrspc, varname, factor, samplingrate=, ...``.

    Runs :func:`~iugonet.tools.s_trans.s_trans` over a tplot variable and
    stores the result as ``<varname>_stpwrspc``, a spectrogram whose y axis is
    period (``1/freq``).

    Multi-component variables are split with ``split_vec`` and each component is
    transformed separately, as in IDL.

    Parameters
    ----------
    varname : str
        tplot variable name.
    factor : float
        Window width scaling, passed to :func:`s_trans`. Default 1.
    samplingrate : float
        **Required in practice.** Without it ``s_trans`` returns a bare array
        rather than a structure and IDL dies on ``y1.st``; the IDL wrapper does
        not default it either.
    abs, power : bool
        One of these is needed too: otherwise ``s_trans`` returns a *complex*
        spectrum and ``store_data`` gets complex ``y``.
    trange : list or None
        Restrict to ``['start', 'end']`` before transforming.
    newname : str or None
        Accepted for signature parity but **ignored**: IDL overwrites it with
        ``varname+'_stpwrspc'`` before use, so passing it has no effect.
    maxfreq, minfreq, freqsamplingrate, removeedge, maskedges, verbose :
        Passed through to :func:`s_trans`.

    Notes
    -----
    - ``tdeflag, varname, "linear", /overwrite`` runs first and **modifies the
      input variable in place** -- that is IDL's behaviour, reproduced here.
      See :mod:`iugonet.tools.tdeflag` for why pyspedas' ``deflag`` is
      not a substitute.
    - The stored ``v`` axis is ``1/y1.freq`` and ``freq[0]`` is 0, so
      ``v[0]`` is ``+Inf`` -- in IDL as well as here.
    - :func:`s_trans` is O(N^2 log N) in time and O(N^2/2) in memory, so keep
      the variable short (a 1440-point day of 1-min data is fine; a day of 1-s
      data is not).
    """
    from pyspedas import get_data, options, store_data, time_double, zlim
    from pyspedas import split_vec

    print(varname)
    tdeflag(varname, "linear", overwrite=True)
    d = get_data(varname)
    meta = get_data(varname, metadata=True)
    if d is None:
        print("No data in " + varname)
        return None

    y = np.asarray(d.y)
    if y.ndim == 2:
        ndj = y.shape[1]
        if ndj == 3:
            vn_j = split_vec(varname)
        else:
            vn_j = split_vec(varname)
        for nm in vn_j:
            ustrans_pwrspc(nm, factor, trange=trange, verbose=verbose,
                           samplingrate=samplingrate, maxfreq=maxfreq,
                           minfreq=minfreq, freqsamplingrate=freqsamplingrate,
                           power=power, abs=abs, removeedge=removeedge,
                           maskedges=maskedges)
        return None

    nvn = varname + "_stpwrspc"
    t = np.asarray(d.times, dtype=np.float64)
    y = y.astype(np.float64)

    if trange is not None and len(trange) == 2:
        tr = [time_double(trange[0]), time_double(trange[1])]
        ok = np.where((t >= tr[0]) & (t < tr[1]))[0]
        if ok.size == 0:
            print("No data in time range")
            print("No Dynamic Power spectrum for: " + varname)
            return None
        t = t[ok]
        y = y[ok]

    ok = np.where(np.isfinite(y))[0]
    if ok.size == 0:
        print("No finite data in time range")
        return None
    t = t[ok]
    y = y[ok]

    t00 = np.asarray(d.times, dtype=np.float64)[0]
    t = t - t00

    y1 = s_trans(y, factor, samplingrate=samplingrate, maxfreq=maxfreq,
                 minfreq=minfreq, freqsamplingrate=freqsamplingrate,
                 power=power, abs=abs, removeedge=removeedge,
                 maskedges=maskedges, verbose=verbose)

    # freq[0] is 0, so the first period is +Inf -- as in IDL.
    with np.errstate(divide="ignore"):
        v = 1.0 / np.asarray(y1["freq"], dtype=np.float64)

    print(nvn)
    store_data(nvn, data={"x": t + t00, "y": y1["st"], "v": v},
               attr_dict=meta)
    options(nvn, "spec", 1)
    options(nvn, "ytitle", nvn + "\nPeriod")
    options(nvn, "ztitle", "Amplitude")
    zlim(nvn, 0, float(np.max(y1["st"])))
    return nvn
