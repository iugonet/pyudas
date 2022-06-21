
 
import os
from pyspedas.utilities.dailynames import dailynames
from pyspedas.utilities.download   import download
#from .config import CONFIG
from .config import CONFIG




def download_wp_index(trange):

    ### get remote path ###
    directory   = dailynames(trange=trange,file_format='%Y%m%d')                 # YYYYMMDD
    remote_file = dailynames(trange=trange,file_format='%Y%m%d',prefix='index_', suffix='.html')
    remote_path = [ CONFIG['remote_data_dir_wp_index']  + dire[0:6] + '/' for dire in directory]



    ### download file ###
    directory   = [ os.sep.join( [dire[:4], dire[4:6]] ) for dire in directory ]  # YYYYMMDD -> YYYY/MM
    local_path  = [ os.sep.join( [CONFIG['local_data_dir_wp_index'], dire] ) for dire in directory ]

    local_files = []
    for (rf, rp, lp) in zip(remote_file, remote_path, local_path) :
        lf = download(remote_file=rf, remote_path=rp, local_path=lp)
        if lf : local_files.append(lf[0])



    ### html to text
    for lf in local_files :
        with open(lf) as f :
            lines = f.readlines()
            l1 = [i for i, st in enumerate(lines) if '<pre>' in st]
            l2 = [i for i, st in enumerate(lines) if '</pre>' in st]
            lines = lines[l1[0]+1:l2[0]]
        with open(lf, 'w') as f :
            f.writelines(lines)
    


    return local_files




