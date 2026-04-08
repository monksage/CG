from __future__ import annotations

from datetime import datetime
from typing import Any

from order import Order, OrderStatus
from event_bus import EventBus
from payment import PaymentSystem, PaymentError


def process_refund(
    order: Order,
    reason: str,
    partial_amount: float | None = None,
) -> dict[str, Any]:
    """Handle full or partial refunds for an order.

    Validates the refund is possible, executes it through the payment system,
    updates order state, publishes an event, and returns a detailed result dict.
    """
    # --- validation ----------------------------------------------------------
    refundable_statuses = {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED}
    if order.status not in refundable_statuses:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": None,
            "partial": False,
            "error": (
                f"Order is in status '{order.status.name}' which is not eligible for a refund. "
                f"Eligible statuses: {[s.name for s in refundable_statuses]}."
            ),
            "timestamp": datetime.now().isoformat(),
        }

    order_total: float = order.total

    if partial_amount is not None:
        if partial_amount <= 0:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "partial": True,
                "error": f"partial_amount must be positive, got {partial_amount}.",
                "timestamp": datetime.now().isoformat(),
            }
        if partial_amount > order_total:
            return {
                "success": False,
                "order_id": order.order_id,
                "reason": reason,
                "refund_amount": None,
                "partial": True,
                "error": (
                    f"partial_amount ({partial_amount:.2f}) exceeds order total ({order_total:.2f})."
                ),
                "timestamp": datetime.now().isoformat(),
            }

    refund_amount: float = partial_amount if partial_amount is not None else order_total
    is_partial: bool = partial_amount is not None

    # --- execute refund via payment system -----------------------------------
    try:
        payment = PaymentSystem()
        transaction_id: str = payment.refund(
            order_id=order.order_id,
            amount=refund_amount,
            reason=reason,
        )
    except PaymentError as exc:
        return {
            "success": False,
            "order_id": order.order_id,
            "reason": reason,
            "refund_amount": refund_amount,
            "partial": is_partial,
            "error": f"Payment system error: {exc}",
            "timestamp": datetime.now().isoformat(),
        }

    # --- update order state --------------------------------------------------
    # Only transition to CANCELLED on a full refund; partial refunds leave the
    # order status unchanged (order fulfilled, portion refunded).
    if not is_partial:
        order.cancel()

    order.metadata["refund"] = {
        "transaction_id": transaction_id,
        "amount": refund_amount,
        "partial": is_partial,
        "reason": reason,
        "refunded_at": datetime.now().isoformat(),
    }

    # --- publish event -------------------------------------------------------
    EventBus().publish(
        "order_refunded",
        order_id=order.order_id,
        refund_amount=refund_amount,
        partial=is_partial,
        reason=reason,
        transaction_id=transaction_id,
    )

    # --- return result -------------------------------------------------------
    return {
        "success": True,
        "order_id": order.order_id,
        "reason": reason,
        "refund_amount": refund_amount,
        "partial": is_partial,
        "transaction_id": transaction_id,
        "order_status": order.status.name,
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }
