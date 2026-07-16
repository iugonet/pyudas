"""UDAS-compatible flag removal for time series.

pyspedas also provides ``deflag()``, but it differs from the SPEDAS original in
ways the UDAS routines notice: pyspedas only treats NaN and fills with
``np.interp``, whereas IDL's ``xdeflag`` also flags any value above
``0.98*6.879e28``, and fills each gap with ``yk0 + (t-tk0)*kslope`` computed
from the samples bracketing that gap -- with a slope of **zero** for gaps that
touch either end of the series. ``ustrans_pwrspc`` calls ``tdeflag`` before
transforming, so the placement has to match to reproduce its output.

Public functions:
- :func:`xdeflag` (method, t, y) -- low level; fill the flagged points of a
  time/data array.
- :func:`tdeflag` (names) -- high-level wrapper operating on tplot variables.

Ports of SPEDAS ``general/misc/xdeflag.pro`` and ``tdeflag.pro``.
"""
import numpy as np

__all__ = ["xdeflag", "tdeflag"]

#: IDL's default flag value. Anything above ``0.98*BIG`` is treated as flagged,
#: as are NaN and +/-Inf.
BIG = 6.879e28


def xdeflag(method, t, y, flag=None, maxgap=None, fillval=None):
    """Fill the flagged points of a time/data array.

    Parameters
    ----------
    method : str
        'repeat' -- hold the last good value.
        'linear' -- linear interpolation across the gap; for gaps at either end
        the value is held flat rather than extrapolated.
        'replace' -- write ``fillval``.
        Anything else falls back to 'repeat', as IDL does.
    t : (N,) array
        Time (unix seconds).
    y : (N,) or (N, M) array
        Data. Flagged where ``y > 0.98*flag`` or non-finite.
    flag : float or None
        Default None -> :data:`BIG` (6.879e28).
    maxgap : int or None
        Gaps longer than this many samples are left alone. Default None -> N
        (i.e. every gap is filled).
    fillval : float or None
        For method='replace'. Default 0.

    Returns
    -------
    y_out : ndarray
        A filled copy; the input is not modified.

    Notes
    -----
    A column that is *entirely* flagged is left untouched (IDL prints 'One row
    is all FLAGs: left as is by deflag').
    """
    method = str(method).strip().lower()
    if method == "replace" and fillval is None:
        fillval = 0

    big = flag if (flag is not None) else BIG
    big98 = 0.98 * big
    t = np.asarray(t, dtype=np.float64)
    nrows = t.size
    mxgp = maxgap if maxgap else nrows

    y = np.array(y, dtype=np.float64, copy=True)
    orig_shape = y.shape
    if y.ndim == 1:
        y = y.reshape(nrows, 1)
    else:
        y = y.reshape(nrows, -1)
    nycolayers = y.shape[1]

    for j in range(nycolayers):
        col = y[:, j]
        jiwhere = np.where((col > big98) | (~np.isfinite(col)))[0]
        jiany = jiwhere.size
        if jiany == 0 or jiany >= nrows:
            continue   # nothing flagged, or the whole column is (left as is)

        # Group the flagged indices into contiguous gaps.
        breaks = np.where(np.diff(jiwhere) > 1)[0]
        kbegin = np.concatenate([[jiwhere[0]], jiwhere[breaks + 1]])
        kend = np.concatenate([jiwhere[breaks], [jiwhere[-1]]])
        ngaps = kbegin.size
        ksize = kend - kbegin + 1

        kslope = np.zeros(ngaps, dtype=np.float64)
        tk0 = np.zeros(ngaps, dtype=np.float64)
        yk0 = np.zeros(ngaps, dtype=np.float64)
        for k in range(ngaps):
            at_start = (kbegin[k] == 0)
            at_end = (kend[k] == nrows - 1)
            if at_start and not at_end:
                # Leading gap: hold the first good value, no slope.
                tk0[k] = 0.0
                yk0[k] = col[kend[k] + 1]
                kslope[k] = 0.0
            elif at_end and not at_start:
                # Trailing gap: hold the last good value, no slope.
                tk0[k] = t[kbegin[k] - 1]
                yk0[k] = col[kbegin[k] - 1]
                kslope[k] = 0.0
            elif not at_start and not at_end:
                tk0[k] = t[kbegin[k] - 1]
                yk0[k] = col[kbegin[k] - 1]
                kslope[k] = ((col[kend[k] + 1] - col[kbegin[k] - 1])
                             / (t[kend[k] + 1] - tk0[k]))

        good = np.where(ksize <= mxgp)[0]
        for k in good:
            idx = kbegin[k] + np.arange(ksize[k])
            if method == "linear":
                col[idx] = yk0[k] + (t[idx] - tk0[k]) * kslope[k]
            elif method == "replace":
                col[idx] = fillval
            else:
                # 'repeat' and IDL's fallback for an unknown method.
                col[idx] = yk0[k]
        y[:, j] = col

    return y.reshape(orig_shape)


def tdeflag(names, method="repeat", flag=None, maxgap=None, fillval=None,
            overwrite=True, newname=None, suffix="-deflag"):
    """Fill the flagged points of tplot variables.

    Uses :func:`xdeflag` (not pyspedas ``deflag()``) so the filled values match
    the original output -- see the module docstring.

    Parameters
    ----------
    names : str or list
        tplot variable name(s) or pattern.
    method : str
        'repeat' (default), 'linear' or 'replace'. See :func:`xdeflag`.
    flag, maxgap, fillval : see :func:`xdeflag`.
    overwrite : bool
        If True, overwrite in place.
    newname : str or list
        Output name(s) when overwrite=False.
    suffix : str
        Appended when overwrite=False and no newname is given. Default
        '-deflag', as in SPEDAS.
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
        y_out = xdeflag(method, t, y, flag=flag, maxgap=maxgap, fillval=fillval)
        out = {"x": t, "y": y_out}
        v = getattr(d, "v", None)
        if v is not None:
            out["v"] = v
        target = nm if overwrite else (newname[j] if newname else nm + suffix)
        store_data(target, data=out, attr_dict=meta)
