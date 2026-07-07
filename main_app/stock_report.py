"""
Sale & Stock Report (monthly-cycle stock statement) engine.

Per cycle, per MCC/BMC x Product:

    Closing = Opening + Received + StockTransfer(net) - MPP Sale - Damage - Expire

Data sources:
  * Opening        -> previous cycle's finalized Closing, else a current-inventory snapshot
  * Received (NDS) -> GRN from NDS / other company / party (action=GRN) within the range
  * Received (MCC) -> incoming STN receipts from another MCC/BMC (TRANSFER_IN) within the range
  * StockTransfer  -> outgoing STN transfers (TRANSFER_OUT, negative) within the range
  * MPP Sale       -> aggregated from an uploaded SAP sale export (sum of Order Quantity)
  * Damage / Expire-> filled by the admin (download -> fill -> re-upload)

This module is intentionally self-contained; the only cross-module dependency is the
SAP->ProductMappingGroup resolver in views, imported lazily to avoid an import cycle.
"""

import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.db.models import Sum
from django.utils import timezone

from .models import (
    BMCOrMCC,
    Cycle,
    Inventory,
    InventoryHistory,
    MPPWithCode,
    Product,
    ProductMapping,
    StockStatement,
    StockStatementEntry,
    MPPSaleAggregate,
)

REPORT_COLUMNS = [
    "Sr.No", "MCC/BMC Name", "Product Name", "Opp.Balance",
    "Received Product NDS/Other Company", "Received Product MCC/BMC",
    "Stock Transfer Other MCC/BMC", "MPP Sale", "Damage Product",
    "Expire Product", "Closing Stock", "Remark's",
]
# 0-based column indexes within a report row (matches REPORT_COLUMNS order).
COL_PRODUCT = 2
COL_OPENING = 3
COL_RECEIVED = 4        # Received Product NDS/Other Company (GRN)
COL_RECEIVED_MCC = 5    # Received Product MCC/BMC (transfer in)
COL_TRANSFER = 6
COL_MPP_SALE = 7
COL_DAMAGE = 8
COL_EXPIRE = 9
COL_CLOSING = 10


# ---------------------------------------------------------------------------------------
# Mapping helpers (SAP export -> internal master data)
# ---------------------------------------------------------------------------------------
def _strip_leading_zeros(value):
    s = str(value or "").strip()
    return s.lstrip("0") or ("0" if s else "")


def resolve_product(material_code, material_desc, cache):
    """SAP material (code + description) -> internal Product, memoised in `cache`."""
    key = (str(material_code or "").strip(), str(material_desc or "").strip().upper())
    if key in cache:
        return cache[key]

    product = None
    # 1) Reuse the existing SAP -> ProductMappingGroup resolver, then group -> Product.
    try:
        from .views import find_product_group_for_sap_material
        group = find_product_group_for_sap_material(key[0], material_desc or "")
    except Exception:
        group = None
    if group is not None:
        indent = group.mappings.filter(
            product_mapping__system="INDENT_EASY"
        ).select_related("product_mapping").first()
        candidate_names = []
        if indent and indent.product_mapping:
            candidate_names.append(indent.product_mapping.product_name)
        candidate_names.append(group.name)
        for name in candidate_names:
            if not name:
                continue
            product = Product.objects.filter(name__iexact=name).first()
            if product:
                break

    # 2) Direct fallbacks against Product itself.
    if product is None and key[0]:
        product = Product.objects.filter(product_code=key[0]).first()
    if product is None and material_desc:
        product = Product.objects.filter(name__iexact=material_desc.strip()).first()

    cache[key] = product
    return product


def resolve_bmc(plant, mcc_name, cache):
    """SAP (Plant code, Mcc Name) -> BMCOrMCC, memoised in `cache`."""
    key = (str(plant or "").strip(), str(mcc_name or "").strip().upper())
    if key in cache:
        return cache[key]
    bmc = None
    if key[0]:
        bmc = BMCOrMCC.objects.filter(plant=key[0]).first()
    if bmc is None and key[1]:
        bmc = (BMCOrMCC.objects.filter(name__iexact=key[1]).first()
               or BMCOrMCC.objects.filter(name__icontains=key[1]).first())
    cache[key] = bmc
    return bmc


