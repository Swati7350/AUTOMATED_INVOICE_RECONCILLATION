"""
reconciler.py
-------------
Compares Invoice vs POD on:
  - PO Number
  - Per product: description, size, volume, quantity, unit price, subtotal

One discrepancy entry per product (multiple field issues collapsed into one line).

Fixes:
  - $ and currency symbols stripped before numeric comparison
  - Fuzzy name matching: "Coca-Cola" matches "Coca-Cola Classic" via
    token containment, so partial-name variants don't false-fire as "not received"
"""

from dataclasses import dataclass, field
from extractor import DocumentFields, LineItem


@dataclass
class Discrepancy:
    product: str    # e.g. "Sprite (330ml)"
    message: str    # plain-English one-liner


@dataclass
class ReconciliationReport:
    discrepancies: list[Discrepancy] = field(default_factory=list)
    matched_products: list[str] = field(default_factory=list)
    po_ok: bool = True

    @property
    def is_clean(self) -> bool:
        return len(self.discrepancies) == 0 and self.po_ok


# ── Helpers ────────────────────────────────────────────────────────────────────

def _norm(v: str) -> str:
    """
    Normalise a string for comparison.
    Strips: whitespace, currency symbols ($€£₹), commas, spaces.
    """
    v = v.strip().lower()
    for ch in ("$", "€", "£", "₹", ",", " "):
        v = v.replace(ch, "")
    return v


def _norm_desc(v: str) -> str:
    """Normalise a product description: lowercase, strip punctuation/spaces."""
    v = v.strip().lower()
    for ch in ("-", "_", ".", ",", " "):
        v = v.replace(ch, "")
    return v


def _label(item: LineItem) -> str:
    size = (item.size or item.volume_liters or "").strip()
    name = item.description.strip()
    return f"{name} ({size})" if size else name


def _names_match(inv_desc: str, pod_desc: str) -> bool:
    """
    Match product names with tolerance for minor variants.
    Strategy (in order):
      1. Exact normalised match            → "cocacola" == "cocacola"
      2. One is a prefix of the other      → "cocacola" in "cocacolaclassic"
      3. All tokens of shorter name appear → "coca cola" tokens in "coca cola classic"
    This prevents "Coca-Cola" vs "Coca-Cola Classic" from being treated as
    completely different products.
    """
    a = _norm_desc(inv_desc)
    b = _norm_desc(pod_desc)

    if a == b:
        return True
    if a in b or b in a:
        return True

    # Token subset check (space-split on original strings)
    a_tokens = set(inv_desc.strip().lower().split())
    b_tokens = set(pod_desc.strip().lower().split())
    shorter, longer = (a_tokens, b_tokens) if len(a_tokens) <= len(b_tokens) else (b_tokens, a_tokens)
    if shorter and shorter.issubset(longer):
        return True

    return False


def _find_pod(inv: LineItem, pod_items: list[LineItem]) -> LineItem | None:
    """Find the best matching POD item for an invoice line. Fuzzy name match."""
    # 1st pass: exact normalised match
    for p in pod_items:
        if _norm_desc(inv.description) == _norm_desc(p.description):
            return p
    # 2nd pass: fuzzy match
    for p in pod_items:
        if _names_match(inv.description, p.description):
            return p
    return None


def _compare(inv: LineItem, pod: LineItem) -> list[str]:
    """
    Return short problem phrases for one matched product pair.
    Only flags a field when BOTH sides are non-empty AND differ after normalisation.
    """
    issues = []

    # Size / volume
    inv_size = _norm(inv.size or inv.volume_liters or "")
    pod_size = _norm(pod.size or pod.volume_liters or "")
    if inv_size and pod_size and inv_size != pod_size:
        issues.append(
            f"size {pod.size or pod.volume_liters} "
            f"(expected {inv.size or inv.volume_liters})"
        )

    # Quantity
    if _norm(inv.quantity) and _norm(pod.quantity) \
            and _norm(inv.quantity) != _norm(pod.quantity):
        issues.append(f"qty {pod.quantity} (expected {inv.quantity})")

    # Unit price
    if _norm(inv.unit_price) and _norm(pod.unit_price) \
            and _norm(inv.unit_price) != _norm(pod.unit_price):
        issues.append(
            f"unit price {pod.unit_price} (expected {inv.unit_price})"
        )

    # Subtotal / amount
    if _norm(inv.subtotal) and _norm(pod.subtotal) \
            and _norm(inv.subtotal) != _norm(pod.subtotal):
        issues.append(f"amount {pod.subtotal} (expected {inv.subtotal})")

    return issues


# ── Main ───────────────────────────────────────────────────────────────────────

def reconcile(invoice: DocumentFields, pod: DocumentFields) -> ReconciliationReport:
    report = ReconciliationReport()

    # PO Number
    inv_po = _norm(invoice.po_number)
    pod_po = _norm(pod.po_number)
    if inv_po and pod_po and inv_po != pod_po:
        report.po_ok = False
        report.discrepancies.append(Discrepancy(
            product="PO Number",
            message=(
                f"PO number mismatch — "
                f"Invoice: {invoice.po_number}, Receipt: {pod.po_number}"
            ),
        ))

    matched_pod_idx: set[int] = set()

    for inv_item in invoice.line_items:
        if not inv_item.description.strip():
            continue

        label    = _label(inv_item)
        pod_item = _find_pod(inv_item, pod.line_items)

        if pod_item is None:
            report.discrepancies.append(Discrepancy(
                product=label,
                message=f"{label} — not received",
            ))
        else:
            matched_pod_idx.add(pod.line_items.index(pod_item))
            issues = _compare(inv_item, pod_item)
            if issues:
                detail = ", ".join(issues)
                report.discrepancies.append(Discrepancy(
                    product=label,
                    message=f"{label} — {detail}",
                ))
            else:
                report.matched_products.append(label)

    # Products on GRN/POD not on invoice
    for i, pod_item in enumerate(pod.line_items):
        if i not in matched_pod_idx and pod_item.description.strip():
            label = _label(pod_item)
            report.discrepancies.append(Discrepancy(
                product=label,
                message=f"{label} — received but not on invoice",
            ))

    return report
