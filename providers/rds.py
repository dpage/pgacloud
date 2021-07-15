##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

# AWS RDS PostgreSQL provider

import configparser
import os
import time

import boto3

from providers._abstract import AbsProvider
from utils.io import debug, error, output
from utils.misc import get_my_ip, get_random_id


class RdsProvider(AbsProvider):
    def __init__(self):
        self._clients = {}

        # Get the credentials; environment takes precedence over config
        # TODO: Use the correct path on Windows
        credentials = configparser.ConfigParser()
        credentials.read('~/.aws/credentials')

        self._access_key = credentials.get('default', 'aws_access_key_id',
                                           fallback='')
        self._secret_key = credentials.get('default', 'aws_secret_access_key',
                                           fallback='')

        if 'AWS_ACCESS_KEY_ID' in os.environ:
            self._access_key = os.environ['AWS_ACCESS_KEY_ID']

        if 'AWS_SECRET_ACCESS_KEY' in os.environ:
            self._secret_key = os.environ['AWS_SECRET_ACCESS_KEY']

        # Get the default region
        config = configparser.ConfigParser()
        config.read('~/.aws/config')

        self._default_region = config.get('default', 'region',
                                          fallback='us-east-1')

    def init_args(self, parsers):
        """ Create the command line parser for this provider """
        self.parser = parsers.add_parser('rds',
                                         help='Amazon AWS RDS PostgreSQL',
                                         epilog='Credentials are read from '
                                                '~/.aws/config by default and '
                                                'can be overridden in the '
                                                'AWS_ACCESS_KEY_ID and '
                                                'AWS_SECRET_ACCESS_KEY '
                                                'environment variables. '
                                                'The default region is read '
                                                'from ~/.aws/config and will '
                                                'fall back to us-east-1 if '
                                                'not present.')
        self.parser.add_argument('--region', default=self._default_region,
                                 help='name of the AWS region (default: {})'
                                 .format(self._default_region))

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='RDS commands',
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
                                            default=13, type=int,
                                            help='major version of PostgreSQL '
                                                 'to deploy (default: 13)')
        parser_create_instance.add_argument('--instance-type', required=True,
                                            help='machine type for the '
                                                 'instance nodes, e.g. '
                                                 'db.m3.large')
        parser_create_instance.add_argument('--storage-iops', type=int,
                                            default=0,
                                            help='storage IOPs to allocate '
                                                 '(default: 0)')
        parser_create_instance.add_argument('--storage-size', type=int,
                                            required=True,
                                            help='storage size in GB')
        parser_create_instance.add_argument('--storage-type', default='gp2',
                                            help='storage type for the data '
                                                 'database (default: gp2)')

    ##########################################################################
    # AWS Helper functions
    ##########################################################################
    def _get_aws_client(self, type, args):
        """ Create/cache/return an AWS client object """
        if type in self._clients:
            return self._clients[type]

        session = boto3.Session(
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

        self._clients['type'] = session.client(type, region_name=args.region)

        return self._clients['type']

    def _create_security_group(self, args):
        """ Create a new security group for the instance """
        ec2 = self._get_aws_client('ec2', args)
        ip = get_my_ip()

        # Deploy the security group
        try:
            name = 'pgacloud_{}_{}_{}'.format(args.name,
                                              ip.replace('.', '-'),
                                              get_random_id())
            debug(args, 'Creating security group: {}...'.format(name))
            response = ec2.create_security_group(
                Description='Inbound access for {} to RDS instance {}'.format(
                    ip, args.name),
                GroupName=name
            )
        except Exception as e:
            error(args, e)

        return response['GroupId']

    def _add_ingress_rule(self, args, security_group):
        """ Add a local -> PostgreSQL ingress rule to a security group """
        ec2 = self._get_aws_client('ec2', args)
        ip = get_my_ip()

        try:
            debug(args,
                  'Adding ingress rule for: {}/32...'.format(ip))
            ec2.authorize_security_group_ingress(
                GroupId=security_group,
                IpPermissions=[
                    {
                        'FromPort': 5432,
                        'ToPort': 5432,
                        'IpProtocol': 'tcp',
                        'IpRanges': [
                            {
                                'CidrIp': '{}/32'.format(ip),
                                'Description': 'pgcloud client {}'.format(ip)
                            },
                        ]
                    },
                ]
            )
        except Exception as e:
            error(args, e)

    def _create_rds_instance(self, args, security_group):
        """ Create an RDS instance """
        ec2 = self._get_aws_client('ec2', args)
        rds = self._get_aws_client('rds', args)

        try:
            debug(args, 'Creating RDS instance: {}...'.format(args.name))
            rds.create_db_instance(DBInstanceIdentifier=args.name,
                                   AllocatedStorage=args.storage_size,
                                   DBName=args.db_name,
                                   Engine='postgres',
                                   EngineVersion=str(args.db_major_version),
                                   StorageType=args.storage_type,
                                   StorageEncrypted=True,
                                   Iops=args.storage_iops,
                                   AutoMinorVersionUpgrade=True,
                                   MultiAZ=False,
                                   MasterUsername=args.db_username,
                                   MasterUserPassword=args.db_password,
                                   DBInstanceClass=args.instance_type,
                                   VpcSecurityGroupIds=[
                                       security_group,
                                   ])

        except rds.exceptions.DBInstanceAlreadyExistsFault as e:
            try:
                debug(args, 'Deleting security group: {}...'.
                      format(security_group))
                ec2.delete_security_group(GroupId=security_group)
            except:
                pass
            error(args, 'RDS instance {} already exists.'.format(args.name))
        except Exception as e:
            try:
                debug(args, 'Deleting security group: {}...'.
                      format(security_group))
                ec2.delete_security_group(GroupId=security_group)
            except:
                pass
            error(args, e)

        # Wait for completion
        running = True
        while running:
            response = rds.describe_db_instances(
                DBInstanceIdentifier=args.name)

            db_instance = response['DBInstances'][0]
            status = db_instance['DBInstanceStatus']

            if status != 'creating' and status != 'backing-up':
                running = False

            if running:
                time.sleep(30)

        return response['DBInstances']

    ##########################################################################
    # User commands
    ##########################################################################
    def cmd_create_instance(self, args):
        """ Deploy and RDS instance and security group """
        data = {}

        security_group = self._create_security_group(args)
        self._add_ingress_rule(args, security_group)
        instance = self._create_rds_instance(args, security_group)

        data = {'Id': instance[0]['DBInstanceIdentifier'],
                'Location': instance[0]['AvailabilityZone'],
                'SecurityGroupId': security_group,
                'Hostname': instance[0]['Endpoint']['Address'],
                'Port': instance[0]['Endpoint']['Port'],
                'Database': instance[0]['DBName'],
                'Username': instance[0]['MasterUsername']
                }

        output(data)


def load():
    """ Loads the current provider """
    return RdsProvider()
