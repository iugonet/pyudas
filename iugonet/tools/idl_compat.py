"""Python equivalents of the IDL built-ins used by the UDAS tools.

The UDAS statistical package leans on a handful of IDL library routines. Most
have an exact SciPy/NumPy counterpart and are simply forwarded to it; the rest
do **not** agree with the obvious counterpart, and those are transcribed from
IDL instead. Every difference below was measured against IDL 9.0 (see the
notes on each function). Reproducing the second group is what lets the ported
tools match IDL bit for bit rather than merely to within a tolerance.

Forwarded to SciPy -- the residual disagreement with IDL is far below any
meaningful threshold, so matching IDL's own truncation error is not worth the
code:

- :func:`t_cvf`, :func:`chisqr_cvf`, :func:`gauss_cvf` -- critical values.
  IDL's ``lib/*_cvf.pro`` bisect their CDF to a *relative* 1e-6 instead of
  inverting it, so they carry a truncation error that SciPy does not. Measured
  gap to ``scipy.stats.{t,chi2,norm}.isf``: t 1.8e-6, chi-square 1.7e-5
  (worst at p=0.01, df=27), normal 3.1e-7. These are significance thresholds
  compared against a test statistic; the branch margins in this package are
  ~1e-1, i.e. five orders larger.
- :func:`t_pdf`, :func:`chisqr_pdf`, :func:`gauss_pdf` -- the CDFs the above
  are built from ("pdf" is a misnomer IDL keeps for the whole family). These
  are **bit-identical** to ``scipy.stats.{t,chi2,norm}.cdf``.
- :func:`gaussint` -- normal CDF, bit-identical to ``scipy.special.ndtr``.

Transcribed from IDL -- no counterpart agrees:

- :func:`idl_total` -- sum with IDL's *sequential* accumulation. ``numpy.sum``
  is pairwise and drifts by 2.4e5 from IDL at n=10000 on cancelling float32
  data; this is the foundation the rest of the statistics stand on.
- :func:`f32`, :func:`idl_mean`, :func:`idl_variance`, :func:`idl_stddev` --
  single-precision helpers for the routines that funnel their input through
  IDL's ``float()``. ``idl_variance`` follows ``moment.pro``'s two-pass
  formula, not ``np.var(ddof=1)``.
- :func:`idl_hanning` -- Hanning/Hamming window. Equivalent to SciPy's
  *periodic* ``general_hamming(n, alpha, sym=False)`` in double precision, but
  not in the single-precision path that two of its three callers take.
- :func:`idl_fft` -- IDL's FFT normalisation is the mirror image of NumPy's:
  the *forward* transform carries the 1/N.
- :func:`real_times_complex`, :func:`complex_div_real` -- IDL scales the parts
  of a complex independently, so NaN does not cross over into the other part.
- :func:`idl_median` -- re-exported from :mod:`iugonet.tools.tdegap`.
- :func:`finite_only` -- the ``append_array`` + ``finite()`` filtering loop
  that the statistical routines open with.
"""
import numpy as np
from scipy import special, stats

from iugonet.tools.tdegap import idl_median  # noqa: F401  (re-export)

__all__ = ["t_cvf", "chisqr_cvf", "gauss_cvf", "t_pdf", "chisqr_pdf",
           "gauss_pdf",
           "gaussint", "idl_hanning", "idl_fft", "idl_median",
           "f32", "idl_total", "idl_mean", "idl_variance", "idl_stddev",
           "real_times_complex", "complex_div_real", "finite_only"]


def gaussint(x):
    """IDL ``gaussint(x)``: the normal CDF.

    ``scipy.special.ndtr`` is bit-identical to IDL 9.0 here (measured 2.2e-16
    over x in [-5, 5], i.e. a last-ulp difference at worst).
    """
    return special.ndtr(np.asarray(x, dtype=np.float64))


def t_pdf(v, df):
    """IDL ``t_pdf(v, df)``: the Student's-t CDF (one-tailed).

    ``lib/t_pdf.pro`` builds this out of ``ibeta``; ``scipy.stats.t.cdf`` is
    bit-identical to it, so it is forwarded.
    """
    return float(stats.t.cdf(np.float64(v), np.float64(df)))


def chisqr_pdf(x, df):
    """IDL ``chisqr_pdf(x, df)``: the chi-square CDF.

    ``lib/chisqr_pdf.pro`` is ``igamma(df/2.0, (x>0)/2.0)``;
    ``scipy.stats.chi2.cdf`` is bit-identical to it, and clamps negative ``x``
    to 0 the same way.
    """
    return float(stats.chi2.cdf(np.float64(x), np.float64(df)))


