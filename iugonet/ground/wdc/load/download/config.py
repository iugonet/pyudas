import os
CONFIG={'local_data_dir_dst':'',
        'local_data_dir_site':'',
        'local_data_dir_qddays':'',
        'local_data_dir_wp_index':'',
        'local_data_dir_sym' :'',
        'local_data_dir_ae':'',
        'remote_data_dir_dst':'http://wdc-data.iugonet.org/data/hour/index/',
       'remote_data_dir_site':'http://wdc-data.iugonet.org/data/',
       'remote_data_dir_qddays':'http://wdc-data.iugonet.org/data/day/qddays/',
       'remote_data_dir_wp_index':'https://www.isee.nagoya-u.ac.jp/~nose.masahito/s-cubed/data/',
       'remote_data_dir_sym':'http://wdc-data.iugonet.org/data/min/index/asy/',
       'remote_data_dir_ae':'http://wdc-data.iugonet.org/data/'}

root_dir=''
if os.environ.get('HOME') :
    root_dir = os.environ.get('HOME')

if os.environ.get('SPEDAS_DATA_DIR') :
    root_dir = os.environ.get('SPEDAS_DATA_DIR')

CONFIG['local_data_dir_dst']=os.sep.join([root_dir,'iugonet','wdc_kyoto','dst'])
CONFIG['local_data_dir_site']=os.sep.join([root_dir,'iugonet','wdc_kyoto','site'])
CONFIG['local_data_dir_qddays']   = os.sep.join( [root_dir, 'iugonet', 'wdc', 'qddays'])
CONFIG['local_data_dir_wp_index'] = os.sep.join( [root_dir, 'iugonet', 'wdc', 'wp_index'])
CONFIG['local_data_dir_sym']      = os.sep.join( [root_dir, 'iugonet', 'wdc', 'SYM-ASY'] )
CONFIG['local_data_dir_ae']       = os.sep.join( [root_dir, 'iugonet', 'wdc', 'AE'] )
