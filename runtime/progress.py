# Shared kit file (blender-addon-kit). Do not edit here: change it in the kit
# and run sync_kit.py.
"""Progress feedback for operators that loop over many objects."""


def with_progress(context, items, minimum=2):
    """Yield `items` one by one, showing Blender's progress indicator.

    The percentage advances after each item is finished, so `continue`
    inside the loop still counts. The indicator is skipped for fewer than
    `minimum` items, where it would only flicker. It is always cleared,
    even when the loop stops early or raises.
    """
    items = list(items)

    if len(items) < max(minimum, 1):
        yield from items
        return

    manager = context.window_manager
    manager.progress_begin(0, len(items))

    try:
        for index, item in enumerate(items, start=1):
            yield item
            manager.progress_update(index)
    finally:
        manager.progress_end()