def resolve_mpp(mpp_code, mpp_name, cache):
    key = (str(mpp_code or "").strip(), str(mpp_name or "").strip().upper())
    if key in cache:
        return cache[key]
    mpp = None
    stripped = _strip_leading_zeros(key[0])
    if stripped:
        mpp = (MPPWithCode.objects.filter(mpp_transaction_code=stripped).first()
               or MPPWithCode.objects.filter(mpp_transaction_code=key[0]).first())
    if mpp is None and key[1]:
        mpp = MPPWithCode.objects.filter(name_with_code__icontains=key[1]).first()
    cache[key] = mpp
    return mpp


def _norm_product(name):
    """Loose product-name key so 'Calcium (01_Ltr)' matches 'Calcium 1 Ltr' etc."""
    s = str(name or "").strip().lower()
    s = re.sub(r"[()_/\-.,]", " ", s)       # punctuation -> space
    s = re.sub(r"\b0+(\d)", r"\1", s)        # 01 -> 1, 05 -> 5
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_product_norm_cache():
    """Map loose-normalised product name -> Product (first wins) for pattern matching."""
    cache = {}
    for p in Product.objects.all().only("id", "name"):
        cache.setdefault(_norm_product(p.name), p)
    return cache


def resolve_product_by_name(name, norm_cache, create=False):
    """Match an uploaded product name to a Product: exact (case-insensitive) first, then a
    loose pattern match. If ``create`` and nothing matches, create a Product with just the
    name (all other fields left blank / None)."""
    raw = str(name or "").strip()
    if not raw:
        return None
    p = Product.objects.filter(name__iexact=raw).first()
    if p:
        return p
    key = _norm_product(raw)
    if key and key in norm_cache:
        return norm_cache[key]
    if create:
        p = Product.objects.create(name=raw)   # unique name; other fields blank/default/None
        if key:
            norm_cache[key] = p
        return p
    return None


# ---------------------------------------------------------------------------------------
# Cycle helpers
# ---------------------------------------------------------------------------------------
_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]


def get_previous_cycle(cycle):
    """The cycle immediately before `cycle` (same month; else last cycle of prev month)."""
    mc = cycle.monthly_cycle
    prev = Cycle.objects.filter(
        monthly_cycle=mc, cycle_number=cycle.cycle_number - 1
    ).first()
    if prev:
        return prev
    if cycle.cycle_number <= 1 and mc is not None:
        month_name = (mc.month or "").strip().lower()
        try:
            idx = _MONTHS.index(month_name)
        except ValueError:
            return None
        if idx == 0:
            prev_month, prev_year = "December", (mc.year or 0) - 1
        else:
            prev_month, prev_year = _MONTHS[idx - 1].capitalize(), mc.year
        return (Cycle.objects.filter(
            monthly_cycle__month__iexact=prev_month,
            monthly_cycle__year=prev_year,
        ).order_by("-cycle_number").first())
    return None


