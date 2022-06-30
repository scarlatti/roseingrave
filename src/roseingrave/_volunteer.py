"""
_volunteer.py
The Volunteer class.
"""

# ======================================================================

__all__ = ('Volunteer',)

# ======================================================================


class Volunteer:
    """Volunteer class."""

    def __init__(self, kwargs, known_pieces):
        """Initialize a volunteer from a JSON dict.

        Args:
            kwargs (Dict): The JSON dict.
            known_pieces (Dict[str, Piece]): The known pieces.

        Raises:
            ValueError: If any required key is not found.
        """

        for key in ('email', 'pieces'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._email = kwargs['email']
        self._pieces = {}
        self._unknown = []
        for piece_name in kwargs['pieces']:
            if piece_name in self._pieces:
                continue
            piece = known_pieces.get(piece_name, None)
            if piece is not None:
                self._pieces[piece_name] = True
            else:
                self._unknown.append(piece_name)

    @property
    def email(self):
        return self._email

    @property
    def pieces(self):
        return list(self._pieces.keys())

    @property
    def unknown_pieces(self):
        return self._unknown

    def combine(self, other):
        """Combine this volunteer with another by taking the union of
        all pieces.
        """
        for piece_name in other.pieces:
            if piece_name not in self._pieces:
                self._pieces[piece_name] = True

    def to_json(self):
        """Return a JSON reprsentation of this volunteer."""
        return {
            'email': self._email,
            'pieces': list(self._pieces.keys()),
        }
