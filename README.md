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