# ---------------------------------------------------------------------------------------
# Step 1: generate the statement (Opening / Received / Stock Transfer)
# ---------------------------------------------------------------------------------------
def generate_statement(cycle, user=None):
    """Create/refresh a StockStatement for `cycle`. Preserves any already-entered
    MPP Sale / Damage / Expire and just refreshes Opening / Received / Stock Transfer."""
    statement, _ = StockStatement.objects.get_or_create(cycle=cycle)

    # location string -> BMCOrMCC (Inventory is keyed by user.location, which equals BMCOrMCC.name)
    bmc_by_name = {b.name.strip().upper(): b for b in BMCOrMCC.objects.all()}

    def bmc_for_location(loc):
        return bmc_by_name.get(str(loc or "").strip().upper())

    # ---- Opening: previous cycle finalized closing, else current inventory snapshot ----
    opening = defaultdict(int)   # (bmc_id, product_id) -> qty
    prev = get_previous_cycle(cycle)
    prev_stmt = getattr(prev, "stock_statement", None) if prev else None
    if prev_stmt is not None:
        for e in prev_stmt.entries.all():
            opening[(e.bmc_or_mcc_id, e.product_id)] = e.closing_balance
    else:
        snap = (Inventory.objects
                .values("mcc_bmc_user__location", "product_id")
                .annotate(q=Sum("quantity")))
        for row in snap:
            bmc = bmc_for_location(row["mcc_bmc_user__location"])
            if bmc and row["product_id"] and row["q"]:
                opening[(bmc.id, row["product_id"])] += int(row["q"] or 0)

    # ---- Received (split) and Stock Transfer from InventoryHistory in range ----
    # received      = GRN from NDS / other company / party (action=GRN)
    # received_mcc  = incoming STN transfer received from another MCC/BMC (TRANSFER_IN, +ve)
    # transfer      = only OUTGOING transfers to other MCC/BMC (TRANSFER_OUT, negative)
    received = defaultdict(int)
    received_mcc = defaultdict(int)
    transfer = defaultdict(int)
    hist = (InventoryHistory.objects
            .filter(created_at__date__range=[cycle.start_date, cycle.end_date])
            .values("inventory__mcc_bmc_user__location", "inventory__product_id", "action")
            .annotate(q=Sum("quantity_change")))
    for row in hist:
        bmc = bmc_for_location(row["inventory__mcc_bmc_user__location"])
        pid = row["inventory__product_id"]
        if not bmc or not pid:
            continue
        k = (bmc.id, pid)
        action = row["action"]
        qty = int(row["q"] or 0)
        if action == "GRN":
            received[k] += qty
        elif action == "TRANSFER_IN":
            received_mcc[k] += qty
        elif action == "TRANSFER_OUT":
            transfer[k] += qty   # -ve; only stock sent out to other MCC/BMC

    # ---- Upsert entries: FULL product grid (preserve sale/damage/expire) ----
    combos = set(opening) | set(received) | set(received_mcc) | set(transfer)
    existing = {(e.bmc_or_mcc_id, e.product_id): e for e in statement.entries.all()}
    combos |= set(existing.keys())
    # Every location that appears in the cycle shows EVERY product that appears in the cycle
    # (zero rows included), so each sheet matches the standard master layout.
    present_bmcs = {b for (b, _p) in combos}
    present_products = {p for (_b, p) in combos}
    if present_bmcs and present_products:
        combos = {(b, p) for b in present_bmcs for p in present_products}

    to_create, to_update = [], []
    for (bmc_id, pid) in combos:
        o = opening.get((bmc_id, pid), 0)
        r = received.get((bmc_id, pid), 0)
        rm = received_mcc.get((bmc_id, pid), 0)
        t = transfer.get((bmc_id, pid), 0)
        entry = existing.get((bmc_id, pid))
        if entry is None:
            entry = StockStatementEntry(statement=statement, bmc_or_mcc_id=bmc_id, product_id=pid,
                                        opening_balance=o, received=r, received_mcc=rm, stock_transfer=t)
            entry.closing_balance = entry.compute_closing()
            to_create.append(entry)
        else:
            entry.opening_balance = o; entry.received = r
            entry.received_mcc = rm; entry.stock_transfer = t
            entry.closing_balance = entry.compute_closing()   # preserves sale/damage/expire
            to_update.append(entry)
    if to_create:
        StockStatementEntry.objects.bulk_create(to_create, batch_size=500)
    if to_update:
        StockStatementEntry.objects.bulk_update(
            to_update, ["opening_balance", "received", "received_mcc", "stock_transfer", "closing_balance"],
            batch_size=500)

    if statement.status == StockStatement.STATUS_FINALIZED:
        statement.status = StockStatement.STATUS_SALE_UPLOADED
    statement.generated_by = user or statement.generated_by
    statement.generated_at = timezone.now()
    statement.is_manual_override = False   # recomputed from source -> drops any manual override
    statement.save()
    return statement


def rechain_month(monthly_cycle):
    """Re-link every cycle of a month so each cycle's Opening = the previous cycle's Closing
    (per BMC/MCC + product), recomputing closings forward. The first cycle's Opening is left
    as-is (inventory snapshot / manual). Called whenever a cycle's numbers change so later
    cycles auto-fill from the corrected/updated closing.
    """
    if monthly_cycle is None:
        return
    stmts = list(StockStatement.objects
                 .filter(cycle__monthly_cycle=monthly_cycle)
                 .select_related("cycle")
                 .order_by("cycle__cycle_number"))
    for i in range(1, len(stmts)):
        prev, cur = stmts[i - 1], stmts[i]
        closings = {(e.bmc_or_mcc_id, e.product_id): e.closing_balance for e in prev.entries.all()}
        to_update = []
        for e in cur.entries.all():
            new_open = closings.get((e.bmc_or_mcc_id, e.product_id), 0)
            if e.opening_balance != new_open:
                e.opening_balance = new_open
                e.closing_balance = e.compute_closing()
                to_update.append(e)
        if to_update:
            StockStatementEntry.objects.bulk_update(
                to_update, ["opening_balance", "closing_balance"], batch_size=500)


