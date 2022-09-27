import os

CONFIG = {'local_data_dir': 'iugonet_data/'}

# override local data directory with environment variables
if os.environ.get('SPEDAS_DATA_DIR'):
    CONFIG['local_data_dir'] = os.sep.join(
        [os.environ['SPEDAS_DATA_DIR'], 'iugonet/'])

if os.environ.get('IUGONET_DATA_DIR'):
    CONFIG['local_data_dir'] = os.environ['IUGONET_DATA_DIR']
