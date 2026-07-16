"""The Stockwell (S) transform: a local power spectrum.

Port of ``iugonet/tools/statistical_package/s_trans.pro``.

Public functions:
- :func:`hilbert_trans` -- Hilbert transform / analytic signal.
- :func:`gaussian_window` -- the Gaussian window's spectrum.
- :func:`s_trans` -- the S transform itself.

**Cost.** The transform is O(N^2 log N) and its output is an
``(N, N/2+1)`` float32 array, so it does not scale: N=1440 (a day of 1-min
data) gives a 4 MB result from 720 FFTs, but N=86400 (a day of 1-s data) would
need 43200 FFTs and a ~15 TB array. Slice the series before calling.
"""
import numpy as np

from iugonet.tools.idl_compat import idl_fft, idl_hanning, idl_total

__all__ = ["hilbert_trans", "gaussian_window", "s_trans"]

_F32 = np.float32


def hilbert_trans(x, d=None, analytic=False):
    """IDL ``hilbert_trans(x, d, analytic=)``: shift periodic terms by 90 degrees.

    Transcribed from the helper inside ``s_trans.pro``.

    Notes
    -----
    ``y[1]=y[1:n2]*i`` is IDL **array insertion** -- it writes the slice
    starting at index 1, it is not a scalar assignment. Same for ``y[n2]=``.

    IDL's ``n_params(x)`` is a mistake in the original (``N_PARAMS()`` takes no
    argument); the ``d`` scaling it guards is therefore unreachable in
    practice. Kept behind an explicit ``d is not None`` here.

    Parameters
    ----------
    x : array
    d : float or None
        Scales the rotation ``i``.
    analytic : bool
        Return ``complex(x, y)``, the analytic signal, instead of just the
        transform.
    """
    x = np.asarray(x)
    y = idl_fft(x, -1)
    n = y.size
    i = complex(0.0, -1.0)
    if d is not None:
        i = i * d

    # Effect of an odd vs even number of elements.
    n2 = int(np.ceil(n / 2.0)) - 1

    y = y.astype(np.complex128).copy()
    y[0] = 0.0                      # zero the DC value (required)
    y[1:n2 + 1] = y[1:n2 + 1] * i   # rotate 90 deg counter-clockwise
    if (n % 2) == 0:
        y[n2 + 1] = 0.0
    n2 = n - n2
    y[n2:n] = y[n2:n] / i

    y = np.real(idl_fft(y, 1)).astype(np.float32).astype(np.float64)
    if analytic:
        return np.asarray(x, dtype=np.float64) + 1j * y
    return y


