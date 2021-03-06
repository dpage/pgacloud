##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

# Microsoft Azure PostgreSQL provider

import os
import sys

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.mgmt.rdbms.postgresql import PostgreSQLManagementClient
from azure.mgmt.rdbms.postgresql.models import ServerForCreate, \
    ServerPropertiesForDefaultCreate, Sku, StorageProfile
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
                                         epilog='Credentials are read from '
                                                'the environment, '
                                                'specifically, the '
                                                'AZURE_SUBSCRIPTION_ID, '
                                                'AZURE_TENANT_ID, '
                                                'AZURE_CLIENT_ID and '
                                                'AZURE_CLIENT_SECRET '
                                                'variables. '
                                                'See https://docs.microsoft.com/en-us/azure/developer/python/configure-local-development-environment?tabs=cmd '
                                                'for more information.')

        self.parser.add_argument('--region', default=self._default_region,
                                 help='name of the Azure location (default: '
                                      '{})'.format(self._default_region))

        self.parser.add_argument('--resource-group', required=True,
                                 help='name of the Azure resource group')

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='Azure commands',
                                             dest='command')

        # Create the create instance command parser
        parser_create_instance = parsers.add_parser('create-instance',
                                                    help='create a new '
                                                         'instance')

        parser_create_instance.add_argument('--name', required=True,
                                            help='name of the instance')
        parser_create_instance.add_argument('--db-name', default='postgres',
                                            help='name of the default '
                                                 'database '
                                                 '(default: postgres)')
        parser_create_instance.add_argument('--db-password', required=True,
                                            help='password for the database')
        parser_create_instance.add_argument('--db-username',
                                            default='postgres',
                                            help='user name for the database '
                                                 '(default: postgres)')
        parser_create_instance.add_argument('--db-major-version',
                                            default='11',
                                            help='version of PostgreSQL '
                                                 'to deploy (default: 11)')
        parser_create_instance.add_argument('--instance-type', required=True,
                                            help='machine type for the '
                                                 'instance nodes, e.g. '
                                                 'GP_Gen5_8')
        parser_create_instance.add_argument('--storage-size', type=int,
                                            required=True,
                                            help='storage size in GB')

        # Create the delete instance command parser
        parser_delete_instance = parsers.add_parser('delete-instance',
                                                    help='delete an instance')
        parser_delete_instance.add_argument('--name', required=True,
                                            help='name of the instance')

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
        """ Create the Resource Group if it doesn't exist """
        resource_client = self._get_azure_client('resource')

        debug(args,
              'Creating resource group with name: {}...'.format(
                  args.resource_group))
        result = resource_client.resource_groups.create_or_update(
            args.resource_group,
            {"location": args.region})

        return result.__dict__

    def _create_azure_instance(self, args):
        """ Create an Azure instance """
        # Obtain the management client object
        postgresql_client = self._get_azure_client('postgresql')

        # Check if the server already exists
        svr = None
        try:
            svr = postgresql_client.servers.get(args.resource_group, args.name)
        except ResourceNotFoundError:
            pass
        except Exception as e:
            error(args, e)

        if svr is not None:
            error(args, 'Azure Database for PostgreSQL instance {} already '
                        'exists.'.format(args.name))

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
                        version=args.db_major_version,
                        storage_profile=StorageProfile(
                            storage_mb=args.storage_size * 1024,
                            storage_autogrow='Enabled')
                    ),
                    sku=Sku(name=args.instance_type)
                )
            )
        except Exception as e:
            error(args, e)

        server = poller.result()

        return server.__dict__

    def _create_firewall_rule(self, args):
        """ Create a firewall rule on an instance """
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

        return firewall_rule.__dict__

    def _delete_azure_instance(self, args, name):
        """ Delete an Azure instance """
        # Obtain the management client object
        postgresql_client = self._get_azure_client('postgresql')

        # Delete the server and wait for the result
        debug(args, 'Deleting Azure instance: {}...'.format(args.name))
        try:
            poller = postgresql_client.servers.begin_delete(
                args.resource_group,
                args.name
            )
        except Exception as e:
            error(args, e)

        poller.result()


    ##########################################################################
    # User commands
    ##########################################################################
    def cmd_create_instance(self, args):
        """ Deploy an Azure instance and firewall rule """
        rg = self._create_resource_group(args)
        instance = self._create_azure_instance(args)
        fw = self._create_firewall_rule(args)

        data = {
            'Id': instance['id'],
            'ResourceGroupId': rg['name'],
            'FirewallRuleId': fw['id'],
            'Location': instance['location'],
            'Hostname': instance['fully_qualified_domain_name'],
            'Port': 5432,
            'Database': "postgres",
            'Username': instance['administrator_login']
        }

        output(data)

    def cmd_delete_instance(self, args):
        """ Delete an Azure instance """
        self._delete_azure_instance(args, args.name)


def load():
    """ Loads the current provider """
    return AzureProvider()
