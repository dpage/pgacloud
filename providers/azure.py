##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

# Microsoft Azure PostgreSQL provider

import os, sys

from azure.identity import AzureCliCredential
from azure.mgmt.rdbms.postgresql import PostgreSQLManagementClient
from azure.mgmt.rdbms.postgresql.models import ServerForCreate, \
    ServerPropertiesForDefaultCreate, ServerVersion
from azure.mgmt.resource import ResourceManagementClient

from providers._abstract import AbsProvider
from utils.io import output, debug, error
from utils.misc import get_my_ip, get_random_id


class AzureProvider(AbsProvider):
    def __init__(self):
        self._clients = {}
        self._credentials = None
        self._subscription_id = None
        self._default_region = 'westeurope'

    def init_args(self, parsers):
        """ Create the command line parser for this provider """
        self.parser = parsers.add_parser('azure',
                                         help='Azure Database for PostgreSQL',
                                         epilog='Credentials...')

        self.parser.add_argument('--region', default=self._default_region,
                                 help='name of the Azure location')

        self.parser.add_argument('--resource-group', required=True,
                                 help='name of the Azure resource group')

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='Azure commands',
                                             dest='command')

        # Create the create instance command parser
        parser_deploy = parsers.add_parser('create-instance',
                                           help='create a new instance')

        parser_deploy.add_argument('--name', required=True,
                                   help='name of the instance')
        parser_deploy.add_argument('--db-name', default='postgres',
                                   help='name of the default database')
        parser_deploy.add_argument('--db-password', required=True,
                                   help='password for the database')
        parser_deploy.add_argument('--db-username', default='postgres',
                                   help='user name for the database')

    ##########################################################################
    # Azure Helper functions
    ##########################################################################

    def _get_azure_client(self, type):
        """ Create/cache/return an Azure client object """
        # Acquire a credential object using CLI-based authentication.
        if self._credentials is None:
            self._credentials = AzureCliCredential()

        # Retrieve subscription ID from environment variable
        if self._subscription_id is None:
            try:
                self._subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
            except KeyError as e:
                print('The environment variable AZURE_SUBSCRIPTION_ID is not '
                      'set')
                sys.exit(1)

        if type in self._clients:
            return self._clients[type]

        if type == 'postgresql':
            client = PostgreSQLManagementClient(self._credentials,
                                                self._subscription_id)
        elif type == 'resource':
            client = ResourceManagementClient(self._credentials,
                                              self._subscription_id)

        self._clients['type'] = client

        return self._clients['type']

    def _create_resource_group(self, args):
        resource_client = self._get_azure_client('resource')

        debug(args,
              'Creating resource group with name: {}...'.format(
                  args.resource_group))
        result = resource_client.resource_groups.create_or_update(
            args.resource_group,
            {"location": args.region})

        return [result.__dict__]

    def _create_azure_instance(self, args):
        # Obtain the management client object
        postgresql_client = self._get_azure_client('postgresql')

        # Provision the server and wait for the result
        debug(args, 'Creating Azure instance: {}...'.format(args.name))
        try:
            poller = postgresql_client.servers.begin_create(
                args.resource_group,
                args.name,
                ServerForCreate(
                    location=args.region,
                    properties=ServerPropertiesForDefaultCreate(
                        administrator_login=args.db_username,
                        administrator_login_password=args.db_password,
                        version=ServerVersion.ELEVEN
                    )
                )
            )
        except Exception as e:
            error(args, e)

        server = poller.result()

        return [server.__dict__]

    def _create_firewall_rule(self, args):
        postgresql_client = self._get_azure_client('postgresql')
        ip = get_my_ip()

        name = 'pgacloud_{}_{}_{}'.format(args.name,
                                          ip.replace('.', '-'),
                                          get_random_id())

        # Provision the rule and wait for completion
        debug(args, 'Adding ingress rule for: {}/32...'.format(ip))
        poller = postgresql_client.firewall_rules.begin_create_or_update(
            args.resource_group,
            args.name, name,
            {"start_ip_address": ip, "end_ip_address": ip}
        )

        firewall_rule = poller.result()

        return [firewall_rule.__dict__]

    ##########################################################################
    # User commands
    ##########################################################################
    def cmd_create_instance(self, args):
        """ Deploy an Azure instance and firewall rule """
        data = {}

        data['resource_groups'] = self._create_resource_group(args)
        data['instances'] = self._create_azure_instance(args)
        data['firewall_rules'] = self._create_firewall_rule(args)

        output(data)


def load():
    """ Loads the current provider """
    return AzureProvider()
