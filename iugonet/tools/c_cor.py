"""Cross- and auto-correlation over a lag range, with a significance test.

Ports of ``iugonet/tools/statistical_package/coherence_analysis/c_cor.pro``
(raw arrays) and ``ucross_cor.pro`` (tplot variables).
"""
import numpy as np

from iugonet.tools.idl_compat import a_correlate, c_correlate, f32, t_cvf

__all__ = ["c_cor", "ucross_cor"]


def _lag_defaults(n, low_lag, high_lag):
    """IDL's ``if ~keyword_set(low_lag)`` defaults.

    ``keyword_set`` is false for **0 as well as for unset**, so an explicit
    ``low_lag=0`` is silently replaced by ``-n/2``. The IDL source says as much
    in a Japanese comment ("low_lag=0ではkeyword_setは0を返す"). Reproduced.
    """
    if not low_lag:
        low_lag = -(n // 2)
    if not high_lag:
        high_lag = n // 2
    return int(low_lag), int(high_lag)


def _corr_arrays(x1, y1, low_lag, high_lag):
    """cross_cor / x_cor / y_cor を lag 範囲で作る（c_cor と ucross_cor で共通）。"""
    n = high_lag - low_lag + 1
    cross_cor = np.zeros(n, dtype=np.float64)
    x_cor = np.zeros(n, dtype=np.float64)
    y_cor = np.zeros(n, dtype=np.float64)
    for i in range(low_lag, high_lag + 1):
        cross_cor[i - low_lag] = c_correlate(x1, y1, i)
        x_cor[i - low_lag] = a_correlate(x1, i)
        y_cor[i - low_lag] = a_correlate(y1, i)
    return cross_cor, x_cor, y_cor


def c_cor(x, y, sl=None, mv=None, low_lag=None, high_lag=None, quiet=False):
    """IDL ``C_COR, x, y, cross_cor, cross_spectrum, sl=, low_lag=, high_lag=, x_cor, y_cor``.

    Cross-correlation of two series over a lag range, plus each series'
    autocorrelation.

    Returns
    -------
    dict
        ``{'cross_cor', 'x_cor', 'y_cor', 'low_lag', 'high_lag'}``.

    Notes
    -----
    Pairs are dropped unless **both** x and y are finite at that index, and the
    survivors are cast to double (``append_array,x1,double(x[i])``), so
    :func:`~iugonet.tools.idl_compat.c_correlate` takes its double path.

    ``mv`` is accepted for signature parity but the IDL original never uses it.

    Parameters
    ----------
    x, y : array
    sl : float or None
        Significance level. Default 0.05.
    mv : float or None
        Unused; kept to match the IDL signature.
    low_lag, high_lag : int or None
        Lag range. Default -n/2 .. n/2. **0 counts as unset** -- see
        :func:`_lag_defaults`.
    quiet : bool
        Suppress the console report.
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    good = np.isfinite(x) & np.isfinite(y)
    x1 = x[good]
    y1 = y[good]

    low_lag, high_lag = _lag_defaults(x1.size, low_lag, high_lag)
    cross_cor, x_cor, y_cor = _corr_arrays(x1, y1, low_lag, high_lag)
    return {"cross_cor": cross_cor, "x_cor": x_cor, "y_cor": y_cor,
            "low_lag": low_lag, "high_lag": high_lag}


def ucross_cor(vname1, vname2, sl=None, low_lag=None, high_lag=None,
               quiet=False):
    """IDL ``ucross_cor, vname1, vname2, cross_cor, sl=, low_lag=, high_lag=, x_cor, y_cor``.

    :func:`c_cor` for two tplot variables, with a correlation significance test
    on the maximum and minimum of the cross-correlation.

    Returns
    -------
    dict
        ``{'cross_cor', 'x_cor', 'y_cor', 'max_corr', 'max_zure', 'min_corr',
        'min_zure', 'max_stat', 'min_stat', 'result_max', 'result_min'}``.
        ``*_zure`` are the lags of the extrema ("zure" = offset).

    Notes
    -----
    - IDL declares the positionals *after* the keywords, so the real call order
      is ``ucross_cor, vname1, vname2, cross_cor, x_cor, y_cor``.
    - ``max_zure = where(...) + low_lag`` is an **array**, so ``max_stat`` is an
      array too and IDL's ``if (max_stat ge result_max)`` is only true when
      *every* element is -- i.e. when the extremum is attained at several lags,
      the significance verdict silently becomes an all-or-nothing test.
      Reproduced.
    - ``low_lag=0`` is indistinguishable from unset; see :func:`_lag_defaults`.
    """
    from pyspedas import get_data, tnames

    if not tnames(vname1) or not tnames(vname2):
        print("Cannot find the tplot vars in argument!")
        return None
    d1 = get_data(vname1)
    d2 = get_data(vname2)
    x = np.asarray(d1.y, dtype=np.float64).ravel()
    y = np.asarray(d2.y, dtype=np.float64).ravel()

    # IDL: idx = where(finite(x) and finite(y)) -- pairwise, both must be finite.
    idx = np.where(np.isfinite(x) & np.isfinite(y))[0]
    x1 = x[idx]
    y1 = y[idx]

    low_lag, high_lag = _lag_defaults(x1.size, low_lag, high_lag)
    cross_cor, x_cor, y_cor = _corr_arrays(x1, y1, low_lag, high_lag)

    n1 = x1.size
    max_corr = float(cross_cor.max())
    max_zure = np.where(cross_cor == max_corr)[0] + low_lag
    max_stat = (abs(max_corr)
                * np.sqrt((f32(n1) - np.abs(max_zure) - 2.0)
                          / (1.0 - abs(max_corr) * abs(max_corr))))
    min_corr = float(cross_cor.min())
    min_zure = np.where(cross_cor == min_corr)[0] + low_lag
    min_stat = (abs(min_corr)
                * np.sqrt((f32(n1) - np.abs(min_zure) - 2.0)
                          / (1.0 - abs(min_corr) * abs(min_corr))))

    if not sl:
        sl = 0.05
    result_max = np.asarray([t_cvf(sl / 2.0, n1 - abs(z) - 2) for z in max_zure])
    result_min = np.asarray([t_cvf(sl / 2.0, n1 - abs(z) - 2) for z in min_zure])

    if not quiet:
        print(max_stat, result_max, result_min, n1)
        print("-----------------cross correlation status--------------------------")
        print("|        maximun correlation coefficient       =", max_corr)
        print("|               lag of max correlation         =", max_zure)
        # IDL compares whole arrays here: true only if every element passes.
        if np.all(max_stat >= result_max):
            print("|statistically significant (significance Lv    =", sl, ")")
        else:
            print("|NOT statistically significant (significance Lv    =", sl, ")")
        print("|        minimun correlation coefficient       =", min_corr)
        print("|               lag of min correlation         =", min_zure)
        if np.all(min_stat >= result_min):
            print("|statistically significant (significance Lv    =", sl, ")")
        else:
            print("|NOT statistically significant (significance Lv    =", sl, ")")
        print("-------------------------------------------------------------------")

    return {"cross_cor": cross_cor, "x_cor": x_cor, "y_cor": y_cor,
            "max_corr": max_corr, "max_zure": max_zure,
            "min_corr": min_corr, "min_zure": min_zure,
            "max_stat": max_stat, "min_stat": min_stat,
            "result_max": result_max, "result_min": result_min}
