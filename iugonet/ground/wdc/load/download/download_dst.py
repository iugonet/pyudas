
from pyspedas.utilities.dailynames import dailynames
from pyspedas.utilities.download   import download
from .config import CONFIG
import os

def download_dst(trange,level):
    """
    trange= (Optional) Time range of interest  (2 element array), if
         this is not set, the default is to prompt the user. Note
          that if the input time range is not a full month, a full
          month's data is loaded.
          fomat is trange=["yyyy-mm-dd"] ex:trange=["2012-04-05","2012-04-15"]

    level = The level of the data, the default is 'final' for geomag data.
          For AE and Dst index, the default is ['final', 'provsional'].
    """
    out_files = []
    dir_wdc=[]
    prefix=[]
    name_befo=[]
    name_afte=[]
    #[hour/index/pvdst/2012/dst1203]
    res='hour'
    if(level=='all' or level=='final'):
        dir_wdc.append('dst/')
        prefix.append("dst")
    if(level=='all' or level[0:4]=='prov'):
        dir_wdc.append('pvdst/')
        prefix.append("dst")
    for i in range(len(dir_wdc)):
        name_befo=dailynames(trange=trange,file_format='%Y',directory=dir_wdc[i],suffix='/')
        for j in range(len(name_befo)):
            name_afte.extend(dailynames(trange=trange,file_format='%y%m',prefix=prefix[i], directory=name_befo[j]))
    #print(name_afte)
    name_afte=[lf for lf in name_afte if ((lf[-4:-2]==lf[-10:-8])or(lf[-4:-2]==lf[10:-8]))]
    print(name_afte)
    name_local=[lf.replace("/",os.sep) for lf in name_afte]
    out_files = []
    for (rf, lf) in zip(name_afte, name_local) :
        f = download(remote_file=rf, local_file=lf,remote_path=CONFIG['remote_data_dir_dst'],last_version=False,local_path=CONFIG['local_data_dir_dst'])
        if f:
            out_files.append(f[0])
    #local_files=download(remote_file=name_afte,remote_path=CONFIG['remote_data_dir_dst'],last_version=False,local_path=CONFIG['local_data_dir_dst'])
    #if local_files is not None:
    #            for file in local_files:
    #                out_files.append(file)
    out_files = sorted(out_files)
    return out_files

#download_dst(trange=['2011-1-1', '2011-1-2'],level='final')
