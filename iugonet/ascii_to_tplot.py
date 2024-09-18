import pandas as pd
import numpy as np
import datetime as dt
import calendar
import pytplot
import re
from datetime import datetime, timedelta, timezone
from pytplot import get_data, store_data, options, clip, ylim, cdf_to_tplot, zlim
from .load_ascii_format2 import load_ascii_format2
from .load_ascii_format3 import load_ascii_format3

def xor(a,b):
    return bool(a) != bool(b)

def ascii2tplot(filenames,
                trange,
                localtime=0,
                time_column=1,
                format_type = 1,
                data_start=1,
                comment_symbol='%',
                delimiter=' ',
                file_format='csv',
                var_name='',
                time_format=['Y', 'm', 'd', 'H', 'M'],
                input_time=[-1, -1, -1, -1, -1, -1],
                header_only=False,
                notplot=False,
                no_convert_time=False):
    stored_variables = []
    output_table = {}
    metadata = {}
    time_datetime = []
    time_datenum = []
    data = []
    info = []

    # Time format pre-processing
    if isinstance(time_column, int):
        # Only length of time_format = 1 can process time_format which contains space.
        if isinstance(time_format, list) and (len(time_format) > 1):
            print('Error: Inconsistency between time_column and time_format')
            return
        elif isinstance(time_format, list):
            time_format = time_format[0]
        # Here, time_format is char.
        # Set the flag on time_column_1 processing.
        flag_time_column_scalar = True
    else:
        flag_time_column_scalar = False

    # Pre-process input_time
    # input_time is set by caller in order to cover undefined time variables.
    input_time_format = ['Y', 'm', 'd', 'H', 'M', 'S']
    ind = [i for i, x in enumerate(input_time) if x != -1] 
    input_format_str = []
    input_time_str = []
    if len(ind) != 0:
        for l in ind:
            input_format_str.append(input_time_format[l])
            if l == 1:
                # Year
                input_time_str.append(('%04d'%input_time[l]))
            else:
                # Others
                input_time_str.append(('%02d'%input_time[l]))
    
    # Read and analyze file.
    if len(filenames) != 0:
        if file_format == 'csv' or file_format == 'txt':
            info = []
            for filename in filenames:
                # Initialization
                info_tmp = []
                time_text = []
                tmp_file_data = []
                time_text = []
                time_datetime_file = []
                # Process if header_only
                if header_only:
                    if file_format == 'csv':
                        try:
                            # df = pd.read_csv(filename, encoding='shiftJIS', dtype=str)
                            with open(filename, 'r') as temp_f:
                                # get No of columns in each line
                                col_count = [ len(l.split(",")) for l in temp_f.readlines() ]
                            column_names = [i for i in range(0, max(col_count))]
                            df = pd.read_csv(filename, header=None, names=column_names)
                            bl = np.where(np.array(df.isna().all()))[0]
                            if len(bl) != 0:
                                di = []
                                for drop_idx in range(len(bl)):
                                    di.append(bl[drop_idx])
                                df = df.drop(columns=di)
                        except:
                            print('Error: Cannot open input file. ' + filename)
                    elif file_format == 'txt':
                        try:
                            f = open(filename, 'r')
                            datalist = f.readlines()
                        except:
                            print('Error: Cannot open input file. ' + filename)
                
                    if data_start > 1:
                        # Header is in the file. Keep header info.
                        for j in range(data_start-1):
                            if file_format == 'csv':
                                tline = df.iloc[j]
                            elif file_format == 'txt':
                                tline = datalist[j]
                                tline = re.split(r'[\s,]', tline)
                                tline.remove('')
                            tmp = ''
                            for k in range(tline.shape[0]):
                                tmp = tmp + tline[k]
                            info_tmp.append(tmp)
                    elif comment_symbol == '':
                        row = 0
                        while True:
                            # Read line from file.
                            if file_format == 'csv':
                                tline = df.iloc[row]
                            elif file_format == 'txt':
                                tline = datalist[row]
                                tline = re.split(r'[\s,]', tline)
                                tline.remove('')
                            tmp = ''
                            idx = []
                            for k in range(tline.shape[0]):
                                if comment_symbol in tline[k]:
                                    tmp = tmp + tline[k]
                                    idx.append(k)
                            if len(idx) != 0:
                                if idx[0] == 0:
                                    # Maybe header line. Keep the line as header
                                    info_tmp.append(tmp)
                            row = row + 1
                            if row == df.shape[0]:
                                break
                    if file_format == 'txt':
                        f.close()
                    # In this case, just read header and return this function.
                    # Set info
                    tmp = []
                    tmp.Text = info_tmp
                    tmp.Format = 'ascii'
                    info_ret = tmp
                    data_ret = []
                    return
                
                # Analyze individual file.
                if flag_time_column_scalar:
                    # In case of flag_time_column_scalar
                    if file_format == 'csv':
                        try:
                            # df = pd.read_csv(filename, encoding='shiftJIS', dtype=str)
                            with open(filename, 'r') as temp_f:
                                # get No of columns in each line
                                col_count = [ len(l.split(",")) for l in temp_f.readlines() ]
                            column_names = [i for i in range(0, max(col_count))]
                            df = pd.read_csv(filename, header=None, names=column_names)
                            bl = np.where(np.array(df.isna().all()))[0]
                            if len(bl) != 0:
                                di = []
                                for drop_idx in range(len(bl)):
                                    di.append(bl[drop_idx])
                                df = df.drop(columns=di)
                        except:
                            print("Error: Cannot open input file. ")
                            print(filename)
                            return
                    elif file_format == 'txt':
                        try:
                            f = open(filename, 'r')
                            datalist = f.readlines()
                        except:
                            print("Error: Cannot open input file. ")
                            print(filename)
                            return
                    # Separate header area at first.
                    if data_start > 1:
                        # Header is in the file. Keep header info.
                        for j in range(data_start-1):
                            if file_format == 'csv':
                                tline = df.iloc[j]
                            elif file_format == 'txt':
                                tline = datalist[j]
                                tline = re.split(r'[\s,]', tline)
                                tline.remove('')
                            tmp = ''
                            for k in range(tline.shape[0]):
                                tmp = tmp + tline[k]
                            info_tmp.append(tmp)
                    header_lines = 0
                
                    # Now header is stored in the info_tmp
                    # Process line by line, and save data into temp variable.
                    row = 0
                    while True:
                        if file_format == 'csv':
                            tline = df.iloc[j]
                        elif file_format == 'txt':
                            tline = datalist[j]
                            tline = re.split(r'[\s,]', tline)
                            tline.remove('')
                        tmp = ''
                        for k in range(tline.shape[0]):
                            tmp = tmp + tline[row]
                            row = row + 1
                            if row == df.shape[0]:
                                break
                        tline = tmp
                        
                        # Get rid of comment.
                        if comment_symbol != '':
                            idx = tline.find(comment_symbol)
                            if idx == 0:
                                # Maybe header line. Keep the line as header
                                info_tmp.append(tline)
                            # Delete after comment symbol
                            tline = tline[0:idx]
                        
                        # Time format processing.
                        if flag_time_column_scalar:
                            time_format_len = 0
                            if 'Y' in time_format:
                                time_format_len = time_format_len + 4
                            if 'm' in time_format:
                                time_format_len = time_format_len + 2
                            if 'd' in time_format:
                                time_format_len = time_format_len + 2
                            if 'H' in time_format:
                                time_format_len = time_format_len + 2
                            if 'M' in time_format:
                                time_format_len = time_format_len + 2
                            if 'S' in time_format:
                                time_format_len = time_format_len + 2
                            time_text = time_text.append(tline[0:time_format_len])

                            # Delete data from tline.
                            if ' ' in delimiter:
                                # Usually after the time column, there is delimiter.
                                tline = tline[time_format_len+1:-1]
                                tline = tline.strip()
                            else:
                                # Delimiter is space, it may contain no space just
                                # after the time data.
                                tline = tline[time_format_len:-1]
                                tline = tline.strip()
                        tmp_file_data.append(tline)
                    if file_format == 'txt':
                        f.close()
                else:
                    # In case of NOT flag_time_column_scalar
                    if data_start > 1:
                        if file_format == 'csv':
                            try:
                                with open(filename, 'r') as temp_f:
                                    # get No of columns in each line
                                    col_count = [ len(l.split(",")) for l in temp_f.readlines() ]
                                column_names = [i for i in range(0, max(col_count))]
                                df = pd.read_csv(filename, header=None, names=column_names)
                                bl = np.where(np.array(df.isna().all()))[0]
                                if len(bl) != 0:
                                    di = []
                                    for drop_idx in range(len(bl)):
                                        di.append(bl[drop_idx])
                                    df = df.drop(columns=di)
                            except:
                                print("Error: Cannot open input file. ")
                                print(filename)
                                return
                        elif file_format == 'txt':
                            try:
                                f = open(filename, 'r')
                                datalist = f.readlines()
                            except:
                                print("Error: Cannot open input file. ")
                                print(filename)
                        # Header is in the file. Keep header info.
                        for j in range(data_start-1):
                            if file_format == 'csv':
                                tline = df.values[j]
                            elif file_format == 'txt':
                                tline = datalist[j]
                                tline = re.split(r'[\s,]', tline)
                                tline.remove('')
                            tmp = ''
                            for k in range(len(tline)):
                                if tmp == '':
                                    if 'nan' != str(tline[k]):
                                        tmp = tmp + str(tline[k])
                                else:
                                    if 'nan' != str(tline[k]):
                                        tmp = tmp + ', ' + str(tline[k])
                            info_tmp.append(tmp)
                        if file_format == 'txt':
                            f.close()
                    tmp_file_name = filename
                    header_lines = data_start - 1
                
                # Read data area
                try:
                    if flag_time_column_scalar:
                        Num = len(tmp_file_data)
                        st = 1
                        tbl = np.array([])

                        if header_lines > 0:
                            st = header_lines + 1
                        dat = []
                        for i in range(st, Num):
                            tline = tmp_file_data[i]
                            C = tline.split(delimiter)
                            tmp = np.array(C)
                            if tbl.size == 0:
                                tbl = tmp
                            else:
                                tbl = np.vstack([tbl, tmp])
                    else:
                        flg = False
                        if file_format == 'csv':
                            delimiter_str = '['
                            for sp in delimiter:
                                if sp != ' ' and sp != '-':
                                    delimiter_str = delimiter_str + sp
                                else:
                                    flg = True
                            delimiter_str = delimiter_str + ']'
                            tbl = pd.read_csv(tmp_file_name, skiprows=header_lines, sep=delimiter_str, header=None)
                            tbl.columns = tbl.columns.astype(str)
                            bl = np.where(np.array(tbl.isna().all()))[0]
                            if len(bl) != 0:
                                di = []
                                for drop_idx in range(len(bl)):
                                    tbl = tbl.drop(str(bl[drop_idx]), axis=1)

                            # # 変更前
                            # if '-' in delimiter:
                            #     # 日時の区切り文字に-が含まれている場合（数値の-と区別するため別処理を追加）　
                            #     tmp_tbl = pd.concat([tbl['0'].str.split('-', expand=True), tbl.drop('0', axis=1)], axis=1)
                                            
                            # for sp in range(len(tbl.columns)):
                            #     # スペース文字が存在する場合(read_csv時に区切り文字としてスペースを追加するとエラーが発生)
                            #     if isinstance(tbl.values[0, sp], str):
                            #         if ' ' in tbl.values[0, sp]:
                            #             tmp_tbl = tbl.drop(str(sp), axis=1)
                            #             tmp_insert = tbl[str(sp)].str.split(' ', expand=True)
                            #             for idx in range(len(tmp_insert.columns)):
                            #                 tmp_tbl.insert(sp+idx, str(len(tbl.columns)+idx+1), tmp_insert.values[:, idx])
                            ########################################################

                            # 変更案（2024/05/22）
                            for sp in range(len(tbl.columns)):
                                # スペース文字が存在する場合(read_csv時に区切り文字としてスペースを追加するとエラーが発生)
                                if isinstance(tbl.values[0, sp], str):
                                    if ' ' in tbl.values[0, sp]:
                                        tmp_tbl = tbl.drop(str(sp), axis=1)
                                        tmp_insert = tbl[str(sp)].str.split(' ', expand=True)
                                        for idx in range(len(tmp_insert.columns)):
                                            tmp_tbl.insert(sp+idx, str(len(tbl.columns)+idx+1), tmp_insert.values[:, idx])
                            tmp_tbl.columns = range(len(tmp_tbl.columns))
                            tmp_tbl.columns = tmp_tbl.columns.astype(str)

                            if '-' in delimiter:
                                # 日時の区切り文字に-が含まれている場合（数値の-と区別するため別処理を追加）　
                                tmp_tbl = pd.concat([tmp_tbl['0'].str.split('-', expand=True), tmp_tbl.drop('0', axis=1)], axis=1)
                            tmp_tbl.columns = range(len(tmp_tbl.columns))
                            tmp_tbl.columns = tmp_tbl.columns.astype(str)
                            ########################################################

                            tbl = tmp_tbl
                        elif file_format == 'txt':
                            delimiter_str = ''
                            for sp in delimiter:
                                if sp != ' ':
                                    delimiter_str = delimiter_str + sp
                                else:
                                    flg = True
                                    delimiter_str = r'\s'
                                tbl = pd.read_table(tmp_file_name, skiprows=header_lines, sep=delimiter_str, header=None)
                        if flg:
                            tmp_idx = []
                            for col in range(len(tbl.values[0])):
                                if ' ' in str(tbl.values[0][col]):
                                    tmp_idx.append(col)
                            for c in tmp_idx:
                                data_pd = tbl[c].str.split(' ', expand=True)
                                tbl = tbl.drop(columns=c)
                                cnt = 0
                                for d in range(data_pd.shape[1]):
                                    tbl.insert(c+cnt, str(c+cnt), data_pd[d])
                                    cnt = cnt + 1
                except:
                    print('Error: Analyzing ' + tmp_file_name + ' failed.')
                    return

                data_tmp = []
                for j in range(tbl.shape[1]):
                    # entry = tbl.values[0, j]
                    # try:
                    #     entry = float(entry)
                    # except:
                    #     pass
                    data_tmp.append(tbl.values[:, j])
                
                # time data processing
                if not flag_time_column_scalar:
                    # time_column is not 1 or contains several columns.
                    # In this case, the number of valid time_columns and the number
                    # of valid time_format should be the same.
                    try:
                        time_format_new = []
                        for j in range(len(time_column)):
                            if time_column[j] != -1:
                                tmp = data_tmp[time_column[j]-1]
                            
                                # Check if time data is numeric date or not.
                                # e.g AUG, JAN -> 08, 01
                                mt = tmp[0]
                                if type(mt) == str:
                                    if len(str(mt)) == 3:
                                        tmp = [int(datetime.strptime(x, '%b').strftime('%m')) for x in tmp]
                                        
                                    else:
                                        tmp = [int(s) for s in tmp]
                                    data_tmp[time_column[j]-1] = np.array(tmp, dtype='object')

                                if isinstance(float(tmp[0]), float):
                                    if time_format[j] == 'Y':
                                        length = 4
                                    elif time_format[j] == 'm':
                                        length = 2
                                    elif time_format[j] == 'd':
                                        length = 2
                                    elif time_format[j] == 'H':
                                        length = 2
                                    elif time_format[j] == 'M':
                                        length = 2
                                    elif time_format[j] == 'S':
                                        length = 2
                                    
                                    # ind_dot = time_format[j].find('.')
                                    # if ind_dot == -1:
                                    #     sfmt = '%0' + str(length) + 'd'
                                    # else:
                                    #     # time_format contains '.'
                                    #     len_fi = length - ind_dot
                                    #     sfmt = '%0' + str(ind_dot) + '.' + str(len_fi) + 'f'
                                    
                                    sfmt = '%0' + str(length) + 'd'
                                    stmp = []
                                    if len(time_text) == 0:
                                        for k in range(len(tmp)):
                                            time_text.append(sfmt%float(tmp[k]))
                                    else:
                                        for k in range(len(tmp)):
                                            time_text[k] = time_text[k] + sfmt%float(tmp[k])
                                else:
                                    time_text.append(tmp)
                                if len(time_format_new) == 0:
                                    time_format_new.append('%' + time_format[j])
                                else:
                                    time_format_new[0] = time_format_new[0] + '%' + time_format[j]
                    except:
                        print('Error: inconsistency of time_format and time_column.')
                        if len(tmp) == 0:
                            if (' ' in tmp) and not (' ' in delimiter):
                                print('One possibility is time column contains space and is not set in delimiter.')
                        return
                else:
                    time_format_new = time_format
                
                # Get datetime.
                try:
                    for j in range(len(time_text)):
                        # if the '0' is eliminated, add '0'
                        string = time_text[j]
                        if xor(' ' in time_format_new, ' ' in string):
                            if ' ' in time_format_new:
                                ind = time_format_new[0].find(' ')
                            elif ' ' in string:
                                ind = string.find(' ')
                                string[ind] = '0'

                        # Convert to datetime
                        tmp_time = ''
                        for o in input_time_str:
                            tmp_time = tmp_time + str(o)
                        tmp_time = tmp_time + str(string)

                        tmp_format = ''
                        for o in input_format_str:
                            tmp_format = tmp_format + '%' + str(o)
                        for o in time_format_new:
                            tmp_format = tmp_format + str(o)

                        tmp = datetime.strptime(tmp_time, tmp_format)

                        # Adjust local time
                        tmp = tmp + dt.timedelta(hours=-localtime)

                        # Put the time data into time_datetime.
                        time_datetime_file.append(tmp)
                except:
                    print('Error: time_format is not valid.')

                # Set time data into time_datenum
                time_datetime.append(time_datetime_file)
                time_datetime_tmp = []
                for o in time_datetime_file:
                    time_datetime_tmp.append(calendar.timegm(o.timetuple()))
                time_datenum.append(time_datetime_tmp)
                
                # Set data
                data.append(data_tmp)
                
                # Set info
                tmp = {}
                tmp['Text'] = info_tmp
                tmp['Format'] = 'ascii'
                info.append(tmp)

            if format_type == 1:
                # Connect ydata.
                # In case, time num = n, ydata{k} is 1xn matrix. (Time dependent
                # variable is 2nd dimension.)
                data = data
                time_datenum = time_datenum
                time_datetime = time_datetime
            elif format_type == 2:
                # Pick up unique time, and connect data.
                # In case, unique time num = n, ydata{k} is mxn matrix. (m is the
                # max data size of every ydata. Fill up with NaN.
                data, time_datenum, time_datetime = load_ascii_format2(data, time_datenum, time_datetime)
            elif format_type == 3:
                # Connect ydata matrix.
                # In case, time num = n, ydata is mxn matrix.
                 data, time_datenum, time_datetime = load_ascii_format3(data, time_datenum, time_datetime)
            else:
                print('Error: Invalid format_type.')
                return
            
            # Connect time dependent variables
            # For ASCII file, all the variables are time dependent.
            if format_type == 3:
                sy = len(data)
                sx = 1
            else:
                sy, sx = len(data), len(data[0])
            time_datenum_ret = []
            time_datetime_ret = []

            if len(filenames) > 1:
                data_ret = data[0]
                tmp_data_ret = []
                tmp_data_ret.append(data_ret)
                time_datenum_ret = time_datenum[0]
                time_datetime_ret = time_datetime[0]

                for i in range(1, len(filenames)):
                    for k in range(sx):
                        # In case format 2 has variable columns.
                        cat1 = tmp_data_ret[k]
                        if np.ndim(np.array(data, dtype=object)) > 3:
                            cat2 = data[i][k]
                        else:
                            cat2 = data[i]

                        ssy1, ssx1 = len(cat1[0]), len(cat1)
                        ssy2, ssx2 = len(cat2[0]), len(cat2)
                        if ssx1 != ssx2:
                            ssx_max = np.max([ssx1, ssx2])
                            cat1_base = np.zeros([ssy1, ssx_max])
                            cat1_base[:, :] = np.nan
                            cat1_base[0:ssy1, 0:ssx1] = cat1
                            cat2_base = np.zeros([ssy2, ssx_max])
                            cat2_base[:, :] = np.nan
                            cat2_base[0:ssy2, 0:ssx2] = cat2
                            cat1 = cat1_base
                            cat2 = cat2_base
                        for x in range(len(cat1)):
                            try:
                                if cat1[x][0].isdigit():
                                    tmp_cat1 = [float(y) for y in cat1[x]]
                                    cat1[x] = tmp_cat1
                            except:
                                pass
                        for x in range(len(cat2)):
                            try:
                                if cat2[x][0].isdigit():
                                    tmp_cat2 = [float(y) for y in cat2[x]]
                                    cat2[x] = tmp_cat2
                            except:
                                pass
                        tmp_data_ret[k] = np.append(cat1, cat2, axis=1)
                    data_ret = tmp_data_ret
                    time_datenum_ret = np.append(time_datenum_ret, time_datenum[i])
                    time_datetime_ret = np.append(time_datetime_ret, time_datetime[i])
            else:
                data_ret = data[0]
                for x in range(len(data_ret)):
                    # try:
                    #     # If data can be converted to float
                    #     tmp_cat1 = [float(y) for y in data_ret[x]]
                    #     if x == 0:
                    #         tmp_ret = tmp_cat1
                    #     else:
                    #         tmp_ret = np.vstack([tmp_ret, tmp_cat1])
                    # except:
                    #     pass
                    tmp_cat1 = [y for y in data_ret[x]]
                    if x == 0:
                        tmp_ret = tmp_cat1
                    else:
                        tmp_ret = np.vstack([tmp_ret, tmp_cat1])
                data_ret = []
                data_ret.append(tmp_ret)
                time_datenum_ret = np.array(time_datenum[0])
                time_datetime_ret = np.array(time_datetime[0])
            
            # Select data between startTime and endTime
            startTime = trange[0]
            endTime = trange[1]
            if startTime == '':
                st = 0
            else:
                if isinstance(startTime, datetime):
                    st = calendar.timegm(startTime.timetuple())
                elif isinstance(startTime, str):
                    tmp_format = ''
                    if ('-' in startTime):
                        tmp_startTime = startTime.replace('-', '')
                    if ('/' in startTime):
                        tmp_startTime = startTime.replace('/', '')
                    if (',' in startTime):
                        tmp_startTime = startTime.replace(',', '')
                    if ('.' in startTime):
                        tmp_startTime = startTime.replace('.', '')
                    if (':' in startTime):
                        tmp_startTime = startTime.replace(':', '')
                    try:
                        st = datetime.strptime(tmp_startTime, '%Y%m%d')
                    except:
                        print('Input time range format is wrong.\n')
                        print('Time range should be Year/Month/Day')
                elif isinstance(startTime, int):
                    st = startTime
                else:
                    print('Error on startTime. Please check it.')
                # adjust local time
                st = st + dt.timedelta(hours=-localtime)
                st = calendar.timegm(st.timetuple())
            
            if endTime == '':
                ed = np.inf
            else:
                if isinstance(endTime, datetime):
                    ed = calendar.timegm(endTime.timetuple())
                elif isinstance(endTime, str):
                    tmp_format = ''
                    if ('-' in endTime):
                        tmp_endTime = endTime.replace('-', '')
                    if ('/' in endTime):
                        tmp_endTime = endTime.replace('/', '')
                    if (',' in endTime):
                        tmp_endTime = endTime.replace(',', '')
                    if ('.' in endTime):
                        tmp_endTime = endTime.replace('.', '')
                    if (':' in endTime):
                        tmp_endTime = endTime.replace(':', '')
                    try:
                        ed = datetime.strptime(tmp_endTime, '%Y%m%d')
                    except:
                        print('Input time range format is wrong.\n')
                        print('Time range should be Year/Month/Day')
                elif isinstance(endTime, int):
                    ed = endTime
                else:
                    print('Error on startTime. Please check it.')
                # adjust local time
                ed = ed + dt.timedelta(hours=-localtime)
                ed = calendar.timegm(ed.timetuple())

            # time_data is time variable
            # For ASCII file, all the variables are time dependent.
            if format_type == 3:
                sy = len(data)
                sx = 1
            else:
                # sy, sx = len(data), len(data[0])
                sy, sx = len(data), len(data_ret[0])
            ind = np.where(np.logical_and(np.array(time_datenum_ret) >= st, np.array(time_datenum_ret) <= ed))[0]

            for i in range(sx):
                # if np.ndim(data_ret) > 2:
                #     tmp = data_ret[i]
                # else:
                #     tmp = data_ret
                tmp = data_ret[0][i]
                if np.ndim(tmp) == 2:
                    tmp = tmp[:, ind]
                elif np.ndim(tmp) == 3:
                    tmp = tmp[:, :, ind]
                elif np.ndim(tmp) == 4:
                    tmp = tmp[:, :, :, ind]
                elif np.ndim(tmp) == 5:
                    tmp = tmp[:, :, :, ind]
                data_ret[0][i] = tmp
            time_datenum_ret = time_datenum_ret[ind]
            time_datetime_ret = time_datetime_ret[ind]

            # Add time data to data_ret.
            # The first column is time data.
            # If time_column == 1, no change of the number of columns.
            # If time_column is not 1, the first column is time data which is added.
            tmp = []
            if no_convert_time == 0:
                # serial time
                tmp  = time_datenum_ret
            else:
                # separate time
                format = 'yyyy MM dd HH mm ss'
                tmp = time_datetime_ret

            data_ret.insert(0, tmp)
            info = info[0]

            # print('Reading... ' + filename)
            # df = pd.read_csv(filename, encoding='shiftJIS',dtype=str)
            # v=np.zeros(len(df.columns)-1)
            # for i in range(1,len(df.columns)):
            #     v[i-1]= float(df.columns[i])
            # df1=df.iloc[:,0]
            # time=np.zeros(len(df1))
            # y=df.iloc[0:len(time),1:len(v)+1].to_numpy()
            # for i in range(len(df1)):
            #     time[i]=datetime.datetime.strptime(df1[i],'%Y/%m/%d %H:%M').timestamp()+timeshift#jst補正
            # ydata=np.zeros([len(y[:,0]),len(y[0,:])])
            # for i in range(len(y[:,0])):
            #     for j in range(len(y[0,:])):
            #         ydata[i,j]=float(y[i,j])
            # var_name=prefix+'_'+sitename+'_'+parameter+'norm'
            # var_data=store_data(var_name, {'x': time,'y':ydata,'v':v})
            # return var_name
        else:
            print('wrong file format')
        
        if len(data_ret) != 0:
            time = data_ret[0]
            dat_pr = data_ret[1][len(time_format):len(data_ret[1]), :]
            if format_type == 1:
                output_table[var_name + '_all'] = data_ret
                output_table[var_name + '_time'] = time
                press = dat_pr[0]
                precipi = dat_pr[1]
                rh = dat_pr[2]
                sr = dat_pr[3]
                temp = dat_pr[4]
                wnddir = dat_pr[5]
                wndspd = dat_pr[6]
                output_table[var_name + '_press'] = press
                output_table[var_name + '_precipi'] = precipi
                output_table[var_name + '_rh'] = rh
                output_table[var_name + '_sr'] = sr
                output_table[var_name + '_temp'] = temp
                output_table[var_name + '_wnddir'] = wnddir
                output_table[var_name + '_wndspd'] = wndspd
                store_data(var_name+'_press', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_press']})
                store_data(var_name+'_precipi', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_precipi']})
                store_data(var_name+'_rh', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_rh']})
                store_data(var_name+'_sr', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_sr']})
                store_data(var_name+'_temp', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_temp']})
                store_data(var_name+'_wnddir', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_wnddir']})
                store_data(var_name+'_wndspd', data={'x': output_table[var_name+'_time'], 'y': output_table[var_name+'_wndspd']})
            elif format_type == 3:
                alt = np.array([])
                tmp_info = info['Text'][0]
                tmp_info = tmp_info.split(',')
                for i in tmp_info:
                    try:
                        alt = np.append(alt, float(i))
                    except:
                        pass
                output_table[var_name + '_all'] = data_ret
                output_table[var_name + '_info'] = info
                output_table[var_name + '_time'] = time
                output_table[var_name + '_alt'] = alt
                output_table[var_name] = dat_pr.T
                for i in range(len(output_table[var_name + '_time']) - 1):
                    output_table[var_name + '_alt'] = np.vstack((output_table[var_name + '_alt'], alt))
                row, col = np.where(output_table[var_name] == 999)
                output_table[var_name][row, col] = np.nan
                output_table[var_name] = output_table[var_name].astype(float)
                store_data(var_name, data={'x': output_table[var_name+'_time'], 'y': output_table[var_name], 'v':output_table[var_name + '_alt']})
            if notplot:
                return output_table
            
            if var_name not in stored_variables:
                stored_variables.append(var_name)
            
            return stored_variables
    else:
        print('No file is set. Need at least 1 file to read.')
        return