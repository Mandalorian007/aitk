"""Accessibility tree traversal using ApplicationServices AXUIElement."""

from .errors import require_macos, GuiError, PermissionDeniedError, AppNotFoundError

require_macos()

from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyAttributeNames,
    AXUIElementPerformAction,
    AXIsProcessTrusted,
    kAXErrorSuccess,
    kAXErrorAPIDisabled,
    kAXErrorCannotComplete,
)
from AppKit import NSWorkspace


# Common attributes to include in tree dump
TREE_ATTRIBUTES = [
    "AXRole",
    "AXRoleDescription",
    "AXTitle",
    "AXDescription",
    "AXValue",
    "AXEnabled",
    "AXFocused",
    "AXPosition",
    "AXSize",
    "AXIdentifier",
]

# Attributes for element search
SEARCH_ATTRIBUTES = ["AXTitle", "AXDescription", "AXValue", "AXIdentifier", "AXLabel"]


def check_accessibility_permission() -> bool:
    """Check if accessibility permission is granted.

    Returns:
        True if accessibility access is granted.
    """
    return AXIsProcessTrusted()


def _get_attribute(element, attr: str):
    """Get a single attribute value from an AXUIElement."""
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    if err == kAXErrorSuccess:
        return value
    return None


def _get_attributes(element) -> list[str]:
    """Get list of available attributes for an element."""
    err, attrs = AXUIElementCopyAttributeNames(element, None)
    if err == kAXErrorSuccess and attrs:
        return list(attrs)
    return []


def _element_to_dict(element, depth: int = 0, max_depth: int = 10) -> dict | None:
    """Convert AXUIElement to dictionary representation.

    Args:
        element: AXUIElement to convert.
        depth: Current recursion depth.
        max_depth: Maximum recursion depth.

    Returns:
        Dictionary representation of element and children.
    """
    if depth > max_depth:
        return None

    result = {}

    # Get standard attributes
    for attr in TREE_ATTRIBUTES:
        value = _get_attribute(element, attr)
        if value is not None:
            # Convert attribute name to simpler key
            key = attr.replace("AX", "").lower()

            # Handle special types
            if attr == "AXPosition":
                try:
                    result["x"] = int(value.x)
                    result["y"] = int(value.y)
                except (AttributeError, TypeError):
                    pass
            elif attr == "AXSize":
                try:
                    result["width"] = int(value.width)
                    result["height"] = int(value.height)
                except (AttributeError, TypeError):
                    pass
            elif isinstance(value, (str, int, float, bool)):
                result[key] = value
            elif hasattr(value, "__str__"):
                str_val = str(value)
                if str_val and len(str_val) < 500:
                    result[key] = str_val

    # Get children
    children_value = _get_attribute(element, "AXChildren")
    if children_value:
        children = []
        for child in children_value:
            child_dict = _element_to_dict(child, depth + 1, max_depth)
            if child_dict:
                children.append(child_dict)
        if children:
            result["children"] = children

    return result if result else None


def _find_app_pid(app_name: str) -> int:
    """Find PID for an application by name.

    Args:
        app_name: Application name (case-insensitive partial match).

    Returns:
        Process ID.

    Raises:
        AppNotFoundError: If app not found.
    """
    workspace = NSWorkspace.sharedWorkspace()
    name_lower = app_name.lower()

    for match_fn in [
        lambda n: n.lower() == name_lower,
        lambda n: n.lower().startswith(name_lower),
        lambda n: name_lower in n.lower(),
    ]:
        for app in workspace.runningApplications():
            if app.activationPolicy() != 0:
                continue
            n = app.localizedName()
            if n and match_fn(n):
                return app.processIdentifier()

    raise AppNotFoundError(f"Application not found: {app_name}")


def get_app_accessibility_tree(app_name: str, max_depth: int = 10) -> dict:
    """Get accessibility tree for an application.

    Args:
        app_name: Application name.
        max_depth: Maximum tree depth to traverse.

    Returns:
        Dictionary representation of accessibility tree.

    Raises:
        PermissionDeniedError: If accessibility permission not granted.
        AppNotFoundError: If app not found.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    tree = _element_to_dict(app_element, max_depth=max_depth)
    if not tree:
        raise GuiError(f"Could not read accessibility tree for: {app_name}")

    return tree


def find_elements(app_name: str, label: str, max_results: int = 10) -> list[dict]:
    """Find UI elements by label/title/value.

    Args:
        app_name: Application name.
        label: Text to search for (case-insensitive partial match).
        max_results: Maximum number of results.

    Returns:
        List of matching elements with their properties.

    Raises:
        PermissionDeniedError: If accessibility permission not granted.
        AppNotFoundError: If app not found.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    results = []
    label_lower = label.lower()

    def search(element, path: str = ""):
        if len(results) >= max_results:
            return

        # Check searchable attributes
        for attr in SEARCH_ATTRIBUTES:
            value = _get_attribute(element, attr)
            if value and isinstance(value, str) and label_lower in value.lower():
                elem_dict = {"path": path, "match_attr": attr.replace("AX", "").lower()}

                # Get common attributes
                for a in ["AXRole", "AXTitle", "AXValue", "AXDescription", "AXIdentifier"]:
                    v = _get_attribute(element, a)
                    if v is not None and isinstance(v, (str, int, float, bool)):
                        elem_dict[a.replace("AX", "").lower()] = v

                # Get position and size
                pos = _get_attribute(element, "AXPosition")
                size = _get_attribute(element, "AXSize")
                if pos:
                    try:
                        elem_dict["x"] = int(pos.x)
                        elem_dict["y"] = int(pos.y)
                    except (AttributeError, TypeError):
                        pass
                if size:
                    try:
                        elem_dict["width"] = int(size.width)
                        elem_dict["height"] = int(size.height)
                    except (AttributeError, TypeError):
                        pass

                results.append(elem_dict)
                break  # Found a match, don't duplicate

        # Search children
        children = _get_attribute(element, "AXChildren")
        if children:
            for i, child in enumerate(children):
                role = _get_attribute(child, "AXRole") or "unknown"
                child_path = f"{path}/{role}[{i}]" if path else f"{role}[{i}]"
                search(child, child_path)

    search(app_element)
    return results


