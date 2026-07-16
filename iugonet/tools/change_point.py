"""Locate the change point of a time series (two-segment regression).

Port of ``iugonet/tools/statistical_package/uchange_point_checker.pro``.
"""
import numpy as np

from iugonet.tools.idl_compat import idl_mean, idl_total

__all__ = ["alpha0", "alpha1", "alpha2", "sse_full", "mu_",
           "uchange_point_checker"]

_F32 = np.float32


def alpha0(x):
    """IDL ``alpha0(X)``: the OLS slope of the whole series.

    Notes
    -----
    IDL's ``sum = 0`` starts as an INT but promotes to the *input's* type on
    the first addition, so a double series accumulates in double. This port
    always widens its input to float64, i.e. it takes IDL's double path.
    """
    x = np.asarray(x, dtype=np.float64)
    nx = x.size
    xmean = idl_mean(x)
    total = 0.0
    for i in range(nx):
        total += (i + 1) * (x[i] - xmean)
    return total * 12 / (float(nx) * (nx + 1) * (nx - 1))


def alpha1(c, x):
    """IDL ``alpha1(c, X)``: the OLS slope of ``X[0:c-1]``, centred on c.

    Notes
    -----
    The denominator keeps IDL's explicit ``float(c)*(float(c)+1)*(float(c)-1)``
    -- single precision regardless of the input type, so it rounds for
    ``c`` beyond about 2^24 worth of product. That cast is in the IDL source,
    not an artefact of the input, so it is preserved.
    """
    x = np.asarray(x, dtype=np.float64)
    c = int(c)
    c_mean = (c + 1) / 2.0
    x1mean = idl_mean(x[0:c])
    total = 0.0
    for i in range(c):
        total += (i + 1 - c_mean) * (x[i] - x1mean)
    denom = _F32(_F32(c) * (_F32(c) + 1) * (_F32(c) - 1))
    return total * 12 / denom


def alpha2(c, x):
    """IDL ``alpha2(c, X)``: the OLS slope of ``X[c:]``.

    **Dead code in the original**: ``SSEfull`` calls ``alpha1`` twice (once on
    the tail) and nothing else calls ``alpha2``. Ported for completeness.

    Note it is not simply :func:`alpha1` on the tail: ``alpha1`` centres the
    index on the segment mean (``i+1-c_mean``) while ``alpha2`` does not
    (``i+1``), so the two implement different formulas. IDL's ``alpha2`` has
    the centred version sitting commented out beside the live line.
    """
    x = np.asarray(x, dtype=np.float64)
    nx = x.size
    c = int(c)
    x2mean = idl_mean(x[c:nx])
    total = 0.0
    for i in range(c, nx):
        total += (i + 1) * (x[i] - x2mean)
    return total * 12 / (float(nx - c) * (nx - c + 1) * (nx - c - 1))


def sse_full(x, c):
    """IDL ``SSEfull(X, c)``: residual sum of squares of the two-segment model.

    Note it brackets both segments with :func:`alpha1` -- the second call is
    ``alpha1(nX-c, X[c:])``, not :func:`alpha2`.

    At ``c = nX-1`` the tail segment has one sample, so ``alpha1``'s
    denominator ``float(1)*2*0`` is zero and the result is Inf/NaN. That is
    IDL's behaviour too.
    """
    x = np.asarray(x, dtype=np.float64)
    nx = x.size
    c = int(c)
    a1 = alpha1(c, x)
    a2 = alpha1(nx - c, x[c:nx])
    mu1 = idl_mean(x[0:c]) - a1 * (c + 1) / 2.0
    mu2 = idl_mean(x[c:nx]) - a2 * (c + nx + 1) / 2.0

    vals = np.empty(nx, dtype=np.float64)
    for i in range(c):
        vals[i] = (x[i] - mu1 - a1 * (i + 1)) ** 2
    for i in range(c, nx):
        vals[i] = (x[i] - mu2 - a2 * (i + 1)) ** 2
    return idl_total(vals, double=True)


def mu_(x, a0):
    """IDL ``mu(X, a0)``: the intercept for a given slope.

    Named ``mu_`` because ``iugonet.mu`` is already the MU radar loader.
    """
    x = np.asarray(x, dtype=np.float64)
    nx = x.size
    total = 0.0
    for i in range(nx):
        total = total + (x[i] - a0 * (i + 1))
    return total / nx


def uchange_point_checker(vname1, quiet=False):
    """IDL ``uchange_point_checker, vname1``: find a series' change point.

    Computes the F statistic of a two-segment (broken-stick) regression against
    a single-line reduced model at every candidate breakpoint, and reports where
    it peaks.

    Returns
    -------
    dict
        ``{'Fc1', 'Fc3', 'change_point'}``. ``Fc1`` is the F statistic over
        candidate breakpoints 2..nX-1. ``Fc3`` is IDL's second, **identical**
        statistic (see Notes) and is the same array. ``change_point`` is the
        breakpoint itself, i.e. ``argmax(Fc1) + 2``.

    Notes
    -----
    IDL assigns ``X1 = X2 = X3 = d1.y`` and then computes ``Fc1`` and ``Fc3``
    from the *same* reduced model on the *same* data, so the two are
    necessarily identical -- verified on IDL 9.0, where the routine prints its
    two argmaxes as ``198`` and ``198``. The three-way split is vestigial: it
    only makes sense in the sibling demo ``change_point_checker.pro``, which
    builds three genuinely different synthetic series. ``Fc3`` is returned as
    the same array rather than recomputed, which saves a second O(N^2) sweep.

    IDL also computes a ``c=300`` two-segment model and an OLS fit (``b0``,
    ``b1``) at lines 127-138, but every consumer of those is a commented-out
    ``oplot``. They are dead, and are not ported -- so, unlike IDL, this
    routine has no implicit ``nX > 300`` requirement.

    The printed indices are IDL's ``where(Fc1 eq max(Fc1))``, which index into
    ``Fc1`` and are therefore **2 less than the breakpoint** they refer to
    (``Fc1[0]`` is the statistic at c=2). ``change_point`` in the returned dict
    corrects for that.

    The last element of ``Fc1`` is NaN: at ``c = nX-1`` the tail segment holds
    one sample and ``sse_full`` divides by zero (see :func:`sse_full`). That is
    IDL's behaviour too.
    """
    from pyspedas import get_data, tnames

    if not tnames(vname1):
        print("Cannot find the tplot vars in argument!")
        return None
    d1 = get_data(vname1)
    x1 = np.asarray(d1.y, dtype=np.float64).ravel()
    nx = x1.size

    a0 = alpha0(x1)
    mu0 = mu_(x1, a0)
    ssered0 = np.asarray([(x1[i] - mu0 - a0 * (i + 1)) ** 2 for i in range(nx)],
                         dtype=np.float64)
    ssered = idl_total(ssered0, double=True)

    fc1 = np.empty(nx - 2, dtype=np.float64)
    for i in range(2, nx):
        sse = sse_full(x1, i)
        fc1[i - 2] = ((ssered - sse) * (nx - 4)) / (2.0 * sse)
    fc3 = fc1

    imax = int(np.nanargmax(fc1))
    if not quiet:
        # IDL: print,where(Fc1 eq max(Fc1)),where(Fc3 eq max(Fc3))
        print(imax)
        print(imax)
    return {"Fc1": fc1, "Fc3": fc3, "change_point": imax + 2}
