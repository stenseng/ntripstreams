#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
from time import time
#from ntripstreams import getServerHeader, getNtripSourcetable, getNtripStream
from ntripstreams import NtripStream

def main():
    import sys
    
    argc = len(sys.argv)
    
    ntripstream = NtripStream()

    if argc == 1:
        header = ntripstream.getServerHeader('http://gnsscaster.dk', 'PIP', 
                                 'otto', 'tystys', 2)
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Serv header > {line}')
        header = ntripstream.getServerHeader('http://gnsscaster.dk', 'PIP', 
                                 'otto', 'tystys', 1)
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Serv header > {line}')
    elif argc == 2:
        url = sys.argv[1]
        asyncio.run(ntripstream.getNtripSourcetable(url))
    elif argc == 3:
        url = sys.argv[1]
        stn = sys.argv[2]
        asyncio.run(ntripstream.getNtripStream(url, stn))
    elif argc == 5:
        url = sys.argv[1]
        stn = sys.argv[2]
        user = sys.argv[3]
        passwd = sys.argv[4]
        asyncio.run(ntripstream.getNtripStream(url, stn, user, passwd))


if __name__ == '__main__':
    main()
