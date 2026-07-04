class InputError(Exception):
    """Base class for input validation errors."""
    pass

class MissingMonthError(InputError):
    """Raised when monthly data is missing required months (must have exactly 12)."""
    pass

class InvalidDataFormatError(InputError):
    """Raised when the CSV format is invalid (e.g., missing required columns)."""
    pass

class OutOfRangeError(InputError):
    """Raised when numeric data is out of acceptable bounds."""
    pass
