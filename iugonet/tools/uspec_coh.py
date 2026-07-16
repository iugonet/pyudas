"""Coherence and phase difference between two tplot variables.

Ports of ``iugonet/tools/statistical_package/uspec_coh.pro`` and
``coherence_analysis/coherence_analysis.pro``. Both are thin tplot wrappers
around :func:`~iugonet.tools.cross_spec.cross_spec`; they differ only in
their confidence-interval formula and their plotting.
"""
import numpy as np

from iugonet.tools.cross_spec import cross_spec

__all__ = ["uspec_coh", "coherence_analysis"]

_F32 = np.float32


def _main_period(result, deltat, max_cxy):
    """IDL ``main_period = 1/(deltat*result.f(where(result.cxy eq max_cxy)))``.

    ``where`` can match more than one bin on a tie, in which case IDL -- and
    this -- return an array. A peak at DC gives ``inf``, since ``f[0]`` is 0.
    """
    idx = np.where(result["cxy"] == max_cxy)[0]
    return 1.0 / (deltat * result["f"][idx])


def uspec_coh(vname1, vname2, deltat=None, width=None, window=None, wd=None,
              xsize=None, ysize=None, sl=None, anomaly_flag=None, quiet=False):
    """IDL ``uspec_coh, vname1, vname2, main_period, deltat=, width=, ...``.

    Coherence and phase difference of two tplot variables, plus the period of
    maximum coherence.

    Returns
    -------
    dict
        ``{'main_period', 'max_cxy', 'gama', 'amplitude', 'phase', 'freq',
        'result'}`` -- ``result`` is the full :func:`cross_spec` output.

    Notes
    -----
    - IDL declares ``main_period`` as a positional **after** all the keywords,
      so the call reads ``uspec_coh, v1, v2, main_period, deltat=...``.
    - It **refuses any NaN/Inf** in either input (``print, 'Either of var1 or
      var2 has some invalid data'`` then returns), rather than filtering. Kept.
    - The confidence interval is ``gama = 1*(1-sl^(1/(2*(width-1))))``, which
      differs from :func:`coherence_analysis`'s formula for the same quantity.
    - IDL calls ``window, wd`` in both branches of its ``anomaly_flag`` test,
      so it always needs a display; the plotting is omitted here.

    Parameters
    ----------
    vname1, vname2 : str
        tplot variable names.
    deltat : float or None
        Sampling interval. Passed to :func:`cross_spec` (which defaults it to 1).
    width : float or None
        Smoothing width. Default 10.0.
    window : str or None
        Smoothing window. Default 'hanning'.
    wd, xsize, ysize, anomaly_flag :
        Plotting options in IDL; accepted for signature parity, unused here.
    sl : float or None
        Significance level. Default 0.05.
    quiet : bool
        Suppress the console report.
    """
    from pyspedas import get_data, tnames

    if not tnames(vname1) or not tnames(vname2):
        print("Cannot find the tplot vars in argument!")
        return None
    d1 = get_data(vname1)
    d2 = get_data(vname2)
    y1 = np.asarray(d1.y, dtype=np.float64).ravel()
    y2 = np.asarray(d2.y, dtype=np.float64).ravel()

    if y1.size != y2.size:
        print("var1 and var2 have different array sizes!")
        return None
    if (~np.isfinite(y1)).any() or (~np.isfinite(y2)).any():
        print("Either of var1 or var2 has some invalid data (NaN or Inf)!")
        return None

    if not width:
        width = 10.0
    if not sl:
        sl = 0.05
    if not wd:
        wd = 1
    if not xsize:
        xsize = 1400
    if not ysize:
        ysize = 700
    if not window:
        window = "hanning"

    result = cross_spec(y1, y2, deltat=deltat, width=width, window=window)
    if not deltat:
        deltat = 1.0   # cross_spec defaults it by reference in IDL

    gama = _F32(1 * (1 - _F32(sl) ** (_F32(1.0) / (2.0 * (_F32(width) - 1.0)))))
    max_cxy = float(np.nanmax(result["cxy"]))
    main_period = _main_period(result, deltat, max_cxy)

    if not quiet:
        print("-----------------Coherence analysis result--------------------------")
        print("coherence confidence interval = " + str(gama).strip())
        print("max coherence = " + str(max_cxy).strip())
        print("main_period = " + str(main_period * deltat).strip())
        print("--------------------------------------------------------------------")

    return {"main_period": main_period, "max_cxy": max_cxy, "gama": gama,
            "amplitude": result["absxy"], "phase": result["lag"],
            "freq": result["f"], "result": result}


def coherence_analysis(vname1, vname2, deltat=None, width=None, sl=None,
                       anomaly_flag=None, quiet=False):
    """IDL ``coherence_analysis, vname1, vname2, Y1, Y2, DELTAT=, WIDTH=, ...``.

    The same job as :func:`uspec_coh`, from a different author. Two differences
    that matter and are kept:

    - The confidence interval is ``g2 = 1-sl^(1/((2*(n-width+1)+1)-1))``, i.e.
      it depends on the series length, unlike ``uspec_coh``'s ``gama``.
    - ``window`` is **hard-coded to 'hanning'** (the keyword is declared but
      immediately overwritten), so passing another window has no effect.

    Unlike :func:`uspec_coh` it does no NaN check at all.

    Returns
    -------
    dict
        ``{'main_period', 'max_cxy', 'g2', 'amplitude', 'phase', 'freq',
        'result'}``.
    """
    from pyspedas import get_data

    d1 = get_data(vname1)
    d2 = get_data(vname2)
    y1 = np.asarray(d1.y, dtype=np.float64).ravel()
    y2 = np.asarray(d2.y, dtype=np.float64).ravel()

    if not width:
        width = 10.0
    if not sl:
        sl = 0.05
    window = "hanning"   # IDL overwrites the keyword unconditionally

    result = cross_spec(y1, y2, deltat=deltat, width=width, window=window)
    if not deltat:
        deltat = 1.0

    g2 = _F32(1 - _F32(sl) ** (_F32(1.0)
                               / ((2.0 * (y1.size - _F32(width) + 1) + 1) - 1)))
    if not quiet:
        print("coherence confidence interval", g2)

    # IDL walks cxy with an explicit loop and `ge`, so the *last* maximum wins;
    # np.nanmax alone would not tell us that, but max_cxy's value is identical.
    max_cxy = 0.0
    for v in result["cxy"]:
        if np.isfinite(v) and v >= max_cxy:
            max_cxy = float(v)

    if not quiet:
        print("max coherence", max_cxy)
    main_period = _main_period(result, deltat, max_cxy)
    if not quiet:
        print("main_period  [", deltat, "second]", main_period)

    return {"main_period": main_period, "max_cxy": max_cxy, "g2": g2,
            "amplitude": result["absxy"], "phase": result["lag"],
            "freq": result["f"], "result": result}