def t_cvf(p, df):
    """IDL ``t_cvf(p, df)``: the Student's-t critical value.

    ``lib/t_cvf.pro`` bisects :func:`t_pdf` to a *relative* 1e-6 rather than
    inverting it, so it lands up to 1.8e-6 from ``scipy.stats.t.isf``
    (measured over p in 0.005..0.05, df in 3..998). SciPy is used here: the
    value is a significance threshold and this package's branch margins are
    ~1e-1, so IDL's truncation error is not worth reproducing.
    """
    if p == 0:
        return 1.0e12
    if p == 1:
        return -1.0e12
    return float(stats.t.isf(p, df))


def chisqr_cvf(p, df):
    """IDL ``chisqr_cvf(p, df)``: the chi-square critical value.

    As with :func:`t_cvf`, IDL bisects rather than inverting. This is the
    widest of the three ``*_cvf`` gaps -- measured 1.7e-5 from
    ``scipy.stats.chi2.isf`` at its worst (p=0.01, df=27) -- but still far
    under the 1e-4 comparison tolerance, and the value never reaches a
    compared output. SciPy is used here.
    """
    if p == 0:
        return 1.0e12
    if p == 1:
        return 0.0
    if df < 0:
        raise ValueError("Degrees of freedom must be positive.")
    return float(stats.chi2.isf(p, df))


