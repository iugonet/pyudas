

def iug_wdc_ack(site):
    acknowledg_str_dst=\
    'The DST data are provided by the World Data Center for Geomagnetism, Kyoto, and'+ \
    ' are not for redistribution (http://wdc.kugi.kyoto-u.ac.jp/). Furthermore, we thank'+ \
    ' the geomagnetic observatories (Kakioka [JMA], Honolulu and San Juan [USGS], Hermanus'+ \
    ' [RSA], Alibag [IIG]), NiCT, INTERMAGNET, and many others for their cooperation to'+ \
    ' make the Dst index available.'\
    +'The distribution of DST data has been partly supported by the IUGONET (Inter-university Upper atmosphere Global Observation NETwork) project (http://www.iugonet.org/)'+ \
    'funded by the Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan.'    
    acknowledg_str = \
    'The rules for the data use and exchange are defined'+ \
    ' by the Guide on the World Data Center System '+ \
    ' (ICSU Panel on World Data Centers, 1996).'+\
    ' Note that information on the appropriate institution(s)'+\
    ' is also supplied with the WDC data sets.'+\
    ' If the data are used in publications and presentations,'+\
    ' the data suppliers and the WDC for Geomagnetism, Kyoto'+\
    ' must properly be acknowledged.'+\
    ' Commercial use and re-distribution of WDC data are, in general, not allowed.'+\
    ' Please ask for the information of each observatory to the WDC.'\
    +'The distribution of the data has been partly supported by the IUGONET (Inter-university Upper atmosphere Global Observation NETwork) project (http://www.iugonet.org/) '+\
    'funded by theMinistry of Education, Culture, Sports, Science and Technology (MEXT), Japan.'
#    print("***********")
    if (site=="dst"):
        return acknowledg_str_dst
    else:
        return acknowledg_str
 #   print("***********")
 #   return 0
