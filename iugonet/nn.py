"""Nearest-neighbour lookup in a time series (SPEDAS ``nn.pro``)."""
import numpy as np

__all__ = ["nn"]


def _as_data_dict(data_in):
    """Resolve the many input forms of IDL's ``nn`` into a ``{'x': ..., ...}`` dict.

    Accepts a tplot variable name, a tplot index, a time array, or an
    already-extracted structure (dict or the namedtuple ``get_data`` returns).
    Returns None if the input cannot be resolved.
    """
    from pyspedas import get_data
    from pyspedas.tplot_tools import data_exists, tplot_names

    if isinstance(data_in, str):
        if not data_exists(data_in):
            print(f"Error: tplot variable '{data_in}' not found.")
            return None
        data_in = get_data(data_in)
    elif isinstance(data_in, (int, np.integer)) and not isinstance(data_in, bool):
        # IDL: a bare integer is a tplot index, anything else is a time.
        # tplot_names() takes no index -- it lists every name -- so index into it.
        names = tplot_names(quiet=True)
        if not names or not 0 <= int(data_in) < len(names):
            print(f"Error: no tplot variable found for index '{data_in}'.")
            return None
        data_in = get_data(names[int(data_in)])

    if isinstance(data_in, dict):
        if "x" not in data_in:
            print("Error: dictionary input missing 'x' key.")
            return None
        return dict(data_in)

    # The namedtuple from get_data: times/y plus v or v1, v2, ...
    if hasattr(data_in, "times"):
        out = {"x": np.asarray(data_in.times)}
        for field in getattr(data_in, "_fields", ()):
            if field == "times":
                continue
            value = getattr(data_in, field)
            if isinstance(value, np.ndarray):
                out[field] = value
        return out

    if isinstance(data_in, (list, tuple, np.ndarray)):
        return {"x": np.asarray(data_in)}

    print("Error: unsupported data input format.")
    return None


def nn(data, time):
    """IDL ``nn(data, time)``: index of the sample(s) nearest to the given time(s).

    Parameters
    ----------
    data : str or int or array or dict
        A tplot variable name, a tplot index, an array of unix times, or a
        structure carrying an ``x`` (or ``times``) axis, such as the value
        returned by ``get_data``.
    time : str or float or list
        Time(s) to look for, either as 'YYYY-MM-DD/hh:mm:ss' strings or unix
        seconds.

    Returns
    -------
    dict or None
        ``{'indices', 'x', ...}``: the indices found, the times at those
        indices, and the same slice of every other array in the input (``y``,
        ``v``, ``v1``, ...). None if the lookup fails.

    Notes
    -----
    - IDL returns the index and hands back ``x``/``y``/``v`` through keywords;
      this returns them together, which is the same information.
    - A **1-D** ``v`` is returned **unchanged**, as IDL does
      (``if ndimen(dat.v) eq 2 then v = dat.v[inds,*] else v = dat.v``): a 1-D
      ``v`` is a spectrogram's frequency/energy axis and is not indexed by time.
      Only a 2-D (time-varying) ``v`` is sliced.
    - Ties go to the first (lowest) index, matching IDL's ``MIN``.

    Examples
    --------
    >>> import iugonet
    >>> r = iugonet.nn('nipr_mag_syo_1sec', '2003-10-29/06:11:00')
    >>> r['indices'], r['x']
    """
    from pyspedas import time_double

    data = _as_data_dict(data)
    if data is None:
        return None

    source = np.asarray(data["x"], dtype=np.float64)
    if source.size == 0:
        print("Error: no valid time data found.")
        return None

    targets = np.atleast_1d(np.asarray(time_double(time), dtype=np.float64))
    # abs(x - t).argmin() per target, vectorised over targets.
    indices = np.abs(source[:, None] - targets[None, :]).argmin(axis=0)

    result = {"indices": indices, "x": source[indices]}
    for key, value in data.items():
        if key in ("x", "times"):
            continue
        if not isinstance(value, np.ndarray):
            continue
        if key.startswith("v") and value.ndim == 1:
            result[key] = value          # frequency/energy axis: not time-indexed
        else:
            result[key] = value[indices, ...]
    return result
