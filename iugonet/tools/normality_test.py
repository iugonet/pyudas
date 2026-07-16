"""Chi-square goodness-of-fit test for normality.

Port of ``iugonet/tools/statistical_package/normality_test.pro``.
"""
import numpy as np

from iugonet.tools.idl_compat import (chisqr_cvf, finite_only, gaussint,
                                             idl_mean, idl_stddev, idl_total)

__all__ = ["normality_test"]


def normality_test(x, sl=None, mv=None, quiet=False):
    """IDL ``normality_test(x, sl=, mv=)``: chi-square test against a normal fit.

    Returns
    -------
    int
        0 if normal, 1 if not normal -- IDL's convention.

    Notes
    -----
    Binning follows the original exactly, quirks included:

    - ``nK = round(nc/40.0)`` for nc>=400, else the **float** ``10.0``. The
      loop bound ``for j=0L,nK-2`` then runs over a float limit.
    - Bin edges use ``ge``/``lt`` except the last bin, which uses ``ge``/``le``
      so the maximum is included.
    - For ``nK >= 15`` the ``round(nK/20.0)`` outermost bins at each end are
      dropped ("Section is cut the ends of large errors").

    The IDL original also calls ``window, 2`` and ``plot`` before computing its
    return value; this port omits the plotting (the comparison harness runs IDL
    under a virtual X display so the reference still produces a result).
    """
    c = finite_only(x, mv=mv)

    nc = c.size
    x_max = float(np.max(c))
    x_min = float(np.min(c))
    x_mean = idl_mean(c, single=True)
    x_stddev = idl_stddev(c, single=True)

    # Number of intervals: data points / 40, fixed at 10 below 400 points.
    if nc >= 400:
        nk = float(np.round(nc / 40.0))
    else:
        nk = 10.0
    x_d = np.float32((x_max - x_min) / nk)

    y = []
    z1 = []
    for j in range(int(nk) - 1):
        r1 = np.where((c >= (x_min + x_d * j)) & (c < (x_min + x_d * (j + 1))))[0]
        y.append(r1.size)
        z1.append(x_min + x_d * j)
    # The last bin is closed on the right so that x_max falls inside it.
    rx = np.where((c >= (x_min + x_d * (nk - 1))) & (c <= x_max))[0]
    y.append(rx.size)
    z1.append(x_min + x_d * (nk - 1))
    z1.append(x_min + x_d * nk)

    y = np.asarray(y, dtype=np.float64)
    z1 = np.asarray(z1, dtype=np.float64)

    z2 = np.asarray([float(gaussint((z1[i] - x_mean) / x_stddev))
                     for i in range(int(nk) + 1)], dtype=np.float64)
    z3 = np.asarray([(z2[i + 1] - z2[i]) * nc for i in range(int(nk))],
                    dtype=np.float64)   # expected frequency

    if nk >= 15:
        lo = int(np.round(nk / 20.0))
        hi = int(nk - np.round(nk / 20.0))
        z4 = [((y[i] - z3[i]) ** 2.0) / z3[i] for i in range(lo, hi)]
    else:
        z4 = [((y[i] - z3[i]) ** 2.0) / z3[i] for i in range(int(nk))]
    sum_z4 = idl_total(np.asarray(z4, dtype=np.float64), double=True)

    level = sl if sl else 0.05
    v = chisqr_cvf(level, int(nk) - 1 - 2)
    if sum_z4 <= v:
        char = "   NORMAL DISTRIBUTION with significance level ="
        result = 0
    else:
        char = "   NOT NORMAL DISTRIBUTION with significance level ="
        result = 1
    if not quiet:
        print("comment:", char, level)
    return result
