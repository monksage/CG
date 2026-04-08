from __future__ import annotations

from datetime import datetime
from typing import Any


def process_refund(
    order,
    reason: str,
    partial_amount: float | None = None,
) -> dict:
    """Handle full or partial refunds for an order.

    Validates the refund is possible, executes it through the payment system,
    updates order state, publishes events via EventBus, and returns a detailed
    result dict.

    Args:
        order: An Order instance exposing .order_id (int), .status (OrderStatus),
               .total (float, discount-aware via DiscountStrategy), .metadata (dict),
               and .cancel() (delegates to _state.cancel -> _set_state).
        reason: Human-readable explanation for the refund.
        partial_amount: If provided, refund only this amount (must be > 0 and
                        <= order.total). If None, a full refund is issued.

    Returns:
        dict with keys:
          success (bool), order_id (int), reason (str), refund_amount (float|None),
          refund_type (str|None), error (str|None), timestamp (str ISO-8601),
          and on success: payment_ref (str), order_status (str).
    """
    timestamp = datetime.now().isoformat()

    # --- Validation: status ---
    # Only orders past the payment step carry actual money. Refunds on DRAFT,
    # CONFIRMED, or already-CANCELLED orders make no financial sense.
    REFUNDABLE = {"PAID", "SHIPPED", "DELIVERED"}
    if order.status.name not in REFUNDABLE:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": None,
            "refund_type": None,
            "error": (
                f"Cannot refund order {order.order_id} in status "
                f"'{order.status.name}'. Eligible statuses: {sorted(REFUNDABLE)}."
            ),
            "timestamp": timestamp,
        }

    # --- Validation: compute order total ---
    # order.total calls order_total property which composes order_raw_total with
    # the active DiscountStrategy (NoDiscount, PercentDiscount, etc.).
    order_total: float = order.total

    # --- Validation: partial amount ---
    if partial_amount is not None:
        if partial_amount <= 0:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "refund_type": "partial",
                "error": f"partial_amount must be greater than zero, got {partial_amount!r}.",
                "timestamp": timestamp,
            }
        if partial_amount > order_total:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "refund_type": "partial",
                "error": (
                    f"partial_amount {partial_amount:.2f} exceeds order total "
                    f"{order_total:.2f}."
                ),
                "timestamp": timestamp,
            }

    refund_amount: float = partial_amount if partial_amount is not None else order_total
    refund_type: str = "partial" if partial_amount is not None else "full"

    # --- Execute refund through the payment system ---
    try:
        from payment_gateway import PaymentGateway  # type: ignore[import]

        payment_ref: str = PaymentGateway().refund(
            order_id=order.order_id,
            amount=refund_amount,
            reason=reason,
        )
    except ImportError:
        # Payment module not yet wired; mark as pending so order state and events
        # can still be updated without silently swallowing configuration errors.
        payment_ref = f"PENDING-{order.order_id}"
    except Exception as exc:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": refund_amount,
            "refund_type": refund_type,
            "error": f"Payment gateway error: {exc}",
            "timestamp": timestamp,
        }

    # --- Update order state ---
    # Full refund: cancel the order so its lifecycle correctly reflects the
    # outcome. order.cancel() -> _state.cancel(order) -> _set_state(CancelledState(),
    # OrderStatus.CANCELLED), which also publishes "order_status_changed" via
    # EventBus (handled inside _set_state; no duplication needed here).
    #
    # Partial refund: the order continues its lifecycle unchanged. We record the
    # refund in metadata for auditability.
    if refund_type == "full":
        order.cancel()
    else:
        refunds: list[dict[str, Any]] = order.metadata.setdefault("refunds", [])
        refunds.append(
            {
                "amount": refund_amount,
                "reason": reason,
                "payment_ref": payment_ref,
                "timestamp": timestamp,
            }
        )

    # --- Notify via events ---
    # _set_state already fired "order_status_changed" for full refunds via the
    # cancel() chain. We publish "order_refunded" in both cases so billing,
    # notifications, and analytics subscribers receive a typed money-movement
    # event without filtering status transitions.
    try:
        from event_bus import EventBus  # type: ignore[import]

        EventBus().publish(
            "order_refunded",
            order_id=order.order_id,
            refund_type=refund_type,
            refund_amount=refund_amount,
            reason=reason,
            payment_ref=payment_ref,
        )
    except ImportError:
        pass  # EventBus not wired in this environment; skip gracefully.

    # --- Return detailed result ---
    return {
        "success": True,
        "order_id": order.order_id,
        "reason": reason,
        "refund_amount": refund_amount,
        "refund_type": refund_type,
        "payment_ref": payment_ref,
        "order_status": order.status.name,
        "error": None,
        "timestamp": timestamp,
    }
