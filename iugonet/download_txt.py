import urllib.request
import os

# Download ascii file of txt extension.
def download_txt(
        remote_path='',
        remote_file='',
        local_path='',
        local_file='',
    ):
    out = []
    urls = [remote_path+rfile for rfile in remote_file]
    local_file_in = local_file
    for url in urls:
        resp_data = None
        url_file = url[url.rfind("/")+1:]
        url_base = url.replace(url_file, '')

        # automatically use remote_file locally if local_file is not specified
        if local_file_in == '':
            # if remote_file is the entire url then only use the filename
            if remote_path == '':
                local_file = url_file
            else:
                local_file = url.replace(remote_path, '')

                if local_file == '':  # remote_path was the full file name
                    local_file = remote_path[remote_path.rfind("/")+1:]    
        filename = os.path.join(local_path, local_file)

        tmp = filename.split('.')
        save_folder = tmp[0]
        tmp = save_folder.split('/')
        tmp = tmp[-1]
        save_folder = save_folder.replace(tmp, '')
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)

        urllib.request.urlretrieve(url, filename)
        out.append(filename)
    
    return out