# ---------------------------------------------------------------------------------------
# Step 2: ingest the SAP sale export -> MPP Sale
# ---------------------------------------------------------------------------------------
def _norm_header(v):
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def _materialize(ws):
    """Read a worksheet's rows once as a list of tuples.

    IMPORTANT: openpyxl read-only worksheets stream from the top, so random
    ``ws.cell(r, c)`` access is O(n) per call -> O(n**2) over a loop and hangs on
    files with a few thousand rows. Reading everything once with ``iter_rows`` keeps
    ingestion O(n). Access a cell as ``row[idx - 1]`` (1-based column index).
    """
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


def _cell(row, idx):
    """1-based column access into a materialized row tuple (None if out of range)."""
    if not idx:
        return None
    i = idx - 1
    return row[i] if 0 <= i < len(row) else None


def _find_columns(rows):
    """Locate the header row (containing 'Plant') and map our fields to column indexes.

    `rows` is a list of row tuples (from :func:`_materialize`). Returns the 0-based
    header-row index into `rows` and the field->column-index (1-based) map.
    """
    header_row = None
    headers = None
    for idx, row in enumerate(rows[:15]):
        values = [_norm_header(v) for v in row]
        if "plant" in values:
            header_row = idx
            headers = values
            break
    if header_row is None:
        raise ValueError("Could not find a header row containing 'Plant' in the sale file.")

    def col(*needles):
        for idx, h in enumerate(headers, start=1):
            if all(n in h for n in needles):
                return idx
        return None

    cols = {
        "plant": col("plant") if "plant" in headers else col("plant"),
        "mcc": col("mcc", "name"),
        "mpp_name": col("mpp", "name"),
        "mpp_code": col("mpp", "code"),
        "date": col("document", "date"),
        "material_code": col("material") if col("material") and not col("material", "desc") else col("material"),
        "material_desc": col("material", "desc") or col("description"),
        "qty": col("order", "quantity") or col("quantity"),
        "net": col("net", "value"),
    }
    # 'Material' (code) vs 'Material Description': pick the plain 'material' column for code.
    for idx, h in enumerate(headers, start=1):
        if h == "material":
            cols["material_code"] = idx
    return header_row, cols


