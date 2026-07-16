"""Cross-spectrum estimation and its smoothing helpers.

Ports of ``iugonet/tools/statistical_package/coherence_analysis/cross_spectrum``:
``filter_window.pro``, ``filter.pro`` and ``cross_spec.pro``.

Public functions:
- :func:`filter_window` -- build a normalised smoothing window.
- :func:`idl_filter` -- IDL ``filter()``, a NaN-aware weighted moving average.
  Named ``idl_filter`` because ``filter`` is a Python builtin; the same
  convention as :func:`~iugonet.tools.idl_compat.idl_median`.
- :func:`cross_spec` -- the power cross-spectrum of two vectors.

``cross_spec`` reproduces three quirks of the IDL original that callers
(``uspec_coh``, ``coherence_analysis``) depend on; see the docstring.
"""
import numpy as np

from iugonet.tools.idl_compat import (complex_div_real, f32, idl_fft,
                                             idl_hanning, idl_total,
                                             real_times_complex)

__all__ = ["filter_window", "idl_filter", "cross_spec", "plus", "dimension"]


def plus(y):
    """IDL ``plus(Y)``: 1 where Y is positive, 0 elsewhere.

    Dead code in the IDL tree -- ``filter.pro``'s header claims to use it but
    nothing in ``iugonet/tools`` actually calls it. Ported for completeness;
    it has no comparison case for the same reason.
    """
    y = np.asarray(y)
    ans = np.zeros(y.shape, dtype=np.int16)
    ans[y > 0] = 1
    return ans


def dimension(inarray):
    """IDL ``dimension(Inarray)``: the array's dimensionality, 0 for a scalar.

    Dead code, like :func:`plus` -- see its note. This is just
    ``(size(inarray))[0]``, i.e. NumPy's ``ndim``.
    """
    return int(np.asarray(inarray).ndim)


def filter_window(width, window=None, dim=1, boxcar=None, triangle=None):
    """IDL ``filter_window(Width, Window, DIMENSION=, BOXCAR=, TRIANGLE=)``.

    Returns a filter window of the requested shape, normalised so its integral
    is unity.

    IDL builds the window in ``fltarr(width)`` (float32) and normalises with
    ``filt/total(filt)``, so both the window and its normalisation are single
    precision -- reproduced here.

    Note that IDL's version *mutates its arguments*: ``window =
    strlowcase(window)`` and ``width = round(width)`` write back through IDL's
    pass-by-reference, so a caller that passed ``width=10.0`` (float) finds it
    changed to ``10`` (long) afterwards, and any later integer division in
    ``filter`` behaves accordingly. Python cannot write back to the caller, so
    :func:`idl_filter` rounds at the same point instead.

    Parameters
    ----------
    width : int or float
        Rounded to an integer, as IDL does.
    window : str or None
        'boxcar' (default), 'gaussian', 'hanning' or 'triangle'.
    dim : int
        Dimensionality. Default 1.
    boxcar, triangle : int or None
        Legacy way of giving the width.
    """
    if not window:
        window = "triangle" if triangle else "boxcar"
    window = str(window).lower()
    if not width:
        if boxcar:
            width = boxcar
        elif triangle:
            width = triangle
    width = int(np.round(width))
    if not dim:
        dim = 1

    filt = np.zeros(width, dtype=np.float32)
    if window == "boxcar":
        filt[:] = 1.0
    elif window == "gaussian":
        if width == 1:
            filt[:] = 1.0
        else:
            i = np.arange(width, dtype=np.float32)
            filt = np.exp(-(i - (width - 1.0) / 2) ** 2
                          / (2.0 * ((width - 1.0) / 8.0) ** 2)).astype(np.float32)
    elif window == "hanning":
        # IDL: filt[*] = (hanning(width+1))[1:width] -- no /DOUBLE, so float32.
        filt[:] = idl_hanning(width + 1, double=False)[1:width + 1]
    elif window == "triangle":
        halfwidth = (width + 1) // 2
        z = ((np.arange(halfwidth, dtype=np.float32) + 1.0) / halfwidth).astype(np.float32)
        filt[0:halfwidth] = z
        filt[width - halfwidth:width] = z[::-1]

    if dim > 1:
        nfilt = width ** dim
        filtndim = np.ones(nfilt, dtype=np.float32)
        for i in range(nfilt):
            pos = i
            for j in range(dim):
                nlessdim = width ** (dim - 1 - j)
                dimpos = int(np.floor((1.0 * pos) / nlessdim))
                filtndim[i] = filtndim[i] * filt[dimpos]
                pos = pos - dimpos * nlessdim
        filt = filtndim.reshape([width] * dim)

    return (filt / np.float32(idl_total(filt))).astype(np.float32)


