##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

# Starlight provider

from providers._abstract import AbsProvider


class StarlightProvider(AbsProvider):
    def init_args(self, parsers):
        """ Create the command line parser for this provider """
        self.parser = parsers.add_parser('starlight', help='EDB Starlight')

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='Starlight command help',
                                             dest='command')


def load():
    """ Loads the current provider """
    return StarlightProvider()
