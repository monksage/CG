from __future__ import annotations


REFUNDABLE_STATES = {"delivered", "paid", "shipped"}


def process_refund(
    order: dict,
    reason: str,
    partial_amount: float | None = None,
    *,
    payment_gateway,
    event_bus,
) -> dict:
    """Handle full or partial refund for an order.

    Validates the refund is possible, executes it through the payment system,
    updates order state, publishes events, and returns a detailed result dict.

    Args:
        order: OrderData dict with at least current_state_name, status,
               order_id, total, and payment_id fields.
        reason: Human-readable reason for the refund.
        partial_amount: If provided, refund only this amount; otherwise full refund.
        payment_gateway: Payment system client with a .refund(payment_id, amount) method
                         that returns a dict with at least {"transaction_id": str}.
        event_bus: EventBus with a .publish(event, **data) method.

    Returns:
        dict with keys:
            success (bool): Whether the refund completed without error.
            order_id (str | int): The order's identifier.
            refund_type (str): "partial" or "full".
            refunded_amount (float): The amount actually refunded.
            transaction_id (str | None): Payment gateway transaction id on success.
            new_status (str | None): The order status after the refund, or None on failure.
            reason (str): The reason string passed in.
            error (str | None): Error message if success is False, else None.
    """
    order_id = order.get("order_id")
    current_state = order.get("current_state_name", "")
    order_total = order.get("total", 0.0)
    payment_id = order.get("payment_id")

    # --- Validation ---

    if current_state not in REFUNDABLE_STATES:
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": None,
            "refunded_amount": 0.0,
            "transaction_id": None,
            "new_status": None,
            "reason": reason,
            "error": (
                f"Refund not allowed in state '{current_state}'. "
                f"Must be one of: {sorted(REFUNDABLE_STATES)}."
            ),
        }

    if not payment_id:
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": None,
            "refunded_amount": 0.0,
            "transaction_id": None,
            "new_status": None,
            "reason": reason,
            "error": "Order has no payment_id; cannot process refund.",
        }

    if not reason or not reason.strip():
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": None,
            "refunded_amount": 0.0,
            "transaction_id": None,
            "new_status": None,
            "reason": reason,
            "error": "Refund reason must not be empty.",
        }

    if partial_amount is not None:
        if partial_amount <= 0:
            return {
                "success": False,
                "order_id": order_id,
                "refund_type": "partial",
                "refunded_amount": 0.0,
                "transaction_id": None,
                "new_status": None,
                "reason": reason,
                "error": f"partial_amount must be positive; got {partial_amount}.",
            }
        if partial_amount > order_total:
            return {
                "success": False,
                "order_id": order_id,
                "refund_type": "partial",
                "refunded_amount": 0.0,
                "transaction_id": None,
                "new_status": None,
                "reason": reason,
                "error": (
                    f"partial_amount {partial_amount} exceeds order total {order_total}."
                ),
            }

    is_partial = partial_amount is not None and partial_amount < order_total
    refund_type = "partial" if is_partial else "full"
    refunded_amount = partial_amount if is_partial else order_total

    # --- Execute refund through payment system ---

    try:
        gateway_result = payment_gateway.refund(payment_id, refunded_amount)
        transaction_id = gateway_result["transaction_id"]
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": refund_type,
            "refunded_amount": 0.0,
            "transaction_id": None,
            "new_status": None,
            "reason": reason,
            "error": f"Payment gateway error: {exc}",
        }

    # --- Update order state ---

    if is_partial:
        new_state_name = "partially_refunded"
        new_status = "partially_refunded"
    else:
        new_state_name = "refunded"
        new_status = "refunded"

    updated_order = order_set_state(order, new_state_name, new_status, event_bus)

    # --- Publish refund event ---

    event_bus.publish(
        "order_refunded",
        order_id=order_id,
        refund_type=refund_type,
        refunded_amount=refunded_amount,
        transaction_id=transaction_id,
        reason=reason,
    )

    return {
        "success": True,
        "order_id": order_id,
        "refund_type": refund_type,
        "refunded_amount": refunded_amount,
        "transaction_id": transaction_id,
        "new_status": updated_order["status"],
        "reason": reason,
        "error": None,
    }


def order_set_state(state: dict, new_state_name: str, new_status: str, event_bus) -> dict:
    """Shallow-merge new state fields and publish order_status_changed event.

    This is a local stub matching the spec of the order_set_state node in the
    graph; the real implementation lives in the CodeGraph DB.
    """
    old_status = state["status"]
    new_state = {**state, "current_state_name": new_state_name, "status": new_status}
    event_bus.publish(
        "order_status_changed",
        order_id=state["order_id"],
        old=old_status,
        new=new_status,
    )
    return new_state
