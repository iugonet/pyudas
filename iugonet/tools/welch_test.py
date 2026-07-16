"""Welch's t-test for a difference of means.

Port of ``iugonet/tools/statistical_package/welch_test.pro``.
"""
import numpy as np

from iugonet.tools.idl_compat import (finite_only, idl_mean, idl_stddev,
                                             t_cvf)

__all__ = ["welch_test"]


def welch_test(a, b, sl=None, mv=None, quiet=False):
    """IDL ``welch_test(x, y, sl=, mv=)``: are two means the same?

    Assumes both samples are normal with unequal variance.

    Returns
    -------
    int
        1 if the means are the same, 0 if they differ -- IDL's convention.

    Notes
    -----
    The precision chain is mixed and has to be walked exactly. IDL filters the
    inputs through ``float()`` (:func:`~iugonet.tools.idl_compat.finite_only`),
    so ``x``/``y`` are **single**; ``mean``/``stddev`` are then single too. But
    ``nx``/``ny`` are ``double()``, so ``x_uv/nx`` promotes back to double and
    ``t``, ``v0`` and the ``t_cvf`` call are all double.

    ``mv`` is compared *after* the single-precision cast
    (``if(float(a[i]) eq mv)``), so a float64 -999.0000001 casts to -999.0 and
    is dropped as a missing value.

    Parameters
    ----------
    a, b : array
    sl : float or None
        Significance level. Default 0.05.
    mv : float or None
        Missing value. If unset only NaN is filtered.
    quiet : bool
        Suppress the console report IDL always prints.
    """
    x = finite_only(a, mv=mv)
    y = finite_only(b, mv=mv)

    nx = np.float64(x.size)
    ny = np.float64(y.size)

    x_mean = idl_mean(x, single=True)
    y_mean = idl_mean(y, single=True)
    x_sd = idl_stddev(x, single=True)
    y_sd = idl_stddev(y, single=True)
    x_uv = np.float32(np.float32(x_sd) ** 2)
    y_uv = np.float32(np.float32(y_sd) ** 2)

    t1 = abs(np.float32(x_mean) - np.float32(y_mean))
    t2 = np.sqrt(x_uv / nx + y_uv / ny)
    t = t1 / t2
    v1 = (x_uv / nx + y_uv / ny) ** 2
    v2 = (np.float32(x_sd) ** 4 / (nx ** 2 * (nx - 1))
          + np.float32(y_sd) ** 4 / (ny ** 2 * (ny - 1)))
    v0 = v1 / v2

    if not sl:
        sl = 0.05

    z = t_cvf(sl / 2.0, v0)

    if t < z:
        result = 1
        c = " There is no difference between these data with significance level = "
    else:
        result = 0
        c = " There is a significant difference between these data with significance level = "

    if not quiet:
        print("-----------------Welch test result--------------------------")
        print("t", t, "     t0", z)
        print(c, sl)
        print("-------------------------------------------------------------")
    return result
