# SPDX-FileCopyrightText: 2022-present deepset GmbH <info@deepset.ai>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Literal, TypeVar, Union, get_args, get_origin

from haystack import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _types_are_compatible(
    sender, receiver, type_validation: Literal["strict", "relaxed", "disabled"] = "strict"
) -> bool:
    """
    Determines if two types are compatible based on the specified validation mode.

    :param sender: The sender type.
    :param receiver: The receiver type.
    :param type_validation: The validation mode, which can be:
        - "strict": Enforces strict type compatibility.
        - "relaxed": Allows bidirectional compatibility checks, permitting sender and receiver to be subclasses
          of each other and allowing partial compatibility for Union and Literal types.
        - "disabled": Skips type validation. Always returns True.
    :return: True if the types are compatible, False otherwise.
    """
    if type_validation == "strict":
        return _strict_types_are_compatible(sender, receiver)
    elif type_validation == "relaxed":
        return _relaxed_types_are_compatible(sender, receiver)
    else:
        return True


def _strict_types_are_compatible(sender, receiver):  # pylint: disable=too-many-return-statements
    """
    Checks whether the sender type is equal to or a subtype of the receiver type under strict validation.

    Note: this method has no pretense to perform proper type matching. It especially does not deal with aliasing of
    typing classes such as `List` or `Dict` to their runtime counterparts `list` and `dict`. It also does not deal well
    with "bare" types, so `List` is treated differently from `List[Any]`, even though they should be the same.
    Consider simplifying the typing of your components if you observe unexpected errors during component connection.

    :param sender: The sender type.
    :param receiver: The receiver type.
    :return: True if the sender type is strictly compatible with the receiver type, False otherwise.
    """
    if sender == receiver or receiver is Any:
        return True

    if sender is Any:
        return False

    try:
        if issubclass(sender, receiver):
            return True
    except TypeError:  # typing classes can't be used with issubclass, so we deal with them below
        pass

    sender_origin = get_origin(sender)
    receiver_origin = get_origin(receiver)

    if sender_origin is not Union and receiver_origin is Union:
        return any(_strict_types_are_compatible(sender, union_arg) for union_arg in get_args(receiver))

    # Both must have origins and they must be equal
    if not (sender_origin and receiver_origin and sender_origin == receiver_origin):
        return False

    # Compare generic type arguments
    sender_args = get_args(sender)
    receiver_args = get_args(receiver)
    if len(sender_args) > len(receiver_args):
        return False

    return all(_strict_types_are_compatible(*args) for args in zip(sender_args, receiver_args))


def _relaxed_types_are_compatible(sender, receiver) -> bool:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
    """
    Checks whether two types are compatible under relaxed validation.

    Relaxed validation allows bidirectional compatibility checks, permitting sender and receiver to be subclasses
    of each other and allowing partial compatibility for Union and Literal types.

    :param sender: The first type to compare.
    :param receiver: The second type to compare.
    :return: True if the types are compatible, False otherwise.
    """
    # Handle Any type and direct equality
    if sender is Any or receiver is Any or sender == receiver:
        return True

    # Handle sender being a subclass of receiver
    try:
        if issubclass(sender, receiver):
            return True
    except TypeError:  # typing classes can't be used with issubclass, so we deal with them below
        pass

    # Handle receiver being a subclass of sender
    try:
        if issubclass(receiver, sender):
            return True
    except TypeError:  # typing classes can't be used with issubclass, so we deal with them below
        pass

    sender_origin = get_origin(sender)
    receiver_origin = get_origin(receiver)

    # Handle Union types
    if sender_origin is Union or receiver_origin is Union:
        return _relaxed_check_union_compatibility(sender, receiver, sender_origin, receiver_origin)

    # Handle non-Union types
    if not (sender_origin and sender_origin and sender_origin == receiver_origin):
        return False

    # Compare generic type arguments
    sender_args = get_args(sender)
    receiver_args = get_args(receiver)

    # Handle when both sender and receiver are Literal types
    if sender_origin is Literal and receiver_origin is Literal:
        return any(sender_arg == receiver_arg for sender_arg in sender_args for receiver_arg in receiver_args)

    if len(sender_args) != len(receiver_args):
        return False

    return all(_relaxed_types_are_compatible(s_arg, r_arg) for s_arg, r_arg in zip(sender_args, receiver_args))


def _relaxed_check_union_compatibility(sender: T, receiver: T, sender_origin: Any, receiver_origin: Any) -> bool:
    """
    Handles compatibility checks for Union types under relaxed validation.

    :param sender: The sender type.
    :param receiver: The receiver type.
    :param sender_origin: The origin of the sender type.
    :param receiver_origin: The origin of the receiver type.
    :return: True if there is partial compatibility between the sender and receiver types, False otherwise.
    """
    if sender_origin is Union and receiver_origin is not Union:
        return any(_relaxed_types_are_compatible(union_arg, receiver) for union_arg in get_args(sender))
    if receiver_origin is Union and sender_origin is not Union:
        return any(_relaxed_types_are_compatible(sender, union_arg) for union_arg in get_args(receiver))
    # When both are Union types allow partial compatibility
    return any(
        any(_relaxed_types_are_compatible(arg1, arg2) for arg2 in get_args(receiver)) for arg1 in get_args(sender)
    )


def _type_name(type_):
    """
    Util methods to get a nice readable representation of a type.

    Handles Optional and Literal in a special way to make it more readable.
    """
    # Literal args are strings, so we wrap them in quotes to make it clear
    if isinstance(type_, str):
        return f"'{type_}'"

    name = getattr(type_, "__name__", str(type_))

    if name.startswith("typing."):
        name = name[7:]
    if "[" in name:
        name = name.split("[")[0]
    args = get_args(type_)
    if name == "Union" and type(None) in args and len(args) == 2:
        # Optional is technically a Union of type and None
        # but we want to display it as Optional
        name = "Optional"

    if args:
        args = ", ".join([_type_name(a) for a in args if a is not type(None)])
        return f"{name}[{args}]"

    return f"{name}"
