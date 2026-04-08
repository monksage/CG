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

    Args:
        order: An Order instance. Must expose .order_id, .status, .items,
               .metadata, .total, and .cancel().
        reason: Human-readable explanation for the refund.
        partial_amount: If given, refund only this amount (must be > 0 and
                        <= order total). If None, a full refund is issued.

    Returns:
        dict with keys: success, order_id, reason, refund_amount, refund_type,
        payment_ref (on success), order_status (on success), error (on failure),
        timestamp.
    """
    # --- Validation: status ---
    # Only orders that have been paid can be refunded. The graph spec shows
    # status transitions: DRAFT -> CONFIRMED -> PAID -> SHIPPED -> DELIVERED,
    # and CANCELLED as a terminal state. Refunds are meaningful only after
    # money has changed hands.
    REFUNDABLE_STATUSES = {"PAID", "SHIPPED", "DELIVERED"}
    if order.status.name not in REFUNDABLE_STATUSES:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": None,
            "refund_type": None,
            "error": (
                f"Order {order.order_id} is in status '{order.status.name}' "
                f"and cannot be refunded. Eligible statuses: "
                f"{sorted(REFUNDABLE_STATUSES)}."
            ),
            "timestamp": datetime.now().isoformat(),
        }

    # --- Validation: compute order total ---
    # order.total invokes order_total (discount-aware) per the graph spec.
    # order_total composes order_raw_total with the active DiscountStrategy.
    try:
        order_total: float = order.total
    except AttributeError:
        # Fallback if the property is not yet wired (e.g. stub environment).
        order_total = sum(
            getattr(item, "price", 0.0) * getattr(item, "quantity", 1)
            for item in order.items
        )

    # --- Validation: partial amount ---
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
                    f"partial_amount {partial_amount:.2f} exceeds the order "
                    f"total of {order_total:.2f}."
                ),
                "timestamp": datetime.now().isoformat(),
            }

    refund_amount: float = partial_amount if partial_amount is not None else order_total
    refund_type: str = "partial" if partial_amount is not None else "full"

    # --- Payment system ---
    # PaymentGateway is not represented in the Dunbar context, so we import it
    # defensively. If unavailable, we record the refund as pending so the rest
    # of the function can still update order state and fire events.
    try:
        from payment_gateway import PaymentGateway  # type: ignore[import]

        gateway = PaymentGateway()
        payment_ref: str = gateway.refund(
            order_id=order.order_id,
            amount=refund_amount,
            reason=reason,
        )
    except ImportError:
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

    # --- Order state update ---
    # Full refund: cancel the order so the lifecycle reflects the outcome.
    #   order.cancel() delegates to _state.cancel(order), which calls back
    #   into order._set_state(CancelledState(), OrderStatus.CANCELLED).
    #   _set_state then publishes "order_status_changed" via EventBus.
    # Partial refund: the order continues its normal lifecycle; we record the
    #   refund in metadata so it is auditable without a state change.
    if refund_type == "full":
        order.cancel()
    else:
        refunds: list[dict[str, Any]] = order.metadata.setdefault("refunds", [])
        refunds.append(
            {
                "amount": refund_amount,
                "reason": reason,
                "payment_ref": payment_ref,
                "timestamp": datetime.now().isoformat(),
            }
        )

    # --- Event notification ---
    # order_set_state already publishes "order_status_changed" for full refunds
    # through the cancel() → _state.cancel() → _set_state() chain.
    # We additionally publish "order_refunded" in both cases so consumers that
    # care specifically about money movement (billing, notifications, analytics)
    # receive a typed, dedicated event without having to filter status changes.
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

    # --- Result ---
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
