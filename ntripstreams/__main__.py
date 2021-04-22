#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
from time import time
from ntripstreams import getServerHeader, getNtripSourcetable, getNtripStream


def main():
    import sys
    
    argc = len(sys.argv)
    print('Args:\n', argc, sys.argv)
    if argc == 1:
        header = getServerHeader('http://gnsscaster.dk', 'PIP', 
                                 'otto', 'tystys', 2)
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Serv header > {line}')
        header = getServerHeader('http://gnsscaster.dk', 'PIP', 
                                 'otto', 'tystys', 1)
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Serv header > {line}')
    if argc > 1:
        url = sys.argv[1]
        asyncio.run(getNtripSourcetable(url))
    else: 
        exit(-1)
    if argc > 4:
        stn = sys.argv[2]
        user = sys.argv[3]
        passwd = sys.argv[4]
        asyncio.run(getNtripStream(url, stn, user, passwd))
    elif argc > 2:
        stn = sys.argv[2]
        asyncio.run(getNtripStream(url, stn))


if __name__ == '__main__':
    main()
