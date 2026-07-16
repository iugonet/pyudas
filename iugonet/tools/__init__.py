"""General-purpose helpers and the UDAS statistical analysis package.

Two groups live here:

- **General-purpose helpers** -- :func:`tdegap`, :func:`tdeflag`, :func:`nn` and
  the IDL primitive emulation in :mod:`iugonet.tools.idl_compat`. These
  come from SPEDAS rather than UDAS, and exist here because pyspedas' equivalents
  differ from IDL in ways the UDAS output depends on (or, for ``nn``, has no
  equivalent); each module's docstring says how.
- **The statistical package** -- a port of ``iugonet/tools/statistical_package``.
  IDL's ``u``-prefixed routines are tplot wrappers around a matching numeric
  core (``utrend_test`` -> ``trend_test``); both names are kept, since dropping
  the ``u`` would make them collide.

The user-facing routines are also re-exported at the top level, so
``iugonet.utrend_test(...)`` mirrors IDL's ``utrend_test, ...``.
"""
from iugonet.tools.c_cor import c_cor, ucross_cor
from iugonet.tools.change_point import uchange_point_checker
from iugonet.tools.cross_spec import (cross_spec, dimension,
                                             filter_window, idl_filter, plus)
from iugonet.tools.difference_test import difference_test, udifference_test
from iugonet.tools.gmag_wdc_xyz import gmag_wdc_xyz
from iugonet.tools.mann_whitney_test import mann_whitney_test
from iugonet.tools.nn import nn
from iugonet.tools.normality_test import normality_test
from iugonet.tools.pulsecode_eiscat import get_pulsecode_eiscat
from iugonet.tools.s_trans import gaussian_window, hilbert_trans, s_trans
from iugonet.tools.tdeflag import tdeflag, xdeflag
from iugonet.tools.tdegap import idl_median, tdegap, xdegap
from iugonet.tools.trend_test import trend_test, utrend_test
from iugonet.tools.udata_interpolation import udata_interpolation
from iugonet.tools.uspec_coh import coherence_analysis, uspec_coh
from iugonet.tools.ustrans_pwrspc import ustrans_pwrspc
from iugonet.tools.welch_test import welch_test

__all__ = [
    # general-purpose helpers
    "tdegap", "xdegap", "idl_median", "tdeflag", "xdeflag", "nn",
    # statistical package: tplot wrappers
    "utrend_test", "udifference_test", "ustrans_pwrspc", "ucross_cor",
    "uspec_coh", "udata_interpolation", "uchange_point_checker",
    "coherence_analysis",
    # statistical package: numeric cores
    "trend_test", "difference_test", "welch_test", "mann_whitney_test",
    "normality_test", "s_trans", "hilbert_trans", "gaussian_window",
    "cross_spec", "filter_window", "idl_filter", "c_cor", "plus", "dimension",
    # standalone tools
    "gmag_wdc_xyz", "get_pulsecode_eiscat",
]
