"""pyudas: a Python port of UDAS (IUGONET Data Analysis Software) for pyspedas.

Just as UDAS runs on top of SPEDAS, pyudas runs on top of pyspedas. The
ground-based instrument load functions live under ``iugonet.ground``.
"""
from iugonet.ground.gmag_nipr import gmag_nipr
from iugonet.ground.gmag_nipr_induction import gmag_nipr_induction
from iugonet.ground.eiscat import eiscat
from iugonet.ground.eiscat_vief import eiscat_vief
from iugonet.ground.asi_nipr import asi_nipr
from iugonet.ground.irio_nipr import irio_nipr
from iugonet.ground.lfrto import lfrto
from iugonet.ground.hf_tohokuu import hf_tohokuu
from iugonet.ground.aws_rish import aws_rish
from iugonet.ground.ionosonde_rish import ionosonde_rish
from iugonet.ground.gmag_icswse_iaga import gmag_icswse_iaga
from iugonet.ground.meteor_rish import meteor_rish
from iugonet.ground.radiosonde_rish import radiosonde_rish
from iugonet.ground.mf_rish import mf_rish
from iugonet.ground.gps_ro_rish import gps_ro_rish
from iugonet.ground.gps_atec import gps_atec
from iugonet.ground.gaia_gcm_nc import gaia_gcm_nc
from iugonet.ground.gaia_cpl_nc import gaia_cpl_nc
from iugonet.ground.blr_rish import blr_rish
from iugonet.ground.ltr_rish import ltr_rish
from iugonet.ground.wpr_rish import wpr_rish
from iugonet.ground.gps_isee import gps_isee
from iugonet.ground.gmag_wdc import gmag_wdc, gmag_wdc_qddays
from iugonet.ground.ear import ear
from iugonet.ground.mu import mu
from iugonet.ground.kyushugcm import kyushugcm
from iugonet.ground.iprt import iprt
from iugonet.ground.iprt_highres import iprt_highres
from iugonet.ground.fits_to_tplot import fits_to_tplot
from iugonet.ground.avon_vlfb import avon_vlfb
from iugonet.ground.elf_hokudai import elf_hokudai

__all__ = ["gmag_nipr", "gmag_nipr_induction", "eiscat", "eiscat_vief",
           "asi_nipr", "irio_nipr", "lfrto", "hf_tohokuu",
           "aws_rish", "ionosonde_rish", "gmag_icswse_iaga", "gmag_wdc",
           "meteor_rish", "radiosonde_rish", "mf_rish",
           "gps_ro_rish", "gps_atec", "gps_isee", "gaia_gcm_nc", "gaia_cpl_nc",
           "blr_rish", "ltr_rish", "wpr_rish", "ear", "mu",
           "kyushugcm", "iprt", "iprt_highres", "fits_to_tplot", "avon_vlfb",
           "elf_hokudai", "gmag_wdc_qddays"]
__version__ = "0.2.0"
