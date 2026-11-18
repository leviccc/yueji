"""Reader identity follows request worker threads and is explicit in jobs."""
from contextvars import ContextVar

current_account = ContextVar('yueji_account', default=None)
