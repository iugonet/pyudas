


import os
from pyspedas.utilities.dailynames import dailynames
from pyspedas.utilities.download   import download
from .config import CONFIG



def download_ae_min(trange, level='provisional') :

    inames = ['ae', 'al', 'au', 'ao']
    ### real time
    if level == 'real_time' :
        # リモートディレクトリの設定
        directory = CONFIG['remote_data_dir_ae_real_time']

        # 年、月、日を含む日付リストを生成
        dates = dailynames(trange=trange, file_format='%Y/%m/%d')
        
        # リモートファイルパスを生成
        remote_files = []
        local_paths = []
        
        for date in dates:
            year, month, day = date.split('/')
            # Create local path for each date
            local_path = os.path.join(CONFIG['local_data_dir_ae_real_time'], year, month, day)
            
            # Generate remote files for each index name
            for iname in inames:
                remote_files.append(f"{directory}/{date}/{iname}{year[2:]}{month}{day}")
                local_paths.append(local_path)

        # Download files
        local_files = []
        for remote_file, local_path in zip(remote_files, local_paths):
            downloaded_file = download(remote_file=remote_file, local_path=local_path)
            if downloaded_file:
                local_files.append(downloaded_file[0])

    ### provisional
    elif level == 'provisional' :
        directory = CONFIG['remote_data_dir_ae'] + 'min/index/'

        ## get remote path
        year = dailynames(trange=trange, file_format='%Y%m')
        year = [ yr[0:4] for yr in year ]*4

        remote_file = []
        for iname in inames :
            remote_file += dailynames(trange=trange, file_format='%y%m', prefix=iname)
        remote_file = [ directory + yr + '/' + rf for (yr, rf) in zip(year, remote_file) ]

        i = 0
        for (rf, yr) in zip(remote_file, year) :
            if int(yr) < 1996 :
                subdir = rf[-6] + '.' + rf[-5]  # ae -> a.e
                remote_file[i] = rf.replace('index/', 'index/'+ subdir + '/')
            if int(yr) >= 1996 :
                remote_file[i] = rf.replace('index/', 'index/pvae/')
            i += 1

        ## download
        local_path = [ os.sep.join( [CONFIG['local_data_dir_ae'], 'min', yr] )
                       for yr in year ]
        local_files = []
        for (lp, rf) in zip(local_path, remote_file) :
            f = download(remote_file=rf, local_path = lp)
            if f :
                local_files.append(f[0])

    ### final
    elif level == 'final' :
        local_files= []

    else:
        print("Could you check the level ? Level must be chosen from  ['provisional','real_time', 'final'] ")
        local_files= []

    return local_files
