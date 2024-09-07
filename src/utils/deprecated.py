"""
Deprecated decorator from StackOverflow:
https://stackoverflow.com/questions/2536307/decorators-in-the-python-standard-lib-deprecated-specifically
"""
import functools
import warnings


def deprecated(reason: str = ""):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    def decorator(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            warnings.simplefilter('always', DeprecationWarning)
            msg = f"Call to deprecated function {func.__name__}."

            if reason:
                msg += f"\nReason: {reason}"

            warnings.warn(
                msg,
                category=DeprecationWarning,
                stacklevel=2
            )
            warnings.simplefilter('default', DeprecationWarning)
            return func(*args, **kwargs)

        return new_func

    # If the decorator is called without arguments
    if callable(reason):
        f = reason
        reason = ""
        return decorator(f)

    return decorator

