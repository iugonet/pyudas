"""UDAS-compatible gap filling for time series.

pyspedas also provides ``degap()``, but it places the inserted points
differently: pyspedas steps uniformly by ``dt`` (``np.arange(t[i], t[i+1],
dt)``), whereas this module distributes ``imore = round(tdif/dt) - 1`` points
per gap, evenly spaced by ``tstep = tdif/(imore+1)``. The UDAS load functions
rely on this placement, so it is reproduced here to match the original output.

Public functions:
- :func:`xdegap` (t, y) -- low level; insert NaN rows into the gaps of a time
  and data array.
- :func:`tdegap` (names) -- high-level wrapper operating on tplot variables.
- :func:`idl_median` -- median with integer-index semantics (see below).
"""
import numpy as np


def idl_median(x):
    """Median using integer-index (no-averaging) semantics.

    Returns the value at index ``N//2`` of the ascending-sorted array of N
    elements, rather than averaging the middle two for even N (as
    ``numpy.median`` does). ``dt = median(diff)`` in xdegap/tdegap is computed
    with this convention, so it must match.
    """
    x = np.sort(np.asarray(x, dtype=np.float64))
    n = x.size
    if n == 0:
        return np.nan
    return float(x[n // 2])


def xdegap(t, y, dt=None, margin=0.25, maxgap=None):
    """Insert NaN rows into the gaps of a time/data array.

    Each gap receives ``imore = round(tdif/dt) - 1`` points, evenly spaced by
    ``tstep = tdif/(imore+1)``.

    Parameters
    ----------
    t : (N,) array
        Time (unix seconds); pass an already edge-clipped array.
    y : (N,) or (N, M) array
        Data; inserted rows are filled with NaN.
    dt : float or None
        Default None -> ``idl_median(diff(t))``.
    margin : float
        Default 0.25.
    maxgap : float or None
        Default None -> ``max(t) - min(t)`` (seconds).

    Returns
    -------
    (t_out, y_out)
        The inputs unchanged if there are no gaps.
    """
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    nrows = t.size
    if nrows <= 1:
        return t, y
    if dt is None:
        dt = idl_median(t[1:] - t[:-1])
    if dt <= 0:
        return t, y
    mxgp = (t.max() - t.min()) if maxgap is None else maxgap

    tdif = t[1:] - t[:-1]
    i2add = np.where(((tdif - dt) > margin) & (tdif < mxgp))[0]
    iany = i2add.size
    if iany == 0:
        return t, y

    imore = np.empty(iany, dtype=np.int64)
    tstep = np.empty(iany, dtype=np.float64)
    for k in range(iany):
        # round-half-up: floor(x + 0.5)
        imore[k] = int(np.floor(tdif[i2add[k]] / dt + 0.5)) - 1
        tstep[k] = tdif[i2add[k]] / (imore[k] + 1)
    iaugment = int(imore.sum())
    if iaugment <= 0:
        return t, y
    newnrows = nrows + iaugment

    # start/end indices of each data segment within the new array
    xbegin = np.zeros(iany + 1, dtype=np.int64)
    xend = np.zeros(iany + 1, dtype=np.int64)
    xbegin[0] = 0
    xend[0] = i2add[0]
    for k in range(1, iany):
        xbegin[k] = xend[k - 1] + imore[k - 1] + 1
        xend[k] = i2add[k] - i2add[k - 1] + xbegin[k] - 1
    xbegin[iany] = xend[iany - 1] + imore[iany - 1] + 1
    xend[iany] = nrows - 1 - i2add[iany - 1] + xbegin[iany] - 1

    inewrow = np.arange(newnrows)
    iindices = np.concatenate([
        np.where((inewrow >= xbegin[k]) & (inewrow <= xend[k]))[0]
        for k in range(iany + 1)
    ])

    t_out = np.zeros(newnrows, dtype=np.float64)
    t_out[iindices] = t
    for k in range(iany):
        kidx = np.where((inewrow >= (xend[k] + 1)) & (inewrow <= (xbegin[k + 1] - 1)))[0]
        if kidx.size > 0:
            t_out[kidx] = t[i2add[k]] + tstep[k] * (kidx - xend[k])

    if y.ndim == 1:
        y_out = np.full(newnrows, np.nan, dtype=np.float64)
        y_out[iindices] = y
    else:
        y_out = np.full((newnrows, y.shape[1]), np.nan, dtype=np.float64)
        y_out[iindices, :] = y
    return t_out, y_out


def tdegap(names, dt=None, margin=0.25, maxgap=None, overwrite=True, newname=None):
    """Insert NaN rows into the gaps of tplot variables.

    Uses :func:`xdegap` (not pyspedas ``degap()``) so the inserted points match
    the original output. If the spectrogram v axis (e.g. altitude) varies in
    time (2D, same shape as y), it is degapped as well.

    Parameters
    ----------
    names : str or list
        tplot variable name(s) or pattern.
    dt, margin, maxgap : see :func:`xdegap`.
    overwrite : bool
        If True (default), overwrite in place.
    newname : str or list
        Output name(s) when overwrite=False.
    """
    from pyspedas import get_data, store_data, tnames
    if isinstance(names, str):
        nm_list = list(tnames(names)) or [names]
    else:
        nm_list = list(names)
    if isinstance(newname, str):
        newname = [newname]

    for j, nm in enumerate(nm_list):
        d = get_data(nm)
        meta = get_data(nm, metadata=True)
        if d is None:
            continue
        t = np.asarray(d.times, dtype=np.float64)
        y = np.asarray(d.y, dtype=np.float64)
        if t.size <= 1:
            continue
        t_out, y_out = xdegap(t, y, dt=dt, margin=margin, maxgap=maxgap)
        out = {"x": t_out, "y": y_out}
        # v (spectrogram y axis): degap it if it varies in time
        # (2D, same number of times as y), otherwise keep it as is.
        v = getattr(d, "v", None)
        if v is not None:
            v = np.asarray(v)
            if v.ndim == 2 and v.shape[0] == t.size:
                _, v_out = xdegap(t, v.astype(np.float64), dt=dt, margin=margin, maxgap=maxgap)
                out["v"] = v_out
            else:
                out["v"] = v
        target = nm if overwrite else (newname[j] if newname else nm + "_degap")
        store_data(target, data=out, attr_dict=meta)
