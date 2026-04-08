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
    updates order state, publishes events, and returns a detailed result dict.
    """
    # --- validation ---
    REFUNDABLE_STATUSES = {"PAID", "SHIPPED", "DELIVERED"}
    if order.status.name not in REFUNDABLE_STATUSES:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": None,
            "refund_type": None,
            "error": (
                f"Order {order.order_id} cannot be refunded in status "
                f"'{order.status.name}'. Refundable statuses: "
                f"{sorted(REFUNDABLE_STATUSES)}."
            ),
            "timestamp": datetime.now().isoformat(),
        }

    # Compute the applicable total via the discount-aware total property.
    # order.total delegates to order_total (discount chain) per the graph spec.
    try:
        order_total: float = order.total
    except AttributeError:
        # Fallback: sum items directly if the property is not yet wired.
        order_total = sum(
            getattr(item, "price", 0) * getattr(item, "quantity", 1)
            for item in order.items
        )

    if partial_amount is not None:
        if partial_amount <= 0:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "refund_type": None,
                "error": "partial_amount must be greater than zero.",
                "timestamp": datetime.now().isoformat(),
            }
        if partial_amount > order_total:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "refund_type": None,
                "error": (
                    f"partial_amount {partial_amount:.2f} exceeds order total "
                    f"{order_total:.2f}."
                ),
                "timestamp": datetime.now().isoformat(),
            }

    refund_amount: float = partial_amount if partial_amount is not None else order_total
    refund_type: str = "partial" if partial_amount is not None else "full"

    # --- payment system ---
    # PaymentGateway is assumed to be a singleton/service reachable by import;
    # the graph context does not expose it, so we import defensively.
    try:
        from payment_gateway import PaymentGateway  # type: ignore[import]
        gateway = PaymentGateway()
        payment_ref: str = gateway.refund(
            order_id=order.order_id,
            amount=refund_amount,
            reason=reason,
        )
    except ImportError:
        # No payment integration available in this environment; record as pending.
        payment_ref = f"PENDING-{order.order_id}"
    except Exception as exc:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": refund_amount,
            "refund_type": refund_type,
            "error": f"Payment gateway error: {exc}",
            "timestamp": datetime.now().isoformat(),
        }

    # --- order state update ---
    # Full refund: cancel the order (CancelledState + CANCELLED status).
    # Partial refund: keep current status but record refund metadata.
    if refund_type == "full":
        order.cancel()  # delegates to _state.cancel(order) → order_set_state
    else:
        # Record partial refund in metadata without changing lifecycle status.
        refunds: list[dict[str, Any]] = order.metadata.setdefault("refunds", [])
        refunds.append(
            {
                "amount": refund_amount,
                "reason": reason,
                "payment_ref": payment_ref,
                "timestamp": datetime.now().isoformat(),
            }
        )

    # --- event notification ---
    # EventBus is a Singleton; order_set_state already publishes
    # "order_status_changed" on full refund via cancel().  We additionally
    # publish a dedicated "order_refunded" event for both cases so downstream
    # consumers (billing, notifications, analytics) receive a typed signal.
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
        pass  # EventBus not available in this environment; skip gracefully.

    # --- result ---
    return {
        "success": True,
        "order_id": order.order_id,
        "reason": reason,
        "refund_amount": refund_amount,
        "refund_type": refund_type,
        "payment_ref": payment_ref,
        "order_status": order.status.name,
        "timestamp": datetime.now().isoformat(),
    }
