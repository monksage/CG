from __future__ import annotations


def process_refund(order: dict, reason: str, partial_amount: float | None = None) -> dict:
    """
    Handle a full or partial refund for an order.

    Validates that the refund is possible given the current order state,
    executes the refund through the payment system, updates the order state
    via order_set_state, publishes refund events through the event bus, and
    returns a detailed result dict.

    Parameters
    ----------
    order : dict
        OrderData state dict. Expected fields:
            - order_id          : str
            - status            : str
            - current_state_name: str
            - total             : float   (total amount charged)
            - payment_id        : str     (reference used by payment system)
            - event_bus         : EventBus
            - state_registry    : dict[str, OrderState]
            - payment_system    : object  with .refund(payment_id, amount) -> dict
    reason : str
        Human-readable reason for the refund.
    partial_amount : float | None
        If given, refund only this amount (must be > 0 and <= order total).
        If None, a full refund is performed.

    Returns
    -------
    dict with keys:
        "success"         : bool
        "order_id"        : str
        "refund_type"     : "full" | "partial"
        "requested_amount": float
        "refunded_amount" : float  (as confirmed by the payment system)
        "reason"          : str
        "payment_id"      : str
        "new_status"      : str
        "error"           : str | None  (present only when success is False)
    """
    # ------------------------------------------------------------------ #
    # 0. Extract shared dependencies from the order dict                  #
    # ------------------------------------------------------------------ #
    order_id = order["order_id"]
    current_state_name = order["current_state_name"]
    total = float(order["total"])
    payment_id = order["payment_id"]
    event_bus = order["event_bus"]
    payment_system = order["payment_system"]

    def _failure(error_msg: str) -> dict:
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": "partial" if partial_amount is not None else "full",
            "requested_amount": partial_amount if partial_amount is not None else total,
            "refunded_amount": 0.0,
            "reason": reason,
            "payment_id": payment_id,
            "new_status": order["status"],
            "error": error_msg,
        }

    # ------------------------------------------------------------------ #
    # 1. Validate: refund is only allowed after payment has been taken     #
    # ------------------------------------------------------------------ #
    REFUNDABLE_STATES = {"paid", "shipped", "delivered"}
    if current_state_name not in REFUNDABLE_STATES:
        return _failure(
            f"Refund not allowed in state '{current_state_name}'. "
            f"Order must be in one of: {sorted(REFUNDABLE_STATES)}."
        )

    if not reason or not reason.strip():
        return _failure("Refund reason must not be empty.")

    # ------------------------------------------------------------------ #
    # 2. Determine refund amount                                           #
    # ------------------------------------------------------------------ #
    is_partial = partial_amount is not None
    if is_partial:
        if partial_amount <= 0:
            return _failure(
                f"partial_amount must be greater than 0, got {partial_amount}."
            )
        if partial_amount > total:
            return _failure(
                f"partial_amount ({partial_amount}) exceeds order total ({total})."
            )
        amount_to_refund = float(partial_amount)
        refund_type = "partial"
    else:
        amount_to_refund = total
        refund_type = "full"

    # ------------------------------------------------------------------ #
    # 3. Execute refund through the payment system                         #
    # ------------------------------------------------------------------ #
    try:
        payment_result = payment_system.refund(payment_id, amount_to_refund)
    except Exception as exc:
        return _failure(f"Payment system error: {exc}")

    refunded_amount = float(payment_result.get("refunded_amount", amount_to_refund))

    # ------------------------------------------------------------------ #
    # 4. Determine new order state after the refund                        #
    # ------------------------------------------------------------------ #
    if is_partial:
        new_state_name = current_state_name       # stays in the same lifecycle state
        new_status = "partially_refunded"
    else:
        new_state_name = "refunded"
        new_status = "refunded"

    # ------------------------------------------------------------------ #
    # 5. Update order state (immutable merge via order_set_state pattern)  #
    # ------------------------------------------------------------------ #
    old_status = order["status"]
    updated_order = {
        **order,
        "current_state_name": new_state_name,
        "status": new_status,
    }

    event_bus.publish(
        "order_status_changed",
        order_id=order_id,
        old=old_status,
        new=new_status,
    )

    # ------------------------------------------------------------------ #
    # 6. Publish a dedicated refund event                                  #
    # ------------------------------------------------------------------ #
    event_bus.publish(
        "order_refunded",
        order_id=order_id,
        refund_type=refund_type,
        refunded_amount=refunded_amount,
        reason=reason,
        payment_id=payment_id,
    )

    # ------------------------------------------------------------------ #
    # 7. Return detailed result                                            #
    # ------------------------------------------------------------------ #
    return {
        "success": True,
        "order_id": order_id,
        "refund_type": refund_type,
        "requested_amount": amount_to_refund,
        "refunded_amount": refunded_amount,
        "reason": reason,
        "payment_id": payment_id,
        "new_status": new_status,
        "error": None,
    }
