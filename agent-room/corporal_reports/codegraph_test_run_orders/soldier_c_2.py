from __future__ import annotations

from datetime import datetime
from typing import Any

from eventbus import EventBus
from order import Order
from order_status import OrderStatus
from payment import PaymentSystem, PaymentError
from states import RefundedState


def process_refund(
    order: Order,
    reason: str,
    partial_amount: float | None = None,
) -> dict[str, Any]:
    """Handle full or partial refund for an order.

    Validates that a refund is possible given current order state,
    executes the refund through the payment system, updates order
    state for full refunds, publishes a refund event, and returns
    a detailed result dict.

    Args:
        order: The Order instance to refund.
        reason: Human-readable explanation for the refund.
        partial_amount: If provided, refund only this amount instead of
            the full order total. Must be > 0 and <= order.total.

    Returns:
        A dict with keys:
            success (bool): Whether the refund completed.
            order_id (int): The order's identifier.
            refund_amount (float): Actual amount refunded.
            partial (bool): True when a partial refund was requested.
            reason (str): The supplied reason.
            timestamp (str): ISO-8601 datetime of the refund.
            error (str | None): Error message when success is False.
    """
    timestamp = datetime.now().isoformat()

    base_result: dict[str, Any] = {
        "success": False,
        "order_id": order.order_id,
        "refund_amount": 0.0,
        "partial": partial_amount is not None,
        "reason": reason,
        "timestamp": timestamp,
        "error": None,
    }

    # --- validation ---

    refundable_statuses = {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED}
    if order.status not in refundable_statuses:
        base_result["error"] = (
            f"Refund not allowed in current order state: {order.status.name}. "
            f"Refundable statuses: {[s.name for s in refundable_statuses]}."
        )
        return base_result

    order_total: float = order.total

    if partial_amount is not None:
        if partial_amount <= 0:
            base_result["error"] = (
                f"partial_amount must be greater than zero, got {partial_amount}."
            )
            return base_result
        if partial_amount > order_total:
            base_result["error"] = (
                f"partial_amount ({partial_amount:.2f}) exceeds order total "
                f"({order_total:.2f})."
            )
            return base_result

    refund_amount = partial_amount if partial_amount is not None else order_total

    # --- execute refund through payment system ---

    try:
        payment = PaymentSystem()
        payment.refund(order_id=order.order_id, amount=refund_amount, reason=reason)
    except PaymentError as exc:
        base_result["error"] = f"Payment system error: {exc}"
        return base_result

    # --- update order state for full refunds ---

    is_partial = partial_amount is not None
    if not is_partial:
        old_status = order.status
        order._set_state(RefundedState(), OrderStatus.CANCELLED)
    else:
        old_status = order.status
        # Partial refund: record in metadata without changing lifecycle state.
        order.metadata.setdefault("partial_refunds", []).append(
            {
                "amount": refund_amount,
                "reason": reason,
                "timestamp": timestamp,
            }
        )

    # --- notify via events ---

    EventBus().publish(
        "order_refunded",
        order_id=order.order_id,
        refund_amount=refund_amount,
        partial=is_partial,
        reason=reason,
        old_status=old_status,
        new_status=order.status,
        timestamp=timestamp,
    )

    # --- return detailed result ---

    base_result["success"] = True
    base_result["refund_amount"] = refund_amount
    return base_result
