"""Transform WDC geomagnetic field data into XYZ (geographic) coordinates.

Port of ``iugonet/tools/iug_gmag_wdc_xyz.pro``.
"""
import numpy as np

__all__ = ["gmag_wdc_xyz"]

_F32 = np.float32


def _labels_of(vname):
    """IDL's ``get_data, v, LIMITS=str`` -> ``str.LABELS``, via pyspedas metadata.

    ``iug_load_gmag_wdc_wdcmin.pro`` sets the component names with
    ``options, ..., labels=`` which lands in IDL's *limits*; the ported
    ``gmag_wdc`` sets the same strings ('H [nT]', 'D [deg]', ...) as pyspedas
    ``legend_names``.
    """
    from pyspedas import get_data
    meta = get_data(vname, metadata=True) or {}
    opts = (meta.get("plot_options") or {}).get("yaxis_opt") or {}
    labels = opts.get("legend_names")
    if labels is None:
        return []
    return list(labels) if isinstance(labels, (list, tuple, np.ndarray)) else [labels]


def gmag_wdc_xyz(site=None, resolution="min"):
    """IDL ``iug_gmag_wdc_xyz, site=, resolution=``: HDZ -> XYZ for WDC tplot vars.

    Reads the ``wdc_mag_<site>_1<resolution>`` variables already loaded by
    :func:`~iugonet.gmag_wdc` and creates ``<name>_xyz`` holding
    X (north), Y (east) and Z (vertical, downward positive)::

        X = H*cos(D*pi/180)
        Y = H*sin(D*pi/180)
        Z = Z

    Components are identified by their labels ('H [nT]', 'D [deg]', ...), not
    by column order -- as IDL does. Variables already in XYZF coordinates are
    passed through unchanged.

    Parameters
    ----------
    site : str, list or None
        Station code(s), e.g. 'kak' or ['gua', 'kak']. None/'*' -> every
        loaded WDC variable at this resolution.
    resolution : str
        'min' (default) or 'hour'.

    Notes
    -----
    - The output is **float32**: IDL allocates ``y = fltarr(n_elements(d.x), 3)``
      and ``!pi`` is single precision (3.14159274101257324, not ``np.pi``), so
      the whole expression evaluates in single precision.
    - IDL reuses ``h_comp``/``d_comp``/``z_comp`` across the station loop
      **without resetting them**. With ``site=['gua','kak']``, a station that
      lacks D silently inherits the previous station's D. The leak is
      reproduced rather than fixed.
    - IDL's ``if size(z_comp,/N_ELEMENTS) eq 0 then z_comp = h_comp + NaN``
      sits inside a branch already guarded on ``z_comp`` being non-empty, so it
      is unreachable; it is therefore not implemented here either.
    """
    from pyspedas import get_data, options, store_data, tnames

    if not resolution:
        resolution = "min"
    # IDL: colors=[3,5,6] in loadct2 -> cyan / yellow / red, which is also what
    # gmag_wdc's own _COLOR_MAP uses for X/Y/Z. Given as matplotlib letters
    # because pyspedas rejects raw IDL colour indices.
    colors = ["c", "y", "r"]

    if site is None or (isinstance(site, str) and site.strip() == "*"):
        result = list(tnames("wdc_mag_*_1" + resolution))
    else:
        sites = site.split() if isinstance(site, str) else list(site)
        result = []
        for s in sites:
            res = tnames("wdc_mag_" + s + "_1" + resolution)
            result.extend(list(res))

    if not result:
        return []

    created = []
    # Deliberately declared outside the loop: see the docstring note about IDL
    # leaking components between stations.
    h_comp = d_comp = x_comp = y_comp = z_comp = None
    for name in result:
        d = get_data(name)
        if d is None:
            continue
        labels = _labels_of(name)
        yy = np.asarray(d.y, dtype=_F32)
        if yy.ndim == 1:
            yy = yy[:, None]
        for i, lab in enumerate(labels):
            if i >= yy.shape[1]:
                break
            if lab == "D [deg]":
                d_comp = yy[:, i]
            elif lab == "H [nT]":
                h_comp = yy[:, i]
            elif lab == "X [nT]":
                x_comp = yy[:, i]
            elif lab == "Y [nT]":
                y_comp = yy[:, i]
            elif lab == "Z [nT]":
                z_comp = yy[:, i]

        y = np.zeros((np.asarray(d.times).size, 3), dtype=_F32)

        # HDZ -> XYZ. !pi is float32 in IDL, so the conversion is too.
        if h_comp is not None and d_comp is not None and z_comp is not None:
            rad = (d_comp * _F32(np.pi) / _F32(180.0)).astype(_F32)
            y[:, 0] = (h_comp * np.cos(rad.astype(np.float64)).astype(_F32)).astype(_F32)
            y[:, 1] = (h_comp * np.sin(rad.astype(np.float64)).astype(_F32)).astype(_F32)
            y[:, 2] = z_comp
            store_data(name + "_xyz", data={"x": d.times, "y": y})
            options(name + "_xyz", "legend_names", ["X [nT]", "Y [nT]", "Z [nT]"])
            options(name + "_xyz", "Color", colors)
            created.append(name + "_xyz")
            print("Created " + name + "_xyz")

        # Already XYZF: copy straight through.
        if (h_comp is None and d_comp is None and x_comp is not None
                and y_comp is not None and z_comp is not None):
            y[:, 0] = x_comp
            y[:, 1] = y_comp
            y[:, 2] = z_comp
            store_data(name + "_xyz", data={"x": d.times, "y": y})
            options(name + "_xyz", "legend_names", ["X [nT]", "Y [nT]", "Z [nT]"])
            options(name + "_xyz", "Color", colors)
            created.append(name + "_xyz")
            print("Created " + name + "_xyz")

    return created