def idl_filter(vector, width, window=None, filt=None, boxcar=None,
               triangle=None, start_index=0, step=1, wrap_edges=False,
               edge_truncate=False, nan=False):
    """IDL ``filter(Vector, Width, Window, ...)``: a weighted moving average.

    A literal transcription of the IDL loop::

        outvec[i] = total(filt*temp, nan=nanopt) / total(filt*finite(temp), nan=nanopt)

    rather than a ``np.convolve``/``scipy`` equivalent, because the edge
    handling and the NaN-aware denominator are what the callers rely on:

    - By default (no ``edge_truncate``, no ``wrap_edges``) the ends are padded
      with **NaN**, so the first ``(width-1)//2`` and last ``width//2`` outputs
      are NaN.
    - The denominator ``total(filt*finite(temp))`` renormalises by the weight
      actually covered by finite samples. For complex input, IDL's ``finite()``
      is 1 only when both parts are finite.
    - ``outvec = nan*1.*vector[0:n_out-1]`` inherits the input type, so complex
      input yields complex output.

    Parameters
    ----------
    vector : array
        Real or complex.
    width : int
        Rounded to an integer (see :func:`filter_window`).
    window : str or None
        Passed to :func:`filter_window`.
    filt : array or None
        Pre-built window; skips :func:`filter_window`.
    start_index : int
        First position the window is applied at. Default 0.
    step : int
        Window stepping. Default 1.
    wrap_edges, edge_truncate, nan : bool
        IDL's ``/WRAP_EDGES``, ``/EDGE_TRUNCATE``, ``/NAN``.
    """
    width = int(np.round(width))
    if filt is None:
        filt = filter_window(width, window, boxcar=boxcar, triangle=triangle)
    filt = np.asarray(filt)

    hwidth0 = (width - 1) // 2
    hwidth1 = width // 2

    vector = np.asarray(vector).ravel()
    n = vector.size
    if start_index < 0:
        return 0

    n_out = n - start_index
    if step != 1:
        n_out = (n_out + start_index - start_index // width * width) // step

    iscomplex = np.iscomplexobj(vector)
    dt = np.complex128 if iscomplex else np.float64
    nanval = dt(np.nan)

    # Pad to handle the edges.
    if edge_truncate:
        newvec = np.concatenate([np.full(hwidth0, vector[0], dtype=dt),
                                 vector.astype(dt),
                                 np.full(hwidth1, vector[n - 1], dtype=dt)])
    elif wrap_edges:
        newvec = np.concatenate([vector[n - hwidth0:n].astype(dt) if hwidth0 > 0
                                 else np.empty(0, dtype=dt),
                                 vector.astype(dt),
                                 vector[0:hwidth1].astype(dt) if hwidth1 > 0
                                 else np.empty(0, dtype=dt)])
    else:
        newvec = np.concatenate([np.full(hwidth0, nanval, dtype=dt),
                                 vector.astype(dt),
                                 np.full(hwidth1, nanval, dtype=dt)])

    outvec = np.full(n_out, nanval, dtype=dt)
    for i in range(n_out):
        lo = start_index + i * step
        temp = newvec[lo:lo + width]
        fin = np.isfinite(temp.real) & np.isfinite(temp.imag) if iscomplex \
            else np.isfinite(temp)
        # Type rules matter here. IDL's filt is FLOAT, temp is DOUBLE (or
        # complex) and finite() returns BYTE, so `filt*temp` accumulates in
        # double while `filt*finite(temp)` accumulates in *single* -- the
        # denominator is a float32 sum. Forcing it to float64 costs ~3e-6.
        # real_times_complex, not `*`: on the NaN-padded edges NumPy's complex
        # product would drag the imaginary part to NaN, while IDL leaves it
        # finite (its float32 NaN pad promotes to complex(NaN, 0.0)).
        num = idl_total(real_times_complex(filt, temp), double=True, nan=nan)
        den = idl_total((filt * fin.astype(np.float32)).astype(np.float32), nan=nan)
        outvec[i] = complex_div_real(num, den) if iscomplex else num / den
    return outvec


def cross_spec(y1, y2, deltat=None, width=None, window=None, double=False):
    """IDL ``cross_spec(Y1, Y2, ...)``: the power cross-spectrum of two vectors.

    A positive phase means Y1 leads Y2.

    Returns
    -------
    dict
        ``{'f', 'x', 'y', 'xy', 'absxy', 'cxy', 'lag'}`` -- the tags of the IDL
        ``xspec_data`` structure: frequency, autospectrum 1, autospectrum 2,
        cross spectrum, amplitude, coherence and phase.

    Two IDL behaviours are reproduced deliberately, because the callers see
    them:

    1. **The taper is a Hamming, not a Hanning.** IDL calls
       ``hanning(ny, ALPHA=0.54, /DOUBLE)``; alpha=0.54 makes it a Hamming, and
       IDL's window divides the index by ``N`` (not ``N-1`` like
       ``numpy.hamming``). ``0.54`` is also a *single-precision* literal in
       IDL, so the effective alpha is ``float32(0.54)``. See
       :func:`~iugonet.tools.idl_compat.idl_hanning`.
    2. **The coherence is computed before the positive-frequency fold**, on the
       smoothed full-length arrays. Order matters.

    Note ``f[0]`` is DC (0 Hz), so ``1/f`` -- the period, which ``uspec_coh``
    and ``coherence_analysis`` both compute -- is ``inf`` there.

    Without ``width``, ``cxy`` is identically 1.0 at every frequency
    (``|z1 conj(z2)|^2 / (|z1|^2 |z2|^2)`` cancels exactly), so its maximum is
    degenerate. Smoothing is what makes the coherence meaningful.
    """
    y1 = np.asarray(y1, dtype=np.float64)
    y2 = np.asarray(y2, dtype=np.float64)
    ny = y1.size
    if ny != y2.size:
        print("In cross_spec(), y1 and y2 have diffferent array sizes!")
        return 0
    if not deltat:
        deltat = 1.0

    # IDL: han = hanning(ny, ALPHA=0.54, /DOUBLE) -- a Hamming; 0.54 is float32.
    han = idl_hanning(ny, alpha=f32(0.54), double=True)
    z1 = idl_fft(y1 * han, -1)
    z2 = idl_fft(y2 * han, -1)

    crossspec12 = z1 * np.conj(z2)
    autospec1 = np.real(z1 * np.conj(z1))
    autospec2 = np.real(z2 * np.conj(z2))

    if width:
        crossspec12 = idl_filter(crossspec12, width, window)
        autospec1 = idl_filter(autospec1, width, window)
        autospec2 = idl_filter(autospec2, width, window)

    coherency = np.abs(crossspec12) ** 2 / (np.abs(autospec1) * np.abs(autospec2))

    # Fold to positive frequencies. IDL builds these as ny/2+1 long ...
    # The `2 *` goes through real_times_complex for the same reason as in
    # idl_filter: with a NaN real part (from a smoothed edge), NumPy's
    # `2 * complex(nan, b)` returns (nan, nan) while IDL returns (nan, 2*b).
    crossspec12 = np.concatenate([[crossspec12[0]],
                                  real_times_complex(2, crossspec12[1:ny // 2]),
                                  [crossspec12[ny // 2]]])
    autospec1 = np.concatenate([[autospec1[0]], 2 * autospec1[1:ny // 2],
                                [autospec1[ny // 2]]])
    autospec2 = np.concatenate([[autospec2[0]], 2 * autospec2[1:ny // 2],
                                [autospec2[ny // 2]]])
    coh = coherency[0:ny // 2 + 1]

    # ... and freq matches them at ny/2+1, DC first. See note 2.
    # findgen() is float32 but `ny*deltat` is double, so IDL's division is done
    # in double. NumPy would keep float32 here (float32 array / Python float),
    # which shows up as 36.900001525879 where IDL gives exactly 36.9.
    freq = np.arange(ny // 2 + 1, dtype=np.float32).astype(np.float64) / (ny * deltat)
    freq = freq[0:ny // 2 + 1]

    amplitude = np.abs(crossspec12)
    phase = np.arctan2(np.imag(crossspec12), np.real(crossspec12))

    return {"f": freq, "x": autospec1, "y": autospec2, "xy": crossspec12,
            "absxy": amplitude, "cxy": coh, "lag": phase}
