"""Mann-Whitney U test for a difference of distributions.

Port of ``iugonet/tools/statistical_package/mann_whitney_test.pro``.
"""
import numpy as np

from iugonet.tools.idl_compat import f32, finite_only, gauss_cvf, idl_total

__all__ = ["mann_whitney_test"]


def mann_whitney_test(x, y, sl=None, mv=None, quiet=False):
    """IDL ``mann_whitney_test(x, y, sl=, mv=)``: a distribution-free difference test.

    Returns
    -------
    int
        3 if the distributions are the same, 2 if they differ -- IDL's
        convention (note it differs from :func:`welch_test`'s 1/0).

    Notes
    -----
    The ranking is IDL's own loop, not ``scipy.stats.rankdata``:

        while min(e_tmp) ne 1e10 do begin
           aaa=where(e_tmp eq min(e_tmp))
           rank=counter+(bbb-1)/2.0     ; ties share the mean rank
           e_tmp[aaa]=1e10              ; sentinel marks them consumed
        endwhile

    It ranks ascending and marks consumed values with a ``1e10`` sentinel, so
    real data containing exactly ``1e10`` would terminate the loop early. The
    sentinel is reproduced rather than fixed.

    Precision is deliberately inconsistent in the original and is copied as-is:
    ranks live in ``dblarr`` (double) here, whereas ``trend_test`` ranks into
    ``fltarr`` (single); and ``u_mean = float(nc*nd)/2`` is **single** while
    everything around it is double.
    """
    c = finite_only(x, mv=mv)
    d = finite_only(y, mv=mv)

    nc = np.float64(c.size)
    nd = np.float64(d.size)
    e = np.concatenate([c, d])

    # Ascending rank with a 1e10 sentinel, ties share the mean rank.
    counter = 1
    e_tmp = e.astype(np.float64).copy()
    h = np.zeros(int(nc + nd), dtype=np.float64)
    while e_tmp.min() != 1e10:
        m = e_tmp.min()
        aaa = np.where(e_tmp == m)[0]
        bbb = aaa.size
        rank = counter + (bbb - 1) / 2.0
        h[aaa] = rank
        e_tmp[aaa] = 1e10
        counter = counter + bbb

    k1 = h[0:int(nc)].astype(np.float64)
    k = h[int(nc):int(nc + nd)].astype(np.float64)
    j_total = idl_total(k1, double=True)
    k_total = idl_total(k, double=True)

    if j_total >= k_total:
        u = j_total - nc * (nc + 1) / 2
    else:
        u = k_total - nd * (nd + 1) / 2

    u_mean = f32(nc * nd) / 2          # IDL: float(nc*nd)/2 -- single precision
    u_std = np.sqrt(np.float64(nc * nd * (nc + nd + 1)) / 12.0)
    z = (u - u_mean) / u_std

    if not sl:
        sl = 0.05
    z0 = gauss_cvf(float(f32(sl)) / 2.0)

    if abs(z) < z0:
        result = 3
        c_msg = "There is no difference between these data with significance level = "
    else:
        result = 2
        c_msg = "There is significant difference between these data with significance level = "

    if not quiet:
        print("-----------------Mann Whitney test result--------------------------")
        print("t", abs(z), "      t0", z0)
        print(c_msg, sl)
        print("-------------------------------------------------------------------")
    return result
