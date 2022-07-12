"""Functions to bisect sorted, line-based files."""

import contextlib
import io
import os
import typing


T = typing.TypeVar("T")
PathLike = typing.Union[str, bytes, os.PathLike]


def _linear_search_file(
    file: typing.BinaryIO,
    value: T,
    *,
    key: typing.Callable[[str], T],
    encoding: str,
) -> io.TextIOWrapper:
    """
    Helper function to `bisect_file_left`.  Performs a linear search through
    the specified file stream as a fallback for when binary search is not
    possible.
    """
    while True:
        line_start = file.tell()
        line = file.readline().decode(encoding=encoding)
        if not line:
            break

        try:
            k = key(line)
        except ValueError as e:
            if not line.rstrip():
                continue
            raise e from None

        # XXX: Ignore type checks until there's a built-in `Comparable` type.
        if value <= k:  # type: ignore
            file.seek(line_start, os.SEEK_SET)
            break

    return io.TextIOWrapper(file, encoding=encoding)


def _bisect_file_left(
    file: typing.BinaryIO,
    value: T,
    *,
    key: typing.Callable[[str], T],
    encoding: str,
) -> io.TextIOWrapper:
    """
    Helper function to `bisect_file_left`.  Performs a binary search through
    the specified file stream.
    """
    file_length = file.seek(0, os.SEEK_END)
    if file_length == 0:
        return io.TextIOWrapper(file, encoding=encoding)

    start = 0  # Inclusive.
    end = file_length  # Exclusive.
    while True:
        mid = (start + end) // 2

        if start == end:
            # Empty interval.
            break

        file.seek(mid, os.SEEK_SET)

        # The seek position might be in the middle of a line; discard
        # the incomplete portion so that we can read the next line
        # whole.
        file.readline()

        while True:
            mid = file.tell()
            if file.tell() < end:
                line = file.readline().decode(encoding=encoding)
            else:
                # We read the (possibly incomplete) last line in the interval.
                # We can't tell if `mid` started in the middle of a line or
                # not, so read lines sequentially from the start, which is
                # expected to always be the start of a line.
                file.seek(start, os.SEEK_SET)
                return _linear_search_file(file, value, key=key, encoding=encoding)

            try:
                k = key(line)
                break
            except ValueError as e:
                if not line.rstrip():
                    continue
                raise e from None

        # XXX: Ignore type checks until there's a built-in `Comparable` type.
        if value < k:  # type: ignore
            end = mid
        elif value > k:  # type: ignore
            start = mid
        else:
            break

    file.seek(mid, os.SEEK_SET)
    return io.TextIOWrapper(file, encoding=encoding)


@contextlib.contextmanager
def bisect_file_left(
    path: PathLike,
    value: T,
    *,
    key: typing.Callable[[str], T],
    encoding: str = "utf-8",
) -> typing.Generator[io.TextIOWrapper, None, None]:
    """
    Bisects a line-based file.  The lines in the file must already be sorted.

    Yields a text stream whose stream position is set such that all lines
    preceding that position would satisfy `key(line) < value` and all lines
    after and including that position would satisfy `key(line) >= value`.
    """
    with open(path, "rb") as f:
        yield _bisect_file_left(f, value, key=key, encoding=encoding)