def gaussian_window(l, w):
    """IDL ``gaussian_window(l, w)``: the spectrum of a Gaussian window.

    Notes
    -----
    - ``l/2`` is **integer** division in IDL, so an odd length shifts the
      centre by half a sample.
    - ``wl = where(ex lt 25)`` truncates the Gaussian where it underflows
      (``exp(-25)`` is 1.4e-11); entries outside stay zero. This *looks* like
      the empty-``where`` trap -- IDL's ``where`` returns ``-1`` on no match and
      ``g[-1]`` would write the **last** element -- but that path is
      unreachable: ``sigma = l/(2*pi*w)`` is always > 0 (the ``w ne 0`` guard
      covers the only way to make it 0), so ``ex[l/2]`` is always 0 and ``wl``
      always matches at least the centre. The guard below is defensive only.
    """
    if w == 0.0:
        raise ValueError("width is zero!")
    sigma = l / (2 * np.pi * w)
    g = np.zeros(int(l), dtype=np.float32)
    iarr = np.arange(int(l), dtype=np.float32)
    ex = ((iarr - (int(l) // 2)) ** 2 / (2 * sigma ** 2)).astype(np.float32)
    wl = np.where(ex < 25)[0]
    if wl.size:
        g[wl] = np.exp(-ex[wl].astype(np.float64)).astype(np.float32)
    else:
        g[-1] = np.exp(-np.float64(ex[-1])).astype(np.float32)   # IDL's g[-1]
    g = np.roll(g, -(int(l) // 2))
    return g.astype(np.float64) + 0j


def s_trans(ts, factor=1, samplingrate=None, maxfreq=None, minfreq=None,
            freqsamplingrate=None, power=False, abs=False, removeedge=False,
            maskedges=None, verbose=False):
    """IDL ``s_trans(ts, factor, ...)``: the local (Stockwell) spectrum.

    Returns
    -------
    dict or ndarray
        With ``samplingrate`` set: ``{'st', 'time', 'freq'}``, matching IDL's
        structure. Without it: the bare ``st`` array. Note that
        :func:`~iugonet.tools.ustrans_pwrspc.ustrans_pwrspc` needs the
        structure and so **must** pass ``samplingrate``.

    Parameters
    ----------
    ts : array
        The time series. A complex input is used as-is; a real one is turned
        into its analytic signal via :func:`hilbert_trans`.
    factor : float
        Width scaling of the Gaussian window. Default 1.
    samplingrate : float or None
        Sample interval. Set it to get the structure (and the frequency axis).
    maxfreq, minfreq : int or None
        Frequency index range. Defaults 0 .. length/2.
    freqsamplingrate : int or None
        Frequency step. Default 1.
    power : bool
        Return the power spectrum (``|ST|^2``).
    abs : bool
        Return the amplitude spectrum (``|ST|``). If both ``power`` and ``abs``
        are set IDL prints an insult and picks amplitude; kept.
    removeedge : bool
        Detrend with a quadratic fit and taper the ends.

        IDL's ``poly_fit`` solves the normal equations and inverts them
        (``poly_fit.pro:165``), which is in principle less stable than
        ``numpy.polyfit``'s SVD: for ``ind = findgen(N)`` the normal matrix is
        badly conditioned (measured cond=1.8e12 at N=1000, i.e. a worst-case
        relative error of ~4e-4 in float64). In practice the two agree far
        better than that bound -- measured 1e-13 relative on the coefficients
        and 4.7e-13 absolute on the fitted values -- so this path *is* verified
        against IDL (see the ``tools_s_trans`` comparison case).
    maskedges : float or None
        Zero out the S-transform where a ramp's own transform exceeds a
        threshold, to suppress edge artefacts. ``1`` (i.e. ``/maskedges``)
        selects the default 5%; ``0 < maskedges < 1`` is the threshold itself;
        ``1 < maskedges <= 100`` is a percentage.

        Note a ramp's own transform peaks at ~0.498, so a threshold at or above
        that masks nothing at all.

        Caveat: the masking only lines up when the frequency range is the
        default. IDL calls ``s_trans(edgets, /abs)`` recursively **without**
        passing ``minfreq``/``maxfreq``/``freqsamplingrate``, so with a
        restricted range on the outer call the mask's flat indices refer to a
        differently-shaped array -- silently masking the wrong cells, or
        raising a subscript error. That is still true of the IDL original; the
        comparison case therefore uses the default range.
    verbose : bool
        Print progress, as IDL does.
    """
    ts = np.asarray(ts)
    if ts.size == 0:
        raise ValueError("Invalid timeseries (check your spelling).")
    time_series = np.asarray(ts).ravel()

    if abs and power:
        print("You are a moron! Defaulting to Local Amplitude Spectra calculation")
        power = False

    if removeedge:
        if verbose:
            print("Removing edges")
        ind = np.arange(time_series.size, dtype=np.float64)
        coef = np.polyfit(ind, np.asarray(time_series, dtype=np.float64), 2)
        fit = np.polyval(coef, ind)
        ts_power = np.sqrt(idl_total((np.asarray(time_series, dtype=np.float32) ** 2)
                                     .astype(np.float32)) / time_series.size)
        if verbose:
            print("power", ts_power)
        time_series = np.asarray(time_series, dtype=np.float64) - fit
        sh_len = time_series.size // 10
        if sh_len > 1:
            wn = idl_hanning(sh_len, double=False)
            half = sh_len // 2      # IDL: sh_len/2 is integer division
            time_series[0:half] = time_series[0:half] * wn[0:half]
            # IDL: time_series[n-sh_len/2:*] = time_series[n-sh_len/2:*]*wn[sh_len/2:*]
            # For an odd sh_len the two operands differ in length (e.g. sh_len=25
            # -> 12 samples vs wn[12:] = 13), and **IDL silently truncates array
            # arithmetic to the shorter operand** where NumPy raises. Trim to
            # match IDL rather than let it broadcast-error.
            tail = time_series[time_series.size - half:]
            w = wn[half:]
            n = min(tail.size, w.size)
            time_series[time_series.size - half:time_series.size - half + n] = \
                tail[:n] * w[:n]

    if not np.iscomplexobj(time_series):
        if verbose:
            print("Not complex data, finding analytic signal.")
        time_series = hilbert_trans(time_series, analytic=True)

    length = time_series.size
    spe_length = length // 2

    h = idl_fft(time_series, -1)

    if maxfreq is not None and maxfreq < 1:
        maxfreq = int(length * maxfreq)
    if not minfreq:
        minfreq = 0
    else:
        if minfreq > spe_length:
            minfreq = spe_length
            print("minfreq too large, using default value")
    if not maxfreq:
        maxfreq = spe_length
    else:
        if maxfreq > spe_length:
            maxfreq = spe_length
            print("maxfreq too large, using default value")
    if not freqsamplingrate:
        freqsamplingrate = 1

    if maxfreq < minfreq:
        maxfreq, minfreq = minfreq, maxfreq
        print("Switching frequency limits.")
    if maxfreq != minfreq:
        if freqsamplingrate > (maxfreq - minfreq):
            print("FreqSamplingRate too big, using default = 1.")
            freqsamplingrate = 1
    else:
        freqsamplingrate = 1

    spe_nelements = int(np.floor((maxfreq - minfreq) / freqsamplingrate)) + 1

    want_real = bool(abs or power)
    loc = np.zeros((length, spe_nelements),
                   dtype=(np.float32 if want_real else np.complex128))

    h = np.roll(h, -minfreq)
    if minfreq == 0:
        gw = np.zeros(length, dtype=np.float64)
        gw[0] = 1
        first = idl_fft(h * gw, 1)
    else:
        f = _F32(minfreq)
        width = factor * length / f
        gw = gaussian_window(length, width)
        first = idl_fft(h * gw, 1)
    loc[:, 0] = np.abs(first).astype(np.float32) if want_real else first

    for index in range(1, spe_nelements):
        f = _F32(minfreq) + index * freqsamplingrate
        width = factor * length / f
        gw = gaussian_window(length, width)
        h = np.roll(h, -freqsamplingrate)
        b = h * gw
        v = idl_fft(b, 1)
        loc[:, index] = np.abs(v).astype(np.float32) if want_real else v

    if power:
        loc = (loc ** 2).astype(np.float32)

    if maskedges:
        if maskedges == 1:
            maskthreshold = 0.05
        elif 0 < maskedges < 1:
            maskthreshold = maskedges
        elif 1 < maskedges <= 100:
            maskthreshold = float(maskedges) / 100.0
        else:
            maskthreshold = 0.05
        edgets = np.arange(length, dtype=np.float32) / length
        st = s_trans(edgets, abs=True)
        loc[st > maskthreshold] = 0

    if samplingrate:
        frequencies = ((minfreq + np.arange(spe_nelements, dtype=np.float32)
                        * freqsamplingrate) / (samplingrate * length))
        time = np.arange(length, dtype=np.float32) * samplingrate
        return {"st": loc, "time": time, "freq": frequencies}
    return loc
