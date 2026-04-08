from __future__ import annotations


def process_refund(order: dict, reason: str, partial_amount: float | None = None) -> dict:
    """Handle full or partial refunds for an order.

    Validates the refund is possible, executes it through the payment system,
    updates order state, notifies via events, and returns a detailed result dict.

    Args:
        order: OrderData dict representing the current order state.
        reason: Human-readable reason for the refund.
        partial_amount: If provided, refund only this amount; otherwise refund in full.

    Returns:
        A dict with keys:
            success (bool), refund_id (str | None), amount (float),
            order_id (str), reason (str), updated_order (dict | None),
            error (str | None).
    """
    REFUNDABLE_STATUSES = {"paid", "shipped", "delivered"}

    order_id = order.get("order_id") or order.get("id")
    current_status = order.get("status", "")
    total_amount = order.get("total_amount", 0.0)
    payment_id = order.get("payment_id")
    event_bus = order.get("event_bus")

    # --- Validate ---

    if current_status not in REFUNDABLE_STATUSES:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": f"Refund not allowed in state '{current_status}'. "
                     f"Must be one of: {sorted(REFUNDABLE_STATUSES)}.",
        }

    if not payment_id:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": "Order has no associated payment_id; cannot process refund.",
        }

    refund_amount = partial_amount if partial_amount is not None else total_amount

    if refund_amount <= 0:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": f"Refund amount must be positive, got {refund_amount}.",
        }

    if refund_amount > total_amount:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": (
                f"Refund amount {refund_amount} exceeds order total {total_amount}."
            ),
        }

    is_full_refund = (partial_amount is None or partial_amount >= total_amount)

    # --- Execute via payment system ---

    payment_gateway = order.get("payment_gateway")
    if payment_gateway is None:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": "No payment_gateway available on order; cannot execute refund.",
        }

    try:
        gateway_result = payment_gateway.refund(
            payment_id=payment_id,
            amount=refund_amount,
            reason=reason,
        )
    except Exception as exc:
        return {
            "success": False,
            "refund_id": None,
            "amount": 0.0,
            "order_id": order_id,
            "reason": reason,
            "updated_order": None,
            "error": f"Payment gateway error: {exc}",
        }

    refund_id = gateway_result.get("refund_id")

    # --- Update order state ---

    already_refunded = order.get("refunded_amount", 0.0)
    new_refunded_amount = already_refunded + refund_amount

    if is_full_refund:
        new_status = "refunded"
        new_state_name = "RefundedState"
    else:
        new_status = "partially_refunded"
        new_state_name = "PartiallyRefundedState"

    updated_order = {
        **order,
        "status": new_status,
        "current_state_name": new_state_name,
        "refunded_amount": new_refunded_amount,
        "last_refund_id": refund_id,
        "last_refund_reason": reason,
    }

    # --- Publish event ---

    if event_bus is not None:
        old_status = current_status
        event_bus.publish(
            "order_status_changed",
            order_id=order_id,
            old=old_status,
            new=new_status,
        )
        event_bus.publish(
            "order_refund_processed",
            order_id=order_id,
            refund_id=refund_id,
            amount=refund_amount,
            reason=reason,
            full_refund=is_full_refund,
        )

    return {
        "success": True,
        "refund_id": refund_id,
        "amount": refund_amount,
        "order_id": order_id,
        "reason": reason,
        "updated_order": updated_order,
        "error": None,
    }
