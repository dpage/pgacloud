##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

import random
import string
import urllib.request


def get_my_ip():
    """ Return the public IP of this host """
    try:
        external_ip = urllib.request.urlopen(
            'https://ident.me').read().decode('utf8')
    except:
        try:
            external_ip = urllib.request.urlopen(
                'https://ifconfig.me/ip').read().decode('utf8')
        except:
            external_ip = '127.0.0.1'

    return external_ip


def get_random_id():
    """ Return a random 10 byte string """
    letters = string.ascii_letters + string.digits
    return(''.join(random.choice(letters) for i in range(10)))