from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Returns the value for the given key from the dictionary."""
    return dictionary.get(key)



@register.filter
def split_po_number(value):
    """Split the PO number and return the first part before the hyphen."""
    return value.split(':')[0]

@register.filter
def dict_get(dictionary, key):
    """Returns the value for the given key from the dictionary."""
    return dictionary.get(key, [])


@register.filter
def extract_emails(email_data_list):
    return ', '.join([email_data['email'] for email_data in email_data_list])

@register.filter
def sum_quantity(inventory_list):
    """Sum the total_quantity of all items in the inventory list"""
    if not inventory_list:
        return 0
    return sum(item.get('total_quantity', 0) for item in inventory_list)


@register.filter
def sap_mapped_count(inventory):
    """Count SAP mapped products"""
    if not inventory:
        return 0
    return sum(1 for item in inventory if item.get('is_sap_mapped', False))

@register.filter
def nddb_mapped_count(inventory):
    """Count NDDB mapped products"""
    if not inventory:
        return 0
    return sum(1 for item in inventory if item.get('is_nddb_mapped', False))

@register.filter
def is_dummy_po(po_number):
    """Check if PO number is dummy (exactly 10 zeros) - Business Rule"""
    return po_number == "0000000000"  # Exact match, no trimming or casting

@register.filter
def should_display_po(po_number):
    """Inverse of is_dummy_po for more readable templates"""
    return po_number != "0000000000"
@register.filter
def truncate_filename(value, max_length=18):
    """
    Truncate a filename safely and append '...' if needed.
    Example:
    sap_reconciliation_february.xlsx -> sap_reconciliation...
    """
    if not value:
        return ""

    try:
        max_length = int(max_length)
    except (TypeError, ValueError):
        max_length = 18

    if len(value) <= max_length:
        return value

    return value[:max_length] + "..."


@register.filter(name='abs_value')
def abs_value(value):
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return 0

    

@register.filter
def prefix_sign(value):
    """Add + sign for positive numbers"""
    if value > 0:
        return f"+{value}"
    return str(value)

# In your custom_filters.py
@register.filter
def calculate_diff(advance, sap):
    return advance - sap

@register.filter
def count_user_notifications(items, user_location):
    """Count notifications for current user's location."""
    if not items:
        return 0
    count = 0
    for notification in items:
        if str(notification.from_user.location) == str(user_location):
            count += 1
    return count

@register.filter
def sum_notification_counts(grouped_notifications, user_location):
    """Sum all notification counts across all routes for a user's location."""
    if not grouped_notifications:
        return 0
    total = 0
    for items in grouped_notifications.values():
        for notification in items:
            if str(notification.from_user.location) == str(user_location):
                total += 1
    return total