def ingest_sale(statement, file_obj, filename=""):
    """Parse an uploaded SAP sale export and fill MPP Sale per (BMC/MCC, Product)."""
    wb = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    ws = wb.active
    rows = _materialize(ws)
    wb.close()
    header_row, cols = _find_columns(rows)

    prod_cache, bmc_cache, mpp_cache = {}, {}, {}
    # aggregation keys
    per_entry = defaultdict(int)                 # (bmc_id, product_id) -> qty
    per_mpp = {}                                 # (mpp_code, material_code) -> dict
    total = matched = unmatched = 0

    for r in range(header_row + 1, len(rows)):
        row = rows[r]
        plant = _cell(row, cols["plant"])
        mcc_name = _cell(row, cols["mcc"])
        mpp_code = _cell(row, cols["mpp_code"])
        mpp_name = _cell(row, cols["mpp_name"])
        material_code = _cell(row, cols["material_code"])
        material_desc = _cell(row, cols["material_desc"])
        qty_raw = _cell(row, cols["qty"])
        net_raw = _cell(row, cols["net"])
        if plant is None and mcc_name is None and material_code is None and qty_raw is None:
            continue   # blank row
        total += 1

        try:
            qty = int(round(float(qty_raw))) if qty_raw not in (None, "") else 0
        except (TypeError, ValueError):
            qty = 0
        try:
            net_value = Decimal(str(net_raw)) if net_raw not in (None, "") else Decimal("0")
        except (InvalidOperation, TypeError):
            net_value = Decimal("0")

        product = resolve_product(material_code, material_desc, prod_cache)
        bmc = resolve_bmc(plant, mcc_name, bmc_cache)
        mpp = resolve_mpp(mpp_code, mpp_name, mpp_cache)
        is_matched = bool(product and bmc)
        if is_matched:
            matched += 1
            per_entry[(bmc.id, product.id)] += qty
        else:
            unmatched += 1

        agg_key = (str(mpp_code or "").strip(), str(material_code or "").strip())
        row = per_mpp.get(agg_key)
        if row is None:
            per_mpp[agg_key] = {
                "bmc": bmc, "mpp": mpp, "product": product,
                "sap_plant": str(plant or "").strip(), "sap_mcc_name": str(mcc_name or "").strip(),
                "sap_mpp_code": str(mpp_code or "").strip(), "sap_mpp_name": str(mpp_name or "").strip(),
                "sap_material_code": str(material_code or "").strip(),
                "sap_material_desc": str(material_desc or "").strip(),
                "qty": qty, "net_value": net_value, "matched": is_matched,
            }
        else:
            row["qty"] += qty
            row["net_value"] += net_value

    # ---- persist MPP-level aggregation (rebuild) ----
    statement.mpp_sales.all().delete()
    bulk = []
    for row in per_mpp.values():
        bulk.append(MPPSaleAggregate(
            statement=statement,
            bmc_or_mcc=row["bmc"], mpp=row["mpp"], product=row["product"],
            sap_plant=row["sap_plant"][:50], sap_mcc_name=row["sap_mcc_name"][:150],
            sap_mpp_code=row["sap_mpp_code"][:50], sap_mpp_name=row["sap_mpp_name"][:150],
            sap_material_code=row["sap_material_code"][:50],
            sap_material_desc=row["sap_material_desc"][:255],
            quantity=row["qty"], net_value=row["net_value"], matched=row["matched"],
        ))
    MPPSaleAggregate.objects.bulk_create(bulk, batch_size=500)

    # ---- apply MPP Sale onto entries (reset then set; create combos as needed) ----
    statement.entries.exclude(mpp_sale=0).update(mpp_sale=0)   # clear stale sale values
    for (bmc_id, pid), qty in per_entry.items():
        entry, _ = StockStatementEntry.objects.get_or_create(
            statement=statement, bmc_or_mcc_id=bmc_id, product_id=pid,
        )
        entry.mpp_sale = qty
        entry.save()
    # recompute closing for any entry whose sale was reset to 0
    for entry in statement.entries.all():
        new_closing = entry.compute_closing()
        if entry.closing_balance != new_closing:
            entry.closing_balance = new_closing
            entry.save(update_fields=["closing_balance", "updated_at"])

    statement.sale_file_name = filename or getattr(file_obj, "name", "")
    statement.sale_rows_total = total
    statement.sale_rows_matched = matched
    statement.sale_rows_unmatched = unmatched
    statement.sale_uploaded_at = timezone.now()
    if statement.status == StockStatement.STATUS_DRAFT:
        statement.status = StockStatement.STATUS_SALE_UPLOADED
    statement.save()

    return {
        "total": total, "matched": matched, "unmatched": unmatched,
        "mpp_rows": len(per_mpp), "entries_with_sale": len(per_entry),
    }


# ---------------------------------------------------------------------------------------
# Step 3: build the downloadable report (one sheet per MCC/BMC, in the required format)
# ---------------------------------------------------------------------------------------
_THIN = Side(style="thin", color="B0B0B0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")


def _safe_sheet_title(name, used):
    title = re.sub(r"[\\/*?:\[\]]", "-", str(name or "Sheet")).strip()[:31] or "Sheet"
    base, i = title, 1
    while title in used:
        suffix = f"_{i}"
        title = base[:31 - len(suffix)] + suffix
        i += 1
    used.add(title)
    return title


