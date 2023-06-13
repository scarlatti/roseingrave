"""
__main__.py
The command-line interface for Roseingrave.
"""

# ======================================================================

import click

from .__version__ import __version__
from .compile_pieces import compile_pieces
from .create_sheet import create_sheet
from .export_summary import export_summary
from .fix_input import fix_input
from .import_summary import import_summary
from .piece_summary import piece_summary
from .reauth import reauth
from .volunteer_summary import volunteer_summary

# ======================================================================


class OrderedGroup(click.Group):
    """Lists the commands in the listed order (instead of alphabetical)."""

    def __init__(self, *args, **kwargs):
        commands = kwargs.get("commands", None)
        if commands is not None:
            if isinstance(commands, list):
                kwargs["commands"] = {cmd.name: cmd for cmd in commands}
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
        import_summary,
        export_summary,
    ],
    help="Massively scalable musical source comparator",
)
cli = click.version_option(
    version=__version__,
    package_name="roseingrave",
    message="%(prog)s, version %(version)s",
)(cli)

if __name__ == "__main__":
    cli()
