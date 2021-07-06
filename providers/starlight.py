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
    def _init_args(self, parsers):
        """ Create the command line parser for this provider """
        self.parser = parsers.add_parser('starlight', help='EDB Starlight')

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='Starlight command help',
                                             dest='command')

        # Create the Deploy command parser
        parser_deploy = parsers.add_parser('deploy-cluster',
                                           help='deploy a new cluster')
        parser_deploy.add_argument('--name', required=True,
                                   help='name of the cluster')
        parser_deploy.add_argument('--type', required=True,
                                   help='machine type for the cluster nodes')

        # Create the Types command parser
        parser_types = parsers.add_parser('list-types',
                                          help='list available instance types')

    def deploy_cluster(self, args):
        print(
            'Deploying Starlight Cluster "{}" using instance type {}...'.format(
                args.name, args.type))

    def list_types(self, args):
        print('Listing Starlight Types...')


def load():
    """ Loads the current provider """
    return StarlightProvider()
