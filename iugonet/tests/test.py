
import os
import unittest
from pyspedas.utilities.data_exists import data_exists

import pyspedas

class LoadTestCases(unittest.TestCase):
    def test_load_mag_nipr_data(self):
        mag_vars = iugonet.mag_nipr()
        self.assertTrue(data_exists('nipr_mag_syo_1sec'))

    def test_load_mag_nipr_induction_data(self):
        fc_vars = iugonet.mag_nipr_induction()
        self.assertTrue(data_exists('nipr_imag_syo_20hz'))        
        
if __name__ == '__main__':
    unittest.main()