# pyudas

IUGONET plugin for [pySPEDAS](https://github.com/spedas/pyspedas) — a Python port of
UDAS (IUGONET Data Analysis Software). It provides load functions for IUGONET
ground-based upper-atmosphere observations, imported under the `iugonet` namespace
(the same namespace as the existing pySPEDAS plugins).

## Install

Development of v0.2.0 lives on the `release-0.2` branch:

```
pip install "git+https://github.com/iugonet/pyudas.git@release-0.2"
```

## Usage

```python
import iugonet
from pyspedas import tplot

iugonet.gmag_nipr(trange=['2003-10-29', '2003-10-30'], site='syo')
tplot('nipr_mag_syo_1sec')
```

Load functions (`iugonet.<function>`) cover NIPR fluxgate/induction magnetometers,
imaging riometer, EISCAT radars, RISH radars (EAR/MU/BLR/LTR/WPR/MF) and
radiosonde/AWS/meteor, WDC Kyoto geomagnetic indices and observatories,
Kyushu University ICSWSE/MAGDAS, GPS radio occultation / absolute TEC,
GAIA and Kyushu GCM model output, and IPRT/AMATERAS solar radio spectra.

Data are cached under `~/pyudas_data/` (override with the `IUGONET_DATA_DIR` or
`SPEDAS_DATA_DIR` environment variables).

## License

MIT (see [LICENSE](LICENSE)).
