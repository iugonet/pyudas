"""Local data directory and remote server configuration.

Local data directory, in order of precedence:
  1. the ``IUGONET_DATA_DIR`` environment variable, if set
  2. ``<SPEDAS_DATA_DIR>/iugonet`` if ``SPEDAS_DATA_DIR`` is set
  3. otherwise ``~/pyudas_data/iugonet``
"""
import os

_spedas = os.environ.get("SPEDAS_DATA_DIR")
if _spedas:
    _base = os.path.join(_spedas, "iugonet")
else:
    _base = os.path.join(os.path.expanduser("~"), "pyudas_data", "iugonet")

CONFIG = {
    "local_data_dir": os.environ.get("IUGONET_DATA_DIR", _base),
    "remote_data_dir": "http://iugonet0.nipr.ac.jp/data/",
}
