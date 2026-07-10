"""
Location-shared inventory.

Stock belongs to the LOCATION (MCC/BMC), not to the individual user account:
several users can share one location (the admin's location list), and any of
them may receive (GRN), dispatch (STN), sell or adjust the SAME stock — e.g.
user A does a GRN at Bahraich and user B (also Bahraich) transfers that stock
out.

Physically the quantities live on ONE canonical Inventory row per
(location, product): the row owned by the location's canonical user (the
oldest account at that location). location_inventory() lazily consolidates any
stock that older per-user code left on other users' rows into the canonical
row; the sibling rows are kept at zero (never deleted) so their
InventoryHistory audit trail survives, and location-grouped reports — which
aggregate by mcc_bmc_user__location — are unaffected.
"""

from django.db.models import Sum

from .models import CustomUser, Inventory

# The buckets a row carries; all of them move to the canonical row.
_BUCKETS = ("quantity", "expired_quantity", "damaged_quantity", "scrap_quantity")


def location_owner(location):
    """The canonical user whose account holds a location's shared inventory."""
    location = (location or "").strip()
    if not location:
        return None
    return (CustomUser.objects.filter(location__iexact=location)
            .order_by("id").first())


def location_inventory(user_or_location, product, create=True, lock=False):
    """THE shared Inventory row for (location, product).

    Accepts a user (its .location is used) or a location name. Any stock still
    parked on other users of the location is folded into the canonical row
    before it is returned. With create=False, returns None when the location
    holds no row for the product at all. With lock=True the returned row is
    select_for_update()-locked (call inside a transaction).
    """
    user = user_or_location if hasattr(user_or_location, "location") else None
    location = ((user.location if user else user_or_location) or "").strip()
    owner = location_owner(location) or user
    if owner is None or product is None:
        return None

    inv = Inventory.objects.filter(mcc_bmc_user=owner, product=product).first()
    if inv is None:
        stray_exists = Inventory.objects.filter(
            mcc_bmc_user__location__iexact=location, product=product
        ).exists()
        if not create and not stray_exists:
            return None
        inv, _ = Inventory.objects.get_or_create(
            mcc_bmc_user=owner, product=product, defaults={"quantity": 0})

    if lock:
        inv = Inventory.objects.select_for_update().get(pk=inv.pk)

    # Consolidate: fold every sibling row of this location into the canonical one.
    siblings = (Inventory.objects
                .filter(mcc_bmc_user__location__iexact=location, product=product)
                .exclude(pk=inv.pk))
    totals = siblings.aggregate(**{b: Sum(b) for b in _BUCKETS})
    if any(totals[b] for b in _BUCKETS):
        siblings.update(**{b: 0 for b in _BUCKETS})
        for b in _BUCKETS:
            setattr(inv, b, getattr(inv, b) + (totals[b] or 0))
        inv.save()

    return inv
