"""Rank-based test for a significant trend in a time series.

Ports of ``iugonet/tools/statistical_package/trend_test.pro`` (raw array) and
``utrend_test.pro`` (tplot variable).
"""
import numpy as np

from iugonet.tools.idl_compat import (gauss_cvf, idl_mean, idl_total,
                                             t_cvf)

__all__ = ["trend_test", "utrend_test"]

_F32 = np.float32


def _rank_descending(y1, n):
    """IDL's ranking loop: descending, ties share the mean rank, ``-1e4`` sentinel.

    ``scipy.stats.rankdata`` is **not** equivalent -- this ranks high-to-low and
    marks consumed values with a sentinel, so a series that actually contains
    ``-1e4`` terminates the loop early and mis-ranks the rest. The sentinel is
    reproduced rather than fixed. Ranks land in ``fltarr`` (float32).
    """
    y2 = np.zeros(int(n), dtype=_F32)
    counter = 1
    y_tmp = np.asarray(y1, dtype=np.float64).copy()
    while y_tmp.max() != -1e4:
        m = y_tmp.max()
        aaa = np.where(y_tmp == m)[0]
        bbb = aaa.size
        rank = counter + (bbb - 1) / 2.0
        y2[aaa] = _F32(rank)
        y_tmp[aaa] = -1e4
        counter = counter + bbb
    return y2


def _trend_stats(y0, sl):
    """trend_test / utrend_test で共通の統計量を返す。

    Returns (Z, n, y1, y2, E, V, b1, b0, b1_thr, thr_t).
    """
    y0 = np.asarray(y0, dtype=np.float64).ravel()
    # IDL: append_array,y1,y0[i] -- note there is no float() here, unlike
    # welch_test, so y1 keeps the input's precision.
    y1 = y0[np.isfinite(y0)]

    n = _F32(y1.size)
    # Everything below is single precision because `n = float(...)`. At n=1024
    # n^3 is ~1.07e9, where the float32 ulp is 64 -- so Z carries ~1e-5 of
    # single-precision noise by construction. Widening it here would *not*
    # match IDL.
    e_val = _F32((n ** 3 - n) / _F32(6.0))
    v_val = _F32((n ** 2 * (n + 1) ** 2 * (n - 1)) / _F32(36.0))

    y2 = _rank_descending(y1, n)

    # Confidence interval of the regression curve.
    x = np.arange(int(n), dtype=_F32)
    xm = _F32(idl_mean(x, single=True))
    ym = _F32(idl_mean(y1.astype(_F32), single=True)) if y1.dtype == np.float32 \
        else idl_mean(y1)
    sxx = idl_total(((x - xm) ** 2).astype(_F32))
    sxy = idl_total(((x - xm) * (y1 - ym)).astype(np.float64), double=True)
    b1 = sxy / sxx
    b0 = ym - b1 * xm
    y1b = b1 * x + b0
    e2 = idl_total(((y1b - y1) ** 2).astype(np.float64), double=True)
    b1_thr = t_cvf(sl / 2.0, n - 2) * np.sqrt((e2 / (n - 2)) / sxx)

    idx = (np.arange(int(n), dtype=_F32) + _F32(1.0)).astype(_F32)
    y2d = _F32(_F32(_F32(1.0) / _F32(3.0)) * n * (n + 1) * (2 * n + 1)
               - _F32(2) * _F32(idl_total((y2 * idx).astype(_F32))))
    z = _F32((y2d - e_val) / np.sqrt(v_val, dtype=np.float32))

    # IDL: thr_t=-gauss_cvf(sl). Kept negative, as IDL does, so that the
    # `-thr_t` at every use site reads the same as the original.
    return z, n, y1, y2, e_val, v_val, b1, b0, b1_thr, -gauss_cvf(sl)


def trend_test(y0, sl=None, quiet=False):
    """IDL ``trend_test, y0, Z, sl=``: is there a significant trend?

    Returns
    -------
    float
        ``Z``, the test statistic (IDL returns it through the output argument).

    Notes
    -----
    IDL computes ``Z`` in single precision throughout (see :func:`_trend_stats`)
    and then, at the very end, calls ``window, 3`` and plots. This port omits
    the plotting.

    Parameters
    ----------
    y0 : array
        Non-finite entries are dropped.
    sl : float or None
        Significance level. Default 0.05.
    quiet : bool
        Suppress the console report.
    """
    if not sl:
        sl = 0.05
    z, n, y1, y2, e_val, v_val, b1, b0, b1_thr, thr_t = _trend_stats(y0, sl)
    if not quiet:
        print("t=", z)
        # IDL writes 'Max　|t| =' with a full-width space; kept verbatim.
        print("Max　|t| =", e_val / np.sqrt(v_val, dtype=np.float32))
        print("Threshold (at S_Level    =", sl, ")   :", -thr_t)
        print("slope", b1)
        print("error of slope", b1_thr)
    return float(z)


def utrend_test(vname1, sl=None, quiet=False):
    """IDL ``utrend_test, vname1, sl=``: :func:`trend_test` for a tplot variable.

    IDL's version has **no output argument** -- it only prints ``Z``, the
    threshold and the slope to the console, then plots. This port returns ``Z``
    as well, which is strictly more useful and costs nothing; the printed
    report is kept identical so it can be compared against IDL's.

    Parameters
    ----------
    vname1 : str
        tplot variable name.
    sl : float or None
        Significance level. Default 0.05.
    quiet : bool
        Suppress the console report.
    """
    from pyspedas import get_data, tnames

    if not tnames(vname1):
        print("Cannot find the tplot vars in argument!")
        return None
    if not sl:
        sl = 0.05
    d1 = get_data(vname1)
    z, n, y1, y2, e_val, v_val, b1, b0, b1_thr, thr_t = _trend_stats(d1.y, sl)
    if not quiet:
        print("-------------------trend test result--------------------------")
        print("Z=", z)
        print("Max　|Z| =", e_val / np.sqrt(v_val, dtype=np.float32))
        print("Threshold (at S_Level    =", sl, ")   :", -thr_t)
        if abs(z) < -thr_t:
            print("No significant trend")
        else:
            if z < 0:
                print("There is a negative trend.")
            if z > 0:
                print("There is a positive trend.")
        print("slope", b1)
        print("error of slope", b1_thr)
        print("---------------------------------------------------------------")
    return float(z)