def build_workbook(statement, only_bmc=None, include_summary=False):
    """Build the formatted report workbook (one sheet per MCC/BMC).

    Pass ``only_bmc`` (a BMCOrMCC instance) to restrict the workbook to a single
    location's sheet — used by the location-level download.
    Pass ``include_summary=True`` (admin full download) to append the company-wide
    'SMPCL SUMMERY' sheet: a month-wise rollup across all locations (opening from the
    first cycle, closing from the last cycle, flows summed across the month's cycles).
    """
    cycle = statement.cycle
    month_display = ""
    if cycle.monthly_cycle:
        month_display = f"{cycle.monthly_cycle.month}-{cycle.monthly_cycle.year}"
    cycle_range = ""
    if cycle.start_date and cycle.end_date:
        cycle_range = f"{cycle.start_date.strftime('%d')}-{cycle.end_date.strftime('%d %b %Y')}"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used_titles = set()

    entries = (statement.entries
               .select_related("bmc_or_mcc", "product")
               .order_by("bmc_or_mcc__name", "product__name"))
    if only_bmc is not None:
        entries = entries.filter(bmc_or_mcc=only_bmc)
    by_bmc = defaultdict(list)
    for e in entries:
        by_bmc[e.bmc_or_mcc].append(e)

    if not by_bmc:
        ws = wb.create_sheet(_safe_sheet_title("No Data", used_titles))
        ws["A1"] = "No stock statement entries. Generate the statement first."
        bio = io.BytesIO(); wb.save(bio); bio.seek(0)
        return bio

    for bmc in sorted(by_bmc.keys(), key=lambda b: b.name):
        ws = wb.create_sheet(_safe_sheet_title(bmc.name, used_titles))
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(REPORT_COLUMNS))
        ws.cell(1, 1, "Shwetdhara Milk Producer Company Limited").font = Font(bold=True, size=13)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(REPORT_COLUMNS))
        ws.cell(2, 1, f"Input Sale & Stock Report  Month {month_display}").font = Font(bold=True)
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(REPORT_COLUMNS))
        ws.cell(3, 1, f"{bmc.name}  |  Sale Report Cycle {cycle_range}").font = Font(bold=True)

        # header row (row 4)
        for c, title in enumerate(REPORT_COLUMNS, start=1):
            cell = ws.cell(4, c, title)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = _BORDER

        totals = defaultdict(int)
        row_ptr = 5
        for i, e in enumerate(by_bmc[bmc], start=1):
            values = [
                i, bmc.name, e.product.name, e.opening_balance, e.received, e.received_mcc,
                e.stock_transfer, e.mpp_sale, e.damage, e.expire, e.closing_balance, e.remark,
            ]
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row_ptr, c, v)
                cell.border = _BORDER
                if c >= 4:
                    cell.alignment = Alignment(horizontal="center")
            for col in (COL_OPENING, COL_RECEIVED, COL_RECEIVED_MCC, COL_TRANSFER, COL_MPP_SALE,
                        COL_DAMAGE, COL_EXPIRE, COL_CLOSING):
                totals[col] += values[col] or 0
            row_ptr += 1

        # total row
        tcell = ws.cell(row_ptr, 1, "Total")
        tcell.font = Font(bold=True)
        for c in range(1, len(REPORT_COLUMNS) + 1):
            cell = ws.cell(row_ptr, c)
            cell.border = _BORDER
            cell.fill = _TOTAL_FILL
            cell.font = Font(bold=True)
            col0 = c - 1
            if col0 in totals:
                cell.value = totals[col0]
                cell.alignment = Alignment(horizontal="center")

        widths = [7, 22, 34, 12, 18, 16, 16, 11, 13, 13, 13, 16]
        for c, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(c)].width = w
        ws.freeze_panes = "A5"

    if include_summary and only_bmc is None:
        build_smpcl_summary(wb, statement, used_titles)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def build_smpcl_summary(wb, statement, used_titles):
    """Append the company-wide 'SMPCL SUMMERY' sheet — one row per product, aggregated
    across ALL locations for the whole month:

        * Opp.Balance -> opening of the FIRST cycle of the month (summed over locations)
        * Closing     -> closing of the LAST cycle of the month (summed over locations)
        * Received / Transfer / MPP Sale / Damage / Expire -> summed across every cycle
    """
    cycle = statement.cycle
    mc = cycle.monthly_cycle
    stmts = list(StockStatement.objects
                 .filter(cycle__monthly_cycle=mc)
                 .select_related("cycle")
                 .order_by("cycle__cycle_number")) if mc else [statement]
    if not stmts:
        stmts = [statement]
    first_stmt, last_stmt = stmts[0], stmts[-1]
    stmt_ids = [s.id for s in stmts]

    agg = {}   # product_id -> aggregated dict

    def _row(pid):
        return agg.setdefault(pid, {"opening": 0, "recv": 0, "recv_mcc": 0, "xfer": 0,
                                    "sale": 0, "damage": 0, "expire": 0, "closing": 0})

    # flows summed across every cycle of the month
    for r in (StockStatementEntry.objects.filter(statement_id__in=stmt_ids)
              .values("product_id")
              .annotate(recv=Sum("received"), recv_mcc=Sum("received_mcc"),
                        xfer=Sum("stock_transfer"), sale=Sum("mpp_sale"),
                        damage=Sum("damage"), expire=Sum("expire"))):
        d = _row(r["product_id"])
        d["recv"] = r["recv"] or 0; d["recv_mcc"] = r["recv_mcc"] or 0; d["xfer"] = r["xfer"] or 0
        d["sale"] = r["sale"] or 0; d["damage"] = r["damage"] or 0; d["expire"] = r["expire"] or 0
    # opening from the first cycle, closing from the last cycle
    for r in (StockStatementEntry.objects.filter(statement=first_stmt)
              .values("product_id").annotate(o=Sum("opening_balance"))):
        _row(r["product_id"])["opening"] = r["o"] or 0
    for r in (StockStatementEntry.objects.filter(statement=last_stmt)
              .values("product_id").annotate(c=Sum("closing_balance"))):
        _row(r["product_id"])["closing"] = r["c"] or 0

    products = {p.id: p for p in Product.objects.filter(id__in=agg.keys())}
    ordered = sorted(agg.items(), key=lambda kv: (products[kv[0]].name.lower() if kv[0] in products else ""))

    ncol = len(REPORT_COLUMNS)
    month_display = f"{mc.month}-{mc.year}" if mc else ""
    ws = wb.create_sheet(_safe_sheet_title("SMPCL SUMMERY", used_titles))
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.cell(1, 1, "Shwetdhara Milk Producer Company Limited").font = Font(bold=True, size=13)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    ws.cell(2, 1, f"Input Sale & Stock Report Summery  Month {month_display}").font = Font(bold=True)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncol)
    ws.cell(3, 1, "SMPCL STORE  |  All MCC/BMC locations").font = Font(bold=True)

    for c, title in enumerate(REPORT_COLUMNS, start=1):
        cell = ws.cell(4, c, title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER

    totals = defaultdict(int)
    row_ptr = 5
    for i, (pid, d) in enumerate(ordered, start=1):
        p = products.get(pid)
        values = [
            i, "SMPCL STORE", (p.name if p else str(pid)), d["opening"], d["recv"], d["recv_mcc"],
            d["xfer"], d["sale"], d["damage"], d["expire"], d["closing"], "",
        ]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row_ptr, c, v)
            cell.border = _BORDER
            if c >= 4:
                cell.alignment = Alignment(horizontal="center")
        for col in (COL_OPENING, COL_RECEIVED, COL_RECEIVED_MCC, COL_TRANSFER, COL_MPP_SALE,
                    COL_DAMAGE, COL_EXPIRE, COL_CLOSING):
            totals[col] += values[col] or 0
        row_ptr += 1

    tcell = ws.cell(row_ptr, 1, "Total")
    tcell.font = Font(bold=True)
    for c in range(1, ncol + 1):
        cell = ws.cell(row_ptr, c)
        cell.border = _BORDER
        cell.fill = _TOTAL_FILL
        cell.font = Font(bold=True)
        col0 = c - 1
        if col0 in totals:
            cell.value = totals[col0]
            cell.alignment = Alignment(horizontal="center")

    widths = [7, 16, 34, 12, 18, 16, 16, 11, 13, 13, 13, 16]
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A5"
    return ws


