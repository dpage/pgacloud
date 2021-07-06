##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2021, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

class AbsProvider:
    """ Abstract provider """
    parser = None

    def _init_args(self, parsers):
        pass

    def _commands(self):
        """ Get the list of commands for the current provider. """
        attrs = filter(lambda attr: not attr.startswith('_'), dir(self))
        commands = {}

        for attr in attrs:
            method = getattr(self, attr)
            commands[attr] = method

        return commands

    def help(self):
        """ Prints the provider level help """
        self.parser.print_help()
