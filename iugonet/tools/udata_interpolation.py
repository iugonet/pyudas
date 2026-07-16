"""Interpolate two tplot variables onto a common, uniform time grid.

Port of ``iugonet/tools/statistical_package/udata_interpolation.pro``.
"""
import numpy as np

__all__ = ["udata_interpolation"]

_F32 = np.float32


def _first_last_finite(data):
    """IDL's four scan loops: first and last index where ``finite(data)``."""
    fin = np.where(np.isfinite(data))[0]
    if fin.size == 0:
        return None, None
    return int(fin[0]), int(fin[-1])


def _interp_series(time_src, data_src, time_grid, lower_op, upper_op):
    """time_grid の各点へ線形内挿する（IDL の 2 つのループと同じ手順）。

    lower_op / upper_op は IDL の比較演算子。data_01 側は ('lt','ge')、
    data_02 側は ('le','gt') と**非対称**（IDL のソースがそうなっている）。
    """
    out = []
    for tg in time_grid:
        exact = np.where(time_src == tg)[0]
        if exact.size and np.isfinite(data_src[exact[0]]):
            out.append(float(data_src[exact[0]]))
            continue

        lo_mask = (time_src < tg) if lower_op == "lt" else (time_src <= tg)
        hi_mask = (time_src >= tg) if upper_op == "ge" else (time_src > tg)
        li = np.where(lo_mask)[0]
        hi = np.where(hi_mask)[0]

        # IDL walks data_01l backwards from the end for the first finite value.
        # An empty where() returns -1 there, which IDL reads as the *last*
        # element; that quirk is preserved by falling back to the whole series.
        low_d = low_t = None
        src_l = li if li.size else np.array([time_src.size - 1])
        for j in range(src_l.size - 1, -1, -1):
            if np.isfinite(data_src[src_l[j]]):
                low_d = float(data_src[src_l[j]])
                low_t = float(time_src[src_l[j]])
                break
        high_d = high_t = None
        src_h = hi if hi.size else np.array([time_src.size - 1])
        for j in range(src_h.size):
            if np.isfinite(data_src[src_h[j]]):
                high_d = float(data_src[src_h[j]])
                high_t = float(time_src[src_h[j]])
                break

        cal_a = np.float64(low_d)
        cal_b = np.float64(high_d) - np.float64(low_d)
        cal_c = ((np.float64(tg) - np.float64(low_t))
                 / (np.float64(high_t) - np.float64(low_t)))
        out.append(float(cal_a + cal_b * cal_c))
    return np.asarray(out, dtype=np.float64)


def udata_interpolation(vname1, vname2, st_time0=None, ed_time0=None,
                        reverse=False, set_interval=None, quiet=False):
    """IDL ``udata_interpolation, vname1, vname2, st_time0=, ed_time0=, ...``.

    Puts two tplot variables on one uniform time grid and stores the results as
    ``<vname1>_interpol`` and ``<vname2>_interpol``.

    The grid spans the overlap of the two series' finite data and steps by the
    smallest time interval found in ``vname1`` (or ``set_interval``).

    Parameters
    ----------
    vname1, vname2 : str
        tplot variable names.
    st_time0, ed_time0 : str or float or None
        Clamp the grid start/end. Only narrows the overlap, never widens it.
    reverse : bool
        **Always fails**, in IDL and here -- see the notes.
    set_interval : float or None
        Grid step in seconds. Default: the minimum interval in ``vname1``.
    quiet : bool
        Suppress the console report.

    Notes
    -----
    - The output is **float32**: IDL fills ``r_data = fltarr(n, 2)`` even though
      the interpolation itself runs in double.
    - ``/reverse`` swaps the two data sets, so the common grid follows
      ``vname2``'s cadence and time range instead of ``vname1``'s. Note the
      *outputs* keep their names: ``vname1_interpol`` still carries ``vname1``'s
      data, only re-gridded on ``vname2``'s terms.
    - The two interpolation loops are **asymmetric**: the ``vname1`` pass
      brackets with ``lt``/``ge`` while the ``vname2`` pass uses ``le``/``gt``.
      Copied rather than harmonised.
    """
    from pyspedas import get_data, store_data, time_double, time_string, tnames

    if not tnames(vname1) or not tnames(vname2):
        print("Cannot find the tplot vars in argument!")
        return None
    d1 = get_data(vname1)
    d2 = get_data(vname2)

    time_01 = np.asarray(d1.times, dtype=np.float64)
    data_01 = np.asarray(d1.y, dtype=np.float64).ravel()
    time_02 = np.asarray(d2.times, dtype=np.float64)
    data_02 = np.asarray(d2.y, dtype=np.float64).ravel()

    if reverse:
        data_01, data_02 = data_02, data_01
        time_01, time_02 = time_02, time_01

    first01, last01 = _first_last_finite(data_01)
    first02, last02 = _first_last_finite(data_02)

    st_time = max(time_01[first01], time_02[first02])
    ed_time = min(time_01[last01], time_02[last02])

    if st_time0:
        if time_double(st_time0) >= st_time:
            st_time = time_double(st_time0)
    if ed_time0:
        if time_double(ed_time0) <= ed_time:
            ed_time = time_double(ed_time0)

    if not quiet:
        print("Start Time : ", time_string(st_time))
        print("End Time : ", time_string(ed_time))

    interval = time_01[1:] - time_01[:-1]
    itp_interval = set_interval if set_interval else float(interval.min())
    if not quiet:
        print(itp_interval, "  [sec] : Time Interval")

    time_03 = []
    i = 0
    while st_time + itp_interval * i <= ed_time:
        time_03.append(st_time + itp_interval * i)
        i += 1
    time_03 = np.asarray(time_03, dtype=np.float64)

    data_03 = _interp_series(time_01, data_01, time_03, "lt", "ge")
    data_04 = _interp_series(time_02, data_02, time_03, "le", "gt")

    r_data = np.zeros((time_03.size, 2), dtype=_F32)
    r_data[:, 0] = data_03.astype(_F32)
    r_data[:, 1] = data_04.astype(_F32)

    store_data(vname1 + "_interpol", data={"x": time_03, "y": r_data[:, 0]})
    store_data(vname2 + "_interpol", data={"x": time_03, "y": r_data[:, 1]})
    return [vname1 + "_interpol", vname2 + "_interpol"]
