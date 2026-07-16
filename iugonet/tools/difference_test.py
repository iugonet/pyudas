"""Mean-difference test: normality gate, then Welch or Mann-Whitney.

Ports of ``iugonet/tools/statistical_package/difference_test.pro`` (raw arrays)
and ``udifference_test.pro`` (tplot variables).
"""
from iugonet.tools.mann_whitney_test import mann_whitney_test
from iugonet.tools.normality_test import normality_test
from iugonet.tools.welch_test import welch_test

__all__ = ["difference_test", "udifference_test"]


def difference_test(x, y, sl=None, test_sel=0, quiet=False):
    """IDL ``difference_test, x, y, result, sl=, test_sel=``.

    Tests whether two samples have the same mean. With ``test_sel=0`` the
    choice of test is made for you: a chi-square normality test on each sample,
    then Welch if both are normal, Mann-Whitney otherwise.

    Returns
    -------
    int
        The result code, whose meaning depends on which test ran:
        1/0 = Welch says same/different, 3/2 = Mann-Whitney says same/different.

    Parameters
    ----------
    x, y : array
    sl : float or None
        Significance level. Default 0.05.
    test_sel : int
        0 = pick automatically via the normality test (default),
        1 = force Welch, 2 = force Mann-Whitney.
    quiet : bool
        Suppress the console report.
    """
    if not test_sel:
        test_sel = 0

    if test_sel == 1:
        return welch_test(x, y, sl=sl, quiet=quiet)
    if test_sel == 2:
        return mann_whitney_test(x, y, sl=sl, quiet=quiet)

    x1 = normality_test(x, sl=sl, quiet=quiet)
    y1 = normality_test(y, sl=sl, quiet=quiet)
    if (x1 == 0) and (y1 == 0):
        return welch_test(x, y, sl=sl, quiet=quiet)
    return mann_whitney_test(x, y, sl=sl, quiet=quiet)


def udifference_test(vname1, vname2, sl=None, test_sel=0, quiet=False):
    """IDL ``udifference_test, vname1, vname2, result, sl=, test_sel=``.

    :func:`difference_test` for two tplot variables.

    Parameters
    ----------
    vname1, vname2 : str
        tplot variable names.
    sl, test_sel, quiet : see :func:`difference_test`.
    """
    from pyspedas import get_data, tnames

    if not tnames(vname1) or not tnames(vname2):
        print("Cannot find the tplot vars in argument!")
        return None
    d1 = get_data(vname1)
    d2 = get_data(vname2)
    return difference_test(d1.y, d2.y, sl=sl, test_sel=test_sel, quiet=quiet)
