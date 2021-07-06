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
        config.read('~/.aws/credentials')

        self._default_region = config.get('default', 'region',
                                          fallback='us-east-1')

    def _init_args(self, parsers):
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
                                 help='name of the AWS region')

        # Create the command sub-parser
        parsers = self.parser.add_subparsers(help='RDS command help',
                                             dest='command')

        # Create the deploy cluster command parser
        parser_deploy = parsers.add_parser('deploy-cluster',
                                           help='deploy a new cluster')
        parser_deploy.add_argument('--name', required=True,
                                   help='name of the cluster')
        parser_deploy.add_argument('--db-name', default='postgres',
                                   help='name of the default database')
        parser_deploy.add_argument('--db-password', required=True,
                                   help='password for the database')
        parser_deploy.add_argument('--db-username', default='postgres',
                                   help='user name for the database')
        parser_deploy.add_argument('--instance-type', required=True,
                                   help='machine type for the cluster nodes')
        parser_deploy.add_argument('--storage-iops', type=int, default=0,
                                   help='storage IOPs to allocate')
        parser_deploy.add_argument('--storage-size', type=int, required=True,
                                   help='storage size in GB')
        parser_deploy.add_argument('--storage-type', default='gp2',
                                   help='storage type for the data database')

        # Create the get cluster command parser
        parsers.add_parser('get-clusters', help='get information on clusters')

        # Create the get VPCs command parser
        parsers.add_parser('get-vpcs', help='get information on VPCs')

        # Create the get instance types command parser
        parsers.add_parser('get-instance-types', help='get information on '
                                                      'available instance '
                                                      'types')

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
        """ Create a new security group for the cluster """
        ec2 = self._get_aws_client('ec2', args)
        ip = get_my_ip()

        # Deploy the security group
        try:
            name = 'pgacloud_{}_{}_{}'.format(args.name,
                                              ip.replace('.', '-'),
                                              get_random_id())
            debug(args,
                  'Creating security group with name: {}...'.format(name))
            response = ec2.create_security_group(
                Description='Inbound access for {} to RDS cluster {}'.format(
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

    def _get_security_group(self, args, security_group):
        """ Describe a security group """
        ec2 = self._get_aws_client('ec2', args)

        try:
            debug(args,
                  'Retrieving security group configuration for: {}...'.format(
                      security_group))
            response = ec2.describe_security_groups(
                GroupIds=[security_group, ])
        except Exception as e:
            try:
                ec2.delete_security_group(GroupId=security_group)
            except:
                pass
            error(args, e)

        return response['SecurityGroups']

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
                ec2.delete_security_group(GroupId=security_group)
            except:
                pass
            error(args, 'RDS instance {} already exists.'.format(args.name))
        except Exception as e:
            try:
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

            debug(args, 'Status: {}'.format(status))
            time.sleep(30)

        return response['DBInstances']

    def _get_clusters(self, args):
        """ Describe RDS instances """
        rds = self._get_aws_client('rds', args)

        data = []
        try:
            debug(args,
                  'Retrieving instance information...')
            paginator = rds.get_paginator('describe_db_instances')
            page_iterator = paginator.paginate(Filters=[
                {
                    'Name': 'engine',
                    'Values': [
                        'postgres',
                    ]
                },
            ]
            )

            for page in page_iterator:
                data.extend(page['DBInstances'])
        except Exception as e:
            error(args, e)

        return data

    def _get_vpcs(self, args):
        """ Describe VPCs """
        ec2 = self._get_aws_client('ec2', args)

        data = []
        try:
            debug(args,
                  'Retrieving VPC information...')
            paginator = ec2.get_paginator('describe_vpcs')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                data.extend(page['Vpcs'])
        except Exception as e:
            error(args, e)

        return data

    def _get_instance_types(self, args):
        """ Describe instance types """
        pricing = self._get_aws_client('pricing', args)

        data = []
        try:
            debug(args,
                  'Retrieving instance type information...')
            paginator = pricing.get_paginator('get_attribute_values')
            page_iterator = paginator.paginate(ServiceCode='AmazonRDS', AttributeName='instanceType')

            for page in page_iterator:
                for value in page['AttributeValues']:
                    data.append(value['Value'])
        except Exception as e:
            error(args, e)

        return data

    ##########################################################################
    # User commands
    ##########################################################################
    def deploy_cluster(self, args):
        """ Deploy and RDS cluster and security group """
        data = {}

        security_group = self._create_security_group(args)
        self._add_ingress_rule(args, security_group)
        data['security_groups'] = self._get_security_group(args,
                                                           security_group)
        data['clusters'] = self._create_rds_instance(args, security_group)

        output(data)

    def get_clusters(self, args):
        """ Describe all Postgres instances """
        data = self._get_clusters(args)

        output({'clusters': data})

    def get_vpcs(self, args):
        """ Describe all VPCs """
        data = self._get_vpcs(args)

        output({'vpcs': data})

    def get_instance_types(self, args):
        """ Describe all instance types """
        data = self._get_instance_types(args)

        output({'instance-types': data})

def load():
    """ Loads the current provider """
    return RdsProvider()