def c_correlate(x, y, lag, double=None, covariance=False):
    """IDL ``C_CORRELATE(X, Y, Lag)``: the sample cross-correlation.

    Transcribed from IDL's ``lib/c_correlate.pro``::

        Xd = x - TOTAL(X, Double=useDouble)/nX
        Cross[k] = (Lag[k] ge 0) ? TOTAL(Xd[0:nX-Lag-1] * Yd[Lag:*])
                                 : TOTAL(Yd[0:nX+Lag-1] * Xd[-Lag:*])
        Cross = Cross / SQRT(TOTAL(Xd^2)*TOTAL(Yd^2))

    Not equivalent to ``np.correlate``: the deviations use ``TOTAL(X)/nX``
    rather than a NaN-aware mean, negative lags swap the two series, and the
    normalisation is over the **full** series rather than the overlap.

    ``useDouble`` defaults to "double only if an input is double", so a float32
    input makes the whole computation single precision. ``c_cor`` casts to
    double first, so it gets the double path.

    Parameters
    ----------
    x, y : array
    lag : int or array of int
    double : bool or None
        IDL's ``DOUBLE=``. None -> infer from the input dtype.
    covariance : bool
        IDL's ``/COVARIANCE``: divide by nX instead of the variance.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    nx = x.size
    if nx != y.size:
        raise ValueError("X and Y arrays must have the same number of elements.")
    if nx < 2:
        raise ValueError("X and Y arrays must contain 2 or more elements.")

    if double is None:
        double = (x.dtype == np.float64) or (y.dtype == np.float64)
    dt = np.float64 if double else np.float32

    lags = np.atleast_1d(np.asarray(lag, dtype=np.int64))
    xd = (x.astype(dt) - dt(idl_total(x, double=double) / nx)).astype(dt)
    yd = (y.astype(dt) - dt(idl_total(y, double=double) / nx)).astype(dt)

    cross = np.zeros(lags.size, dtype=dt)
    for k, lg in enumerate(lags):
        if lg >= 0:
            cross[k] = idl_total((xd[0:nx - lg] * yd[lg:]).astype(dt), double=double)
        else:
            cross[k] = idl_total((yd[0:nx + lg] * xd[-lg:]).astype(dt), double=double)

    if covariance:
        denom = dt(nx)
    else:
        denom = dt(np.sqrt(idl_total((xd ** 2).astype(dt), double=double)
                           * idl_total((yd ** 2).astype(dt), double=double)))
    cross = (cross / denom).astype(dt)
    return cross if lags.size > 1 else dt(cross[0])


def a_correlate(x, lag, double=None, covariance=False):
    """IDL ``A_CORRELATE(X, Lag)``: the sample autocorrelation.

    Transcribed from IDL's ``lib/a_correlate.pro``::

        data = X - (TOTAL(X, Double=useDouble)/nX)
        M = ABS(Lag)
        Auto[k] = TOTAL(data[0:nX-1-M[k]] * data[M[k]:*])
        Auto = Auto / TOTAL(data^2)

    The lag is used as ``abs(lag)`` and the denominator is the **whole**
    series' sum of squares, so -- as IDL's own comment warns --
    ``A_CORRELATE(X, 1)`` is deliberately not ``CORRELATE(X[0:N-2], X[1:*])``.

    Parameters
    ----------
    x : array
    lag : int or array of int
    double : bool or None
        IDL's ``DOUBLE=``. None -> infer from the input dtype.
    covariance : bool
        IDL's ``/COVARIANCE``: divide by nX instead of the variance.
    """
    x = np.asarray(x)
    nx = x.size
    if nx < 2:
        raise ValueError("X array must contain 2 or more elements.")
    if double is None:
        double = (x.dtype == np.float64)
    dt = np.float64 if double else np.float32

    lags = np.atleast_1d(np.asarray(lag, dtype=np.int64))
    data = (x.astype(dt) - dt(idl_total(x, double=double) / nx)).astype(dt)

    auto = np.zeros(lags.size, dtype=dt)
    m = np.abs(lags)
    for k in range(lags.size):
        auto[k] = idl_total((data[0:nx - m[k]] * data[m[k]:]).astype(dt),
                            double=double)
    denom = dt(nx) if covariance else dt(idl_total((data ** 2).astype(dt),
                                                   double=double))
    auto = (auto / denom).astype(dt)
    return auto if lags.size > 1 else dt(auto[0])


def gauss_pdf(v):
    """IDL ``gauss_pdf(v)``: the normal CDF. ``lib/gauss_pdf.pro`` is just
    ``return, gaussint(v)`` -- see :func:`gaussint` (the "pdf" name is a
    misnomer IDL keeps for the whole ``*_pdf`` family; they are all CDFs)."""
    return gaussint(v)


def gauss_cvf(p):
    """IDL ``gauss_cvf(p)``: the normal critical value.

    Like :func:`t_cvf`, IDL bisects rather than inverting, so it lands up to
    3.1e-7 from ``scipy.stats.norm.isf`` (measured over p in 0.005..0.5).
    SciPy is used here.
    """
    if p < 0.0 or p > 1.0:
        raise ValueError("p must be in the interval [0.0, 1.0]")
    if p == 0:
        return 1.0e12
    if p == 1:
        return -1.0e12
    return float(stats.norm.isf(p))


def idl_hanning(n, alpha=None, double=True):
    """IDL ``hanning(n, ALPHA=alpha, /DOUBLE)``: a 1-D Hanning/Hamming window.

    Transcribed from IDL's ``lib/hanning.pro``::

        a = 2 * pi / N1
        index = DINDGEN(n1)
        return, (alpha-one) * cos(index*a) + alpha

    Dividing the index by ``N`` rather than ``M-1`` makes this the *periodic*
    window, so ``numpy.hamming`` (which divides by ``M-1``) is not a
    substitute -- but ``scipy.signal.windows.general_hamming(n, alpha,
    sym=False)`` **is** the same window, algebraically and to within 2.2e-16
    in double precision (measured over n=4..1000). It is not used here for
    two reasons, both measured against IDL 9.0:

    1. ``alpha`` keeps the precision it was written with. ``cross_spec.pro``
       passes the literal ``0.54``, which IDL types as *single* precision, so
       the effective alpha is ``float32(0.54) = 0.5400000214576721`` and the
       window differs from the float64 formula by ~4e-8. Callers that mirror
       an IDL float literal must therefore pass ``f32(0.54)``.
    2. **IDL evaluates transcendentals on float32 input by promoting to
       float64 and rounding the result back**, whereas NumPy's float32 ``cos``
       uses a single-precision libm. Measured on ``hanning(12)``, computing
       ``cos`` in float32 matches IDL on only 11 of 12 samples; going through
       float64 matches all 12. Hence the explicit float64 ``cos`` below.

    Trap 2 is what rules SciPy out: two of the three callers take the
    single-precision path (``filter_window``'s 'hanning' branch and
    ``s_trans``'s edge taper both call ``hanning()`` without ``/DOUBLE``),
    where ``general_hamming`` is 2.9e-7 away. Keeping the float32 branch would
    be necessary anyway, so forwarding the float64 branch alone buys nothing.

    The expression order below matches IDL's; algebraically equivalent
    rearrangements round differently.
    """
    if alpha is None:
        alpha = np.float64(0.5) if double else np.float32(0.5)
    dt = np.float64 if double else np.float32
    alpha = dt(alpha)
    one = dt(1.0)
    pi = dt(np.pi)
    n1 = dt(n)
    a = 2 * pi / n1
    index = np.arange(n, dtype=dt)
    cosv = np.cos((index * a).astype(np.float64)).astype(dt)
    return ((alpha - one) * cosv + alpha).astype(dt)


def idl_fft(x, direction=-1):
    """IDL ``fft(x, direction)``: the FFT with IDL's normalisation.

    IDL puts the 1/N on the **forward** transform; NumPy puts it on the
    inverse. So ``fft(x, -1)`` (forward, IDL's default) is
    ``np.fft.fft(x)/N`` -- verified exactly -- and ``fft(x, +1)`` (inverse) is
    ``np.fft.ifft(x)*N``. Passing an array straight to ``np.fft.fft`` is off
    by a factor of N.

    Parameters
    ----------
    x : array
    direction : int
        -1 = forward (IDL's default), +1 = inverse.
    """
    x = np.asarray(x)
    n = x.shape[-1] if x.ndim else 1
    if direction < 0:
        return np.fft.fft(x) / n
    return np.fft.ifft(x) * n


def real_times_complex(r, z):
    """IDL's ``&lt;real&gt; * &lt;complex&gt;``: scale both parts, without NaN cross-talk.

    IDL multiplies a real by a complex by scaling the real and imaginary parts
    independently: ``f * (a,b) -> (f*a, f*b)``. NumPy instead promotes the real
    to ``complex(f, 0)`` and runs the full complex product
    ``(f*a - 0*b, f*b + 0*a)``. The results agree on finite data, but **not**
    around NaN: the ``0*a`` term turns into ``0*NaN = NaN`` and poisons the
    imaginary part.

        np.float32(0.1) * np.complex128(np.nan)   -> (nan+nanj)
        IDL   0.1       * complex(NaN, 0.0)       -> (NaN, 0.0)

    NumPy does this for int and float scalars alike (``2 * complex(nan, 5)``
    is also ``(nan+nanj)``), so every real-by-complex product on data that can
    carry a NaN has to come through here. See :func:`complex_div_real` for the
    division counterpart.

    This matters wherever NaN meets a complex array -- e.g. ``filter()``'s
    NaN-padded edges, where IDL's imaginary parts stay finite and NumPy's would
    all go NaN.
    """
    z = np.asarray(z)
    r = np.asarray(r)
    if not np.iscomplexobj(z):
        return r * z
    return (r * z.real) + 1j * (r * z.imag)


def complex_div_real(z, r):
    """IDL's ``&lt;complex&gt; / &lt;real&gt;``: divide both parts. See :func:`real_times_complex`.

    Same NaN trap in the other direction::

        np.complex128(complex(np.nan, 5.0)) / 2.0  -> (nan+nanj)
        IDL          complex(NaN, 5.0)     / 2.0   -> (NaN, 2.5)
    """
    z = np.asarray(z)
    r = np.asarray(r)
    if not np.iscomplexobj(z):
        return z / r
    return (z.real / r) + 1j * (z.imag / r)


def f32(x):
    """IDL ``float(x)``: cast to single precision, keeping a float64 container.

    IDL's ``float()`` truncates to single precision but subsequent arithmetic
    happily mixes types. Returning float64-typed data that holds a
    single-precision *value* mirrors that and keeps downstream NumPy code from
    silently re-widening the intent away.
    """
    return np.asarray(x, dtype=np.float32).astype(np.float64)


def idl_total(x, double=False, nan=False):
    """IDL ``total(x)``: sum with IDL's **sequential** accumulation.

    This is the single most load-bearing function here: ``mean``, ``stddev``,
    ``variance`` and every ``Sxx``/``Syy``/``Sxy`` in the statistical package
    route through IDL's ``TOTAL``.

    ``numpy.sum`` is **not** a substitute. NumPy sums float32 pairwise, IDL
    sums left to right, and on data with cancellation the two diverge fast --
    measured against IDL 9.0 on ``1e6 + sin(2*pi*i/97) + 0.001*i``:

        n=100    np.sum off by 8.0
        n=1000   np.sum off by 5.1e2
        n=10000  np.sum off by 2.4e5

    ``np.cumsum(x, dtype=np.float32)[-1]`` *is* left-to-right and matches IDL
    bit for bit at every size tested (10 .. 200000), at C speed.

    **Threading caveat.** IDL multithreads TOTAL above ``!CPU.TPOOL_MIN_ELTS``
    (100000 by default), which re-partitions the sum and matches neither
    ordering. The comparison harness therefore emits ``cpu, tpool_nthreads=1``
    so IDL stays sequential and reproducible; with that set, this function is
    bit-exact at n=100000 and n=200000 too. A default (multithreaded) IDL
    session summing >100k float32 elements will differ slightly from both this
    and from single-threaded IDL -- that is IDL's own accumulation-order
    artefact, not a port error.

    Parameters
    ----------
    x : array
    double : bool
        IDL's ``/DOUBLE``: accumulate in float64 regardless of input type.
    nan : bool
        IDL's ``NAN=``: treat non-finite entries as zero rather than letting
        them poison the sum.

    Returns
    -------
    float or complex
        complex when the input is complex (IDL keeps the type through TOTAL).
    """
    a = np.asarray(x)
    if a.size == 0:
        return 0.0
    if np.iscomplexobj(a):
        dt = np.complex128 if (double or a.dtype == np.complex128) else np.complex64
    elif double or a.dtype == np.float64:
        dt = np.float64
    else:
        dt = np.float32
    a = a.astype(dt)
    if nan:
        a = np.where(np.isfinite(a), a, dt(0))
    v = np.cumsum(a, dtype=dt)[-1]
    return complex(v) if np.iscomplexobj(a) else float(v)


def idl_mean(x, single=False):
    """IDL ``mean(x)``.

    IDL's ``lib/mean.pro`` is ``TOTAL(X)/N_ELEMENTS(X)`` with no ``/DOUBLE``,
    so a float32 array is summed *and divided* in single precision. Built on
    :func:`idl_total`, hence sequential -- ``np.mean`` (pairwise) drifts away
    from IDL as n grows.
    """
    a = np.asarray(x)
    n = a.size
    if single:
        a = a.astype(np.float32)
        return float(np.float32(np.float32(idl_total(a)) / np.float32(n)))
    return float(idl_total(a.astype(np.float64), double=True) / n)


def idl_variance(x, single=False):
    """IDL ``variance(x)``: via ``lib/moment.pro``'s two-pass formula.

    ``moment.pro`` does **not** use the naive ``sum(r^2)/(n-1)`` that
    ``np.var(ddof=1)`` computes. It uses the corrected two-pass form from
    Numerical Recipes::

        Var = (TOTAL(Resid^2) - (TOTAL(Resid)^2)/nX) / (nX-1.0)

    with ``Resid = X - Mean``, and -- because ``Double = (type EQ 5 || type EQ
    9)`` -- in **single** precision for a float32 input.

    What makes this non-substitutable is the **single-precision sequential
    accumulation** (see :func:`idl_total`), not the correction term. In the
    float64 path that term is ~1e-30..1e-15 and changes zero bits, and
    ``np.var(ddof=1)`` agrees to 4e-16; only ``single=True`` is ever used by
    this package (``welch_test``, ``normality_test``), and there the float32
    ``TOTAL`` is what has to be reproduced.
    """
    a = np.asarray(x)
    n = a.size
    if single:
        a = a.astype(np.float32)
        mean = np.float32(idl_mean(a, single=True))
        r = (a - mean).astype(np.float32)
        t2 = np.float32(idl_total((r * r).astype(np.float32)))
        t1 = np.float32(idl_total(r))
        return float(np.float32((t2 - np.float32(t1 * t1 / n)) / np.float32(n - 1.0)))
    a = a.astype(np.float64)
    mean = idl_mean(a)
    r = a - mean
    t2 = idl_total(r * r, double=True)
    t1 = idl_total(r, double=True)
    return float((t2 - t1 * t1 / n) / (n - 1.0))


def idl_stddev(x, single=False):
    """IDL ``stddev(x)``: ``sqrt(variance(x))``. See :func:`idl_variance`."""
    v = idl_variance(x, single=single)
    if single:
        return float(np.sqrt(np.float32(v), dtype=np.float32))
    return float(np.sqrt(v))


def finite_only(x, mv=None, single=True):
    """The ``append_array`` + ``finite()`` filter the statistical routines open with.

    The IDL pattern is::

        for i=0L,na-1 do begin
           if(float(a[i]) eq mv) or (not finite(a[i])) then continue
           append_array,x,float(a[i])
        endfor

    i.e. drop non-finite entries (and, when ``mv`` is given, entries equal to
    the missing value) while casting to single precision. Order is preserved.

    Parameters
    ----------
    x : array
    mv : float or None
        Missing value. None (default) -> only non-finite values are dropped.
    single : bool
        Cast through ``float()`` as IDL does. Default True.
    """
    a = np.asarray(x, dtype=np.float64).ravel()
    if single:
        a = f32(a)
    keep = np.isfinite(a)
    if mv is not None:
        keep &= (a != mv)
    return a[keep]
