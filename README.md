# pgacloud

This directory contains the *pgacloud* utility. This is a command line tool that
pgAdmin can use to deploy PostgreSQL instances in cloud environments through the
external process infrastructure. 

The utility takes a cloud provider name as the first argument, and then one or 
more non-positional options that define a cloud instances of PostgreSQL. It will
execute the relevant API commands to deploy the instance along with a security
group or equivalent to ensure the instance can be accessed from the client 
machine. It will wait for all asynchronous calls to complete, and then return 
details of the deployment as a JSON document on stdout.

If an error occurs, a JSON document is returned to stdout containing an error
message, and a return code of 1 is given.

The --debug flag can be given before the provider name, which will cause 
log messages to be output on stderr.

## Plugins

The utility has a pluggable architecture, allowing 'providers' to be written for
different cloud environments and then dropped into the 
[plugins directory](/../../plugins).

Any Python file in the plugins directory that has a name ending in '.py' and NOT
beginning with an underscore is treated as a plugin and will be dynamically
loaded.

Plugins are implemented as classes derived from the AbsProvider class in
[plugins/_abstract.py](plugins/_abstract.py). In addition to the plugin class 
that must be defined, a *load()* function must be included which simply returns
and instance of the class, for example:

```python
def load():
    """ Loads the current provider """
    return MyProvider()
```

The provider class implementation has two requirements:

1) It must add *argparser* parsers to the core parser to implement its grammar
   in the ```init_args(self, parsers)``` function.
2) It must contain public member functions with names corresponding to the 
   command defined in the parser, prefixed with 'cmd_', with the exception that 
   underscores are used in place of hyphens. For example, the command 
   *deploy-cluster* will cause the function ```cmd_deploy_cluster(self, args)``` 
   to be called.
   
See [plugins/rds.py](plugins/rds.py) for a comprehensive example, and 
[plugins/starlight.py](plugins/starlight.py)

## Usage

[Subject to change - for illustrative purposes only]

```shell
./pgacloud.py --help
usage: pgacloud.py [-h] [--debug | --no-debug] {rds,starlight} ...

positional arguments:
  {rds,starlight}      provider help
    rds                Amazon AWS RDS PostgreSQL
    starlight          EDB Starlight

optional arguments:
  -h, --help           show this help message and exit
  --debug, --no-debug  send debug messages to stderr (default: False)
```
```shell
./pgacloud.py rds --help
usage: pgacloud.py rds [-h] [--region REGION] {deploy-cluster,get-clusters,get-vpcs,get-instance-types} ...

positional arguments:
  {deploy-cluster,get-clusters,get-vpcs,get-instance-types}
                        RDS command help
    deploy-cluster      deploy a new cluster
    get-clusters        get information on clusters
    get-vpcs            get information on VPCs
    get-instance-types  get information on available instance types

optional arguments:
  -h, --help            show this help message and exit
  --region REGION       name of the AWS region

Credentials are read from ~/.aws/config by default and can be overridden in the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables. The default region is read from ~/.aws/config and will fall back to us-east-1 if not present.
```
```shell
./pgacloud.py rds deploy-cluster --help
usage: pgacloud.py rds deploy-cluster [-h] --name NAME [--db-name DB_NAME] --db-password DB_PASSWORD [--db-username DB_USERNAME] --instance-type INSTANCE_TYPE [--storage-iops STORAGE_IOPS] --storage-size STORAGE_SIZE [--storage-type STORAGE_TYPE]

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           name of the cluster
  --db-name DB_NAME     name of the default database
  --db-password DB_PASSWORD
                        password for the database
  --db-username DB_USERNAME
                        user name for the database
  --instance-type INSTANCE_TYPE
                        machine type for the cluster nodes
  --storage-iops STORAGE_IOPS
                        storage IOPs to allocate
  --storage-size STORAGE_SIZE
                        storage size in GB
  --storage-type STORAGE_TYPE
                        storage type for the data database
```
