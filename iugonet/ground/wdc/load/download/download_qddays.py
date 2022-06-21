
 

from pyspedas.utilities.dailynames import dailynames
from pyspedas.utilities.download   import download
from .config import CONFIG


def download_qddays(trange):

    ## get remote path
    remote_file = dailynames(trange=trange, file_format='%Y', prefix='qd')


    ## download file
    local_files = download(remote_file=remote_file, remote_path=CONFIG['remote_data_dir_qddays'],
                           local_path=CONFIG['local_data_dir_qddays'])

    return local_files    


 
 


