"""Load function for AVON/VLF-B (Asia VLF Observation Network) waveform data.

VLF-B waveform data of the AVON network (Southeast Asia etc.). Stations
tnn/srb/ptk/lbs/hni; parameters ch1 (north-south component) / ch2 (east-west
component). One file is 10 minutes (file_res=600), in CDF format. The variables
created are ``avon_vlfb_{site}_{ch1|ch2}`` (1D waveform time series, [V]).
"""
from pyspedas import get_data, store_data, options, dailynames

from iugonet.load import load

SITE_CODE_ALL = ["tnn", "srb", "ptk", "lbs", "hni"]
# ch1=north-south component, ch2=east-west component
PARAM_ALL = ["ch1", "ch2"]

# site enters the path in uppercase
REMOTE_DATA_DIR = "http://iugonet02.gp.tohoku.ac.jp/avon/cdf/"


def _normalize(value, valid):
    """Normalize a str/list input ('all' accepted) to a list of valid codes (order kept, dups removed)."""
    if isinstance(value, str):
        items = value.lower().split()
    else:
        items = [str(v).lower() for v in value]
    if "all" in items:
        return list(valid)
    out = []
    for it in items:
        if it in valid and it not in out:
            out.append(it)
    return out


def avon_vlfb(
    trange=["2007-12-28/10:20:00", "2007-12-28/10:40:00"],
    site="all",
    parameter="all",
    no_update=False,
    downloadonly=False,
    notplot=False,
    time_clip=False,
    force=False,
    verbose=0,
    ror=True,
    suffix="",
):
    """Load AVON/VLF-B waveform data.

    Parameters
    ----------
    trange : list of str
        Time range of interest [start, end] with the format
        ['YYYY-MM-DD', 'YYYY-MM-DD'] or, to specify hours,
        ['YYYY-MM-DD/hh:mm:ss', 'YYYY-MM-DD/hh:mm:ss']. One file is 10 minutes.
        A range longer than one hour (6 files) requires ``force=True``.
        Default: ['2007-12-28/10:20:00', '2007-12-28/10:40:00']
    site : str or list of str
        Observatory/station code(s). A space-separated string or a list are both
        accepted. 'all' selects every available site. Valid sites:
        tnn srb ptk lbs hni.
        Default: 'all'
    parameter : str or list
        Channel. Valid options: 'ch1' (north-south) / 'ch2' (east-west) /
        'all' (both).
        Default: 'all'
    no_update : bool
        If set, only load data from the local cache.
        Default: False
    downloadonly : bool
        Set this flag to download the data files, but not load them into tplot
        variables.
        Default: False
    notplot : bool
        Return the data in hash tables instead of creating tplot variables.
        Default: False
    time_clip : bool
        Time clip the variables to exactly the range specified in trange.
        Default: False
    force : bool
        If set, allow loading a range longer than one hour (6 files).
        Default: False
    verbose : int
        Verbosity level for diagnostic messages.
        Default: 0
    ror : bool
        If set, print the Rules of the Road and PI/acknowledgement information
        for the dataset.
        Default: True
    suffix : str
        The tplot variable names will be given this suffix.
        Default: '' (no suffix)

    Returns
    -------
    list of str
        List of tplot variables created (``avon_vlfb_{site}_{ch}``). Empty list
        if no data were loaded. If ``downloadonly`` is set, the list of
        downloaded file paths is returned; if ``notplot`` is set, a dictionary
        of data is returned instead.

    Examples
    --------
    >>> import iugonet
    >>> vars = iugonet.avon_vlfb(trange=['2007-12-28/10:20:00', '2007-12-28/10:40:00'])
    >>> from pyspedas import tplot
    >>> tplot(vars)
    """
    sites = _normalize(site, SITE_CODE_ALL)
    params = _normalize(parameter, PARAM_ALL)
    if not sites or not params:
        return {} if notplot else []

    # 10-minute granularity; more than 6 files (>1h) requires force
    fdates = dailynames(file_format="%Y%m%d%H%M%S", trange=trange, res=600)
    if len(fdates) > 6 and not force:
        print("############################################")
        print("!!! timespan too long (>1 hour) !!!")
        print("please set timespan shorter than 1 hour")
        print("if you want to load longer data, use force=True")
        print("############################################")
        return {} if notplot else []

    loaded = {} if notplot else []
    dl_files = []
    any_loaded = False

    for st in sites:
        # remote/local include the site in uppercase in the path
        remote = REMOTE_DATA_DIR + st.upper() + "/"
        local = "TohokuU/radio_obs/" + st.upper() + "/avon/"
        # YYYY/YYMMDD/vlf_waveform_{site}_YYYYMMDDhhmmss_v01.cdf
        pathformat = "%Y/%y%m%d/vlf_waveform_" + st + "_%Y%m%d%H%M%S_v01.cdf"

        for pr in params:
            res = load(
                trange=trange,
                pathformat=pathformat,
                file_res=600.0,
                remote_path=remote,
                local_path=local,
                varformat="vlf_wave_" + pr,
                downloadonly=downloadonly,
                notplot=notplot,
                no_update=no_update,
                time_clip=time_clip,
            )

            if downloadonly:
                dl_files += res
                continue
            if notplot:
                loaded.update(res)
                continue
            if not res:
                continue

            # cdf_to_tplot creates 'vlf_wave_{ch}' -> rename to avon_vlfb_{site}_{ch}
            tmp = "vlf_wave_" + pr
            new = "avon_vlfb_" + st + "_" + pr + suffix
            src = tmp if get_data(tmp) is not None else (res[0] if res else None)
            if src is None or get_data(src) is None:
                continue
            store_data(src, newname=new)
            options(new, "ytitle", "AVON/VLF-B")
            options(new, "ysubtitle", st + "_" + pr + " [V]")
            loaded.append(new)
            any_loaded = True

    if downloadonly:
        return sorted(set(dl_files))

    if ror and any_loaded:
        _print_ror()
    elif not any_loaded and not notplot:
        print("No data is loaded (AVON server iugonet02.gp.tohoku.ac.jp is unreachable).")

    return loaded


def _print_ror():
    """Print the Rules of the Road / acknowledgement."""
    print("**********************************************************************")
    print("Project: Asia VLF Observation Network(AVON) VLF-B")
    print("PI and Host PI(s): Hiroyo Ohya")
    print("Affiliations: Graduate School of Engineering, Chiba University")
    print("Rules of the Road for AVON VLF-B Use:")
    print(" When you use the raw data, you have to participate our consortium. "
          "Please contact us. When the data is used in or contributes to a "
          "presentation or publication, you should make acknowledgement.")
    print("For more information, see http://iugonet02.gp.tohoku.ac.jp/avon/")
    print("**********************************************************************")
