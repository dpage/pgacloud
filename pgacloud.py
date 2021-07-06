#!/usr/bin/env python3

##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

import argparse
import os


def load_providers():
    """ Loads all the providers """
    providers = {}

    for filename in os.listdir('providers'):
        filename = 'providers/' + filename

        if os.path.isfile(filename):
            basename = os.path.basename(filename)
            base, extension = os.path.splitext(basename)

            if extension == ".py" and not basename.startswith("_"):
                module = __import__("providers." + basename[:-3],
                                    fromlist=["providers"])
                provider = module.load()
                providers[basename[:-3]] = provider

    return providers


def get_args(providers):
    """ Creates the parsers and returns the args """
    # Create the top-level parser
    parser = argparse.ArgumentParser(prog='pgacloud.py')
    parser.add_argument('--debug', action=argparse.BooleanOptionalAction,
                        default=False, help='send debug messages to stderr')

    # Create the provider sub-parser
    parsers = parser.add_subparsers(help='provider help', dest='provider')

    # Load the provider parsers
    for provider in providers:
        providers[provider].init_args(parsers)

    args = parser.parse_args()

    return parser, args


def execute_command(providers, parser, args):
    """ Executes the command in the provider """

    # Switch - for _ in command names. We use - in the CLI syntax for ease of
    # use, but we need an _ in Python function names
    if 'command' in args and args.command is not None:
        args.command = args.command.replace('-', '_')

    # Figure out what provider the command was for (if any) and call the
    # relevant function. If we don't get a match, print the help
    if args.provider in providers and args.command is not None:
        command = providers[args.provider].commands()[args.command]
        command(args)
    else:
        # If no provider has been given, display the top level help,
        # otherwise, call the help() method in the provider
        if args.provider is None:
            parser.print_help()
        else:
            command = providers[args.provider].commands()['help']
            command()


def main():
    """ Entry point """
    # Load the providers
    providers = load_providers()

    # Get the args
    parser, args = get_args(providers)

    # Execute the command
    execute_command(providers, parser, args)


if __name__ == '__main__':
    main()
