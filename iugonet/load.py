"""Thin shared loader for CDF files.

Wraps the standard pyspedas ``dailynames`` -> ``download`` -> ``cdf_to_tplot``
pipeline used by the CDF-based ground load functions.
"""
import os

from pyspedas import dailynames, download, cdf_to_tplot
from pyspedas import time_clip as tclip
import pyspedas.utilities.download as _dl_module

from iugonet.config import CONFIG


def _download(verify_cdf=True, **kwargs):
    """Wrapper around the pyspedas ``download``.

    When ``verify_cdf`` is False, the ``check_downloaded_file`` step inside
    ``download`` (which opens the CDF with cdflib to validate it) is replaced
    by a plain existence check. CDFs using a compression that cdflib cannot
    read (e.g. EISCAT) would otherwise fail that validation and be deleted,
    so this keeps them in place.
    """
    if verify_cdf:
        return download(**kwargs)
    _orig = _dl_module.check_downloaded_file
    _dl_module.check_downloaded_file = (
        lambda fn: os.path.isfile(fn) and os.path.getsize(fn) > 0
    )
    try:
        return download(**kwargs)
    finally:
        _dl_module.check_downloaded_file = _orig


def load(
    trange,
    pathformat,
    file_res=24 * 3600.0,
    remote_path=None,
    local_path="",
    prefix="",
    suffix="",
    get_support_data=False,
    get_metadata=False,
    varformat=None,
    varnames=None,
    downloadonly=False,
    notplot=False,
    no_update=False,
    time_clip=False,
    force_download=False,
    verify=False,
    verify_cdf=True,
):
    """Download CDF files and load them into tplot variables.

    Parameters
    ----------
    trange : list of str
        Time range of interest in the format ['YYYY-MM-DD', 'YYYY-MM-DD'].
    pathformat : str
        Remote relative path with strftime fields, e.g.
        'fmag/syo/1sec/%Y/nipr_1sec_fmag_syo_%Y%m%d_v??.cdf'.
    file_res : float
        File cadence in seconds, used to enumerate daily file names.
        Default: 86400.0 (one file per day)
    remote_path : str or None
        Base URL of the remote server. If None, ``CONFIG['remote_data_dir']``
        is used.
        Default: None
    local_path : str
        Sub-directory under ``CONFIG['local_data_dir']`` to store files in.
        Default: '' (the local data directory itself)
    prefix : str
        The tplot variable names will be given this prefix.
        Default: '' (no prefix)
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)
    get_support_data : bool
        Data with an attribute "VAR_TYPE" with a value of "support_data"
        will be loaded into tplot.
        Default: False
    get_metadata : bool
        Load metadata into the tplot variables.
        Default: False
    varformat : str or None
        The file variable formats to load into tplot. Wildcard character
        "*" is accepted.
        Default: None (all variables are loaded)
    varnames : list of str or None
        List of variable names to load.
        Default: None (all variables are loaded)
    downloadonly : bool
        Set this flag to download the data files, but not load them into
        tplot variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    force_download : bool
        If set, re-download data files even if they already exist locally.
        Default: False
    verify : bool
        Verify the SSL certificate of the remote server. Disabled by default
        for the NIPR server.
        Default: False
    verify_cdf : bool
        Validate downloaded files by opening them with cdflib. Disable for
        CDFs using a compression that cdflib cannot read (e.g. EISCAT).
        Default: True

    Returns
    -------
    list of str
        List of tplot variables created. If ``downloadonly`` is set, the list
        of downloaded file paths is returned instead; if ``notplot`` is set, a
        dictionary of data is returned.
    """
    if remote_path is None:
        remote_path = CONFIG["remote_data_dir"]

    remote_names = dailynames(file_format=pathformat, trange=trange, res=file_res)

    local_data_dir = os.path.join(CONFIG["local_data_dir"], local_path)
    files = _download(
        verify_cdf=verify_cdf,
        remote_file=remote_names,
        remote_path=remote_path,
        local_path=local_data_dir,
        no_download=no_update,
        last_version=True,
        force_download=force_download,
        verify=verify,
    )

    out_files = sorted(f for f in (files or []) if os.path.isfile(f))

    if downloadonly:
        return out_files

    if not out_files:
        return {} if notplot else []

    tvars = cdf_to_tplot(
        out_files,
        prefix=prefix,
        suffix=suffix,
        get_support_data=get_support_data,
        get_metadata=get_metadata,
        varformat=varformat,
        varnames=varnames or [],
        notplot=notplot,
    )

    if time_clip and not notplot and tvars:
        for var in tvars:
            tclip(var, trange[0], trange[1], suffix="")

    return tvars
