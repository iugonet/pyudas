# pyudas

IUGONET plugin for [pySPEDAS](https://github.com/spedas/pyspedas) — a Python port of
UDAS (IUGONET Data Analysis Software). It provides load functions for IUGONET
ground-based upper-atmosphere observations and UDAS' statistical analysis package,
imported under the `iugonet` namespace (the same namespace as the existing pySPEDAS
plugins).

## Install

v0.2.0 is on the default branch (`main`):

```
pip install "git+https://github.com/iugonet/pyudas.git"
```

The `release-0.2` branch points at the same commit for now, so
`...pyudas.git@release-0.2` installs the same thing.

## Usage

```python
import iugonet
from pyspedas import tplot

iugonet.gmag_nipr(trange=['2003-10-29', '2003-10-30'], site='syo')
tplot('nipr_mag_syo_1sec')
```

Load functions (`iugonet.<function>`) cover NIPR fluxgate/induction magnetometers,
all-sky imager/keogram and imaging riometer, EISCAT radars, RISH radars
(EAR/MU/BLR/LTR/WPR/MF) and radiosonde/AWS/meteor, WDC Kyoto geomagnetic indices
and observatories, Kyushu University ICSWSE/MAGDAS, GPS radio occultation /
absolute TEC, GAIA and Kyushu GCM model output, and IPRT/AMATERAS solar radio
spectra.

The **tools** — a port of UDAS' statistical analysis package — work on the loaded
data: S-transform dynamic spectra (`ustrans_pwrspc`, `s_trans`), cross-spectra and
coherence (`cross_spec`, `uspec_coh`, `coherence_analysis`), correlation (`c_cor`,
`ucross_cor`), trend and difference tests (`utrend_test`, `welch_test`,
`mann_whitney_test`, `normality_test`, `udifference_test`), interpolation onto a
common grid (`udata_interpolation`) and change-point detection
(`uchange_point_checker`). Routines whose name starts with `u` take tplot variable
names; the others take plain arrays.

`examples/gallery.ipynb` has a runnable example for every function, and
`examples/quickstart.ipynb` a short introduction. Both open in Colab.

Data are cached under `~/pyudas_data/` (override with the `IUGONET_DATA_DIR` or
`SPEDAS_DATA_DIR` environment variables).

## License

MIT (see [LICENSE](LICENSE)).
