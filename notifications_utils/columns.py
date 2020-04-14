from collections import OrderedDict
from functools import lru_cache
from orderedset import OrderedSet


class Columns(OrderedDict):

    """
    `Columns` behaves like an ordered dictionary, except it normalises
    case, whitespace, hypens and underscores in keys.

    In other words,
    Columns({'FIRST_NAME': 'example'}) == Columns({'first name': 'example'})
    >>> True
    """

    def __init__(self, row_dict):
        for key, value in row_dict.items():
            self[key] = value

    @classmethod
    def from_keys(cls, keys):
        """
        This behaves like `dict.from_keys`, except:
        - it normalises the keys to ignore case, whitespace, hypens and
          underscores
        - it stores the original, unnormalised key as the value of the
          item so it can be retrieved later
        """
        return cls(OrderedDict([(key, key) for key in keys]))

    def keys(self):
        return OrderedSet(super().keys())

    def __getitem__(self, key):
        return super().__getitem__(self.make_key(key))

    def __setitem__(self, key, value):
        super().__setitem__(self.make_key(key), value)

    def __contains__(self, key):
        return super().__contains__(self.make_key(key))

    def get(self, key, default=None):
        return self[key] if key in self else default

    def copy(self):
        return self.__class__(super().copy())

    def as_dict_with_keys(self, keys):
        return {
            key: self.get(key) for key in keys
        }

    @staticmethod
    @lru_cache(maxsize=32, typed=False)
    def make_key(original_key):
        if original_key is None:
            return None
        return "".join(
            character.lower() for character in original_key if character not in ' _-'
        )


class Row(Columns):

    message_too_long = False
    message_empty = False

    def __init__(
        self,
        row_dict,
        index,
        error_fn,
        recipient_column_headers,
        placeholders,
        template,
    ):

        self.index = index
        self.recipient_column_headers = recipient_column_headers
        self.placeholders = placeholders

        if template:
            template.values = row_dict
            self.message_too_long = template.is_message_too_long()
            self.message_empty = template.is_message_empty()

        super().__init__(OrderedDict(
            (key, Cell(key, value, error_fn, self.placeholders))
            for key, value in row_dict.items()
        ))

    def __getitem__(self, key):
        return super().__getitem__(key) if key in self else Cell()

    def get(self, key, default=None):
        if key not in self and default is not None:
            return default
        return self[key]

    @property
    def has_error(self):
        return self.has_error_spanning_multiple_cells or any(
            cell.error for cell in self.values()
        )

    @property
    def has_bad_recipient(self):
        return any(
            self.get(recipient_column).recipient_error
            for recipient_column in self.recipient_column_headers
        )

    @property
    def has_error_spanning_multiple_cells(self):
        return self.message_too_long or self.message_empty

    @property
    def has_missing_data(self):
        return any(
            cell.error == Cell.missing_field_error
            for cell in self.values()
        )

    @property
    def recipient(self):
        columns = [
            self.get(column).data for column in self.recipient_column_headers
        ]
        return columns[0] if len(columns) == 1 else columns

    @property
    def personalisation(self):
        return Columns({
            key: cell.data for key, cell in self.items()
            if key in self.placeholders
        })

    @property
    def recipient_and_personalisation(self):
        return Columns({
            key: cell.data for key, cell in self.items()
        })


class Cell():

    missing_field_error = 'Missing'

    def __init__(
        self,
        key=None,
        value=None,
        error_fn=None,
        placeholders=None
    ):
        self.data = value
        self.error = error_fn(key, value) if error_fn else None
        self.ignore = Columns.make_key(key) not in (placeholders or [])

    def __eq__(self, other):
        if not other.__class__ == self.__class__:
            return False
        return all((
            self.data == other.data,
            self.error == other.error,
            self.ignore == other.ignore,
        ))

    @property
    def recipient_error(self):
        return self.error not in {None, self.missing_field_error}
