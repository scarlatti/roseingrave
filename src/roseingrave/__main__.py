"""
__main__.py
The command-line interface for Roseingrave.
"""

# ======================================================================

import click

from .reauth import reauth
from .fix_input import fix_input
from .create_sheet import create_sheet
from .volunteer_summary import volunteer_summary
from .piece_summary import piece_summary
from .compile_pieces import compile_pieces
from .import_master import import_master
from .export_master import export_master

# ======================================================================


class OrderedGroup(click.Group):
    """Lists the commands in the listed order (instead of alphabetical).
    """

    def __init__(self, *args, **kwargs):
        commands = kwargs.get('commands', None)
        if commands is not None:
            if isinstance(commands, list):
                kwargs['commands'] = {cmd.name: cmd for cmd in commands}
        super().__init__(*args, **kwargs)

    def list_commands(self, ctx):
        return list(self.commands.keys())


cli = OrderedGroup(
    commands=[
        reauth,
        fix_input,
        create_sheet,
        volunteer_summary,
        piece_summary,
        compile_pieces,
        import_master,
        export_master,
    ],
    help='Massively scalable musical source comparator'
)

if __name__ == '__main__':
    cli()