# ---------------------------------------------------------------------------------------
# Step 4: ingest the filled report (Damage / Expire) -> finalize + carry forward
# ---------------------------------------------------------------------------------------
def _to_int(v):
    try:
        return int(round(float(v))) if v not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def ingest_filled_report(statement, file_obj):
    """Read Damage/Expire back from the filled workbook, recompute Closing, finalize."""
    wb = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    bmc_by_name = {b.name.strip().upper(): b for b in BMCOrMCC.objects.all()}
    prod_cache = build_product_norm_cache()

    updated = 0
    unmatched_rows = 0
    for ws in wb.worksheets:
        rows = _materialize(ws)   # read once; random cell access on read-only is O(n**2)
        # BMC/MCC for this sheet: prefer sheet title, else the MCC/BMC Name column.
        sheet_bmc = bmc_by_name.get(ws.title.strip().upper())
        # find header row (row containing 'Product Name')
        header_row = None
        for idx, row in enumerate(rows[:12]):
            if "product name" in [_norm_header(v) for v in row]:
                header_row = idx
                break
        if header_row is None:
            continue

        for r in range(header_row + 1, len(rows)):
            row = rows[r]
            name_cell = _cell(row, COL_PRODUCT + 1)
            first_cell = _cell(row, 1)
            if first_cell and str(first_cell).strip().lower() == "total":
                continue
            if not name_cell:
                continue
            bmc = sheet_bmc or bmc_by_name.get(str(_cell(row, 2) or "").strip().upper())
            if not bmc:
                unmatched_rows += 1
                continue
            product = resolve_product_by_name(name_cell, prod_cache, create=False)
            if not product:
                unmatched_rows += 1
                continue
            entry = statement.entries.filter(bmc_or_mcc=bmc, product=product).first()
            if not entry:
                unmatched_rows += 1
                continue
            entry.damage = _to_int(_cell(row, COL_DAMAGE + 1))
            entry.expire = _to_int(_cell(row, COL_EXPIRE + 1))
            remark = _cell(row, len(REPORT_COLUMNS))
            if remark:
                entry.remark = str(remark)[:255]
            entry.save()   # recomputes closing
            updated += 1

    statement.status = StockStatement.STATUS_FINALIZED
    statement.finalized_at = timezone.now()
    statement.save()
    rechain_month(statement.cycle.monthly_cycle)   # carry closings forward to later cycles
    return {"updated": updated, "unmatched_rows": unmatched_rows}