def get_element_value(app_name: str, role: str | None = None, title: str | None = None) -> str | None:
    """Get the value of a specific UI element.

    Searches for element matching role and/or title, returns its AXValue.

    Args:
        app_name: Application name.
        role: Element role to match (e.g., "AXStaticText", "AXTextField").
        title: Element title to match.

    Returns:
        Element value if found, None otherwise.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    def search(element) -> str | None:
        elem_role = _get_attribute(element, "AXRole")
        elem_title = _get_attribute(element, "AXTitle")

        role_match = role is None or elem_role == role
        title_match = title is None or (elem_title and title.lower() in str(elem_title).lower())

        if role_match and title_match:
            value = _get_attribute(element, "AXValue")
            if value is not None:
                return str(value)
            # For static text, the value might be in AXValue or we return the title
            if elem_role == "AXStaticText" and elem_title:
                return str(elem_title)

        # Search children
        children = _get_attribute(element, "AXChildren")
        if children:
            for child in children:
                result = search(child)
                if result is not None:
                    return result

        return None

    return search(app_element)


def get_focused_element(app_name: str) -> dict | None:
    """Get the currently focused element in an application.

    Args:
        app_name: Application name.

    Returns:
        Dictionary with focused element properties, or None.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    focused = _get_attribute(app_element, "AXFocusedUIElement")
    if focused:
        return _element_to_dict(focused, max_depth=0)

    return None


def press_button(app_name: str, identifier: str) -> bool:
    """Press a button by its identifier or description.

    Args:
        app_name: Application name.
        identifier: Button identifier or description to match.

    Returns:
        True if button was found and pressed.

    Raises:
        PermissionDeniedError: If accessibility permission not granted.
        AppNotFoundError: If app not found.
        GuiError: If button not found.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    identifier_lower = identifier.lower()

    def find_and_press(element) -> bool:
        role = _get_attribute(element, "AXRole")

        # Check if this is a button
        if role == "AXButton":
            elem_id = _get_attribute(element, "AXIdentifier") or ""
            elem_desc = _get_attribute(element, "AXDescription") or ""
            elem_title = _get_attribute(element, "AXTitle") or ""

            # Match against identifier, description, or title
            if (identifier_lower in elem_id.lower() or
                identifier_lower in elem_desc.lower() or
                identifier_lower in elem_title.lower()):
                # Perform AXPress action
                err = AXUIElementPerformAction(element, "AXPress")
                return err == kAXErrorSuccess

        # Search children
        children = _get_attribute(element, "AXChildren")
        if children:
            for child in children:
                if find_and_press(child):
                    return True

        return False

    if find_and_press(app_element):
        return True

    raise GuiError(f"Button not found: {identifier}")


def get_button_position(app_name: str, identifier: str) -> tuple[int, int] | None:
    """Get screen position of a button by identifier.

    Args:
        app_name: Application name.
        identifier: Button identifier or description to match.

    Returns:
        (x, y) tuple of button center, or None if not found.
    """
    if not check_accessibility_permission():
        raise PermissionDeniedError(
            "Accessibility permission required.\n"
            "Grant access: System Settings > Privacy & Security > Accessibility > Terminal"
        )

    pid = _find_app_pid(app_name)
    app_element = AXUIElementCreateApplication(pid)

    identifier_lower = identifier.lower()

    def find_button(element) -> tuple[int, int] | None:
        role = _get_attribute(element, "AXRole")

        if role == "AXButton":
            elem_id = _get_attribute(element, "AXIdentifier") or ""
            elem_desc = _get_attribute(element, "AXDescription") or ""
            elem_title = _get_attribute(element, "AXTitle") or ""

            if (identifier_lower in elem_id.lower() or
                identifier_lower in elem_desc.lower() or
                identifier_lower in elem_title.lower()):
                pos = _get_attribute(element, "AXPosition")
                size = _get_attribute(element, "AXSize")
                if pos and size:
                    try:
                        x = int(pos.x) + int(size.width) // 2
                        y = int(pos.y) + int(size.height) // 2
                        return (x, y)
                    except (AttributeError, TypeError):
                        pass

        children = _get_attribute(element, "AXChildren")
        if children:
            for child in children:
                result = find_button(child)
                if result:
                    return result

        return None

    return find_button(app_element)
