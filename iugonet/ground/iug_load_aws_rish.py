def iug_load_aws_rish(
  datatype='troposphere',
  site='all',
  trange='',
  donwloadonly=False
):
  '''
  PURPOSE:
  Queries the RISH server for the surface meterology data 
  taken by the automatic weather station (AWS) 
  and loads data into tplot format.

  KEYWOARDS:
  datatype = Observation data type. For example, iug_load_aws_rish, datatype = 'troposphere'.
            The default is 'troposphere'. 
  site = AWS observation site.  
        For example, iug_load_aws_rish, site = 'bik'.
        The default is 'all', i.e., load all available observation points.
  trange = (Optional) Time range of interest  (2 element array), if
          this is not set, the default is to prompt the user. Note
          that if the input time range is not a full day, a full
          day's data is loaded.
  /downloadonly, if set, then only download the data, do not load it
                into variables.
  '''

  ## Site code check
  site_list = ['bik', 'ktb', 'mnd', 'pon', 'sgk'] # all sites(default)
  site_code = []
  # check site codes
  if site in site_list:
    site_code.append(site)
  elif site != 'all':
    print('This station code is not valid. Please input the allowed keywords, all, bik, ktb, mnd, pon, and sgk.')
    return
  else:
    site_code = site_list
  print(site_code)

  ## Load data of aws
  for i in range(len(site_code)):
    # load of aws data at Indonesian sites
    if (site_code[i] == 'bik') or (site_code[i] == 'ktb') or (site_code[i] == 'mnd') or (site_code[i] == 'pon'):
      iug_load_aws_id, datatype = 1,2
    # load of aws data at the Shigaraki sites
    elif (site_code[i] == 'sgk'):
      iug_load_aws_sgk, datatype = 1,2
      