def ingest_full_report(statement, file_obj):
    """Admin correction upload: read EVERY editable column back from an uploaded report
    workbook and overwrite the matching entries (Opening, both Received columns, Stock
    Transfer, MPP Sale, Damage, Expire). Closing is recomputed from those. Sets the
    statement's manual-override flag so the values are not auto-recomputed from inventory.

    The 'SMPCL SUMMERY' sheet is ignored (it is a rollup, not a per-location source).
    Matching is by sheet title -> BMC/MCC and Product Name -> Product.
    """
    wb = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    bmc_by_name = {b.name.strip().upper(): b for b in BMCOrMCC.objects.all()}
    prod_cache = build_product_norm_cache()   # for pattern-matching product names

    updated = 0
    created = 0
    unmatched_rows = 0
    for ws in wb.worksheets:
        if ws.title.strip().upper().startswith("SMPCL"):
            continue   # summary sheet is derived, never a source of truth
        rows = _materialize(ws)
        sheet_bmc = bmc_by_name.get(ws.title.strip().upper())
        header_row = None
        for idx, row in enumerate(rows[:12]):
            if "product name" in [_norm_header(v) for v in row]:
                header_row = idx
                break
        if header_row is None:
            continue

        for r in range(header_row + 1, len(rows)):
            row = rows[r]
            name_cell = _cell(row, COL_PRODUCT + 1)
            first_cell = _cell(row, 1)
            if first_cell and str(first_cell).strip().lower() == "total":
                continue
            if not name_cell:
                continue
            bmc = sheet_bmc or bmc_by_name.get(str(_cell(row, 2) or "").strip().upper())
            if not bmc:
                unmatched_rows += 1
                continue
            # Match product (exact -> loose pattern); create it if still not found.
            product = resolve_product_by_name(name_cell, prod_cache, create=True)
            if not product:
                unmatched_rows += 1
                continue
            entry = statement.entries.filter(bmc_or_mcc=bmc, product=product).first()
            if not entry:
                entry = StockStatementEntry(statement=statement, bmc_or_mcc=bmc, product=product)
                created += 1
            entry.opening_balance = _to_int(_cell(row, COL_OPENING + 1))
            entry.received = _to_int(_cell(row, COL_RECEIVED + 1))
            entry.received_mcc = _to_int(_cell(row, COL_RECEIVED_MCC + 1))
            entry.stock_transfer = _to_int(_cell(row, COL_TRANSFER + 1))
            entry.mpp_sale = _to_int(_cell(row, COL_MPP_SALE + 1))
            entry.damage = _to_int(_cell(row, COL_DAMAGE + 1))
            entry.expire = _to_int(_cell(row, COL_EXPIRE + 1))
            remark = _cell(row, len(REPORT_COLUMNS))
            if remark:
                entry.remark = str(remark)[:255]
            entry.save()   # recomputes closing from the corrected components
            updated += 1

    statement.is_manual_override = True
    statement.override_uploaded_at = timezone.now()
    statement.save(update_fields=["is_manual_override", "override_uploaded_at", "updated_at"])
    # carry the corrected closings forward into later cycles' openings
    rechain_month(statement.cycle.monthly_cycle)
    return {"updated": updated, "created": created, "unmatched_rows": unmatched_rows}
