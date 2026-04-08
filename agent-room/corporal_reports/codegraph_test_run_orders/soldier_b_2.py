from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def process_refund(order, reason: str, partial_amount: float | None = None) -> dict:
    """
    Handle a full or partial refund for an Order instance.

    Validates the refund is possible given the current order status, executes
    the refund through the payment system, updates the order state via the
    State pattern (_set_state / order_set_state), notifies via EventBus events,
    and returns a detailed result dict.

    Parameters
    ----------
    order : Order
        The Order aggregate. Expected to have:
            - order_id          : int
            - status            : OrderStatus  (enum with .name str)
            - _state            : OrderState
            - payment_id        : str          (stored in order.metadata["payment_id"])
            - payment_system    : object       (stored in order.metadata["payment_system"])
                                               with .refund(payment_id, amount) -> dict
        The order total is obtained via order.total (the discounted total property).
    reason : str
        Human-readable reason for the refund. Must not be empty.
    partial_amount : float | None
        If given, refund only this amount (must be > 0 and <= order total).
        If None, a full refund of the order total is performed.

    Returns
    -------
    dict with keys:
        "success"          : bool
        "order_id"         : int
        "refund_type"      : "full" | "partial"
        "requested_amount" : float
        "refunded_amount"  : float   (as confirmed by the payment system)
        "reason"           : str
        "payment_id"       : str
        "new_status"       : str     (OrderStatus.name after transition)
        "error"            : str | None  (present only when success is False)
    """
    # ------------------------------------------------------------------ #
    # 0. Shared helpers                                                    #
    # ------------------------------------------------------------------ #
    order_id = order.order_id
    current_status_name = order.status.name.lower()

    def _failure(error_msg: str) -> dict:
        return {
            "success": False,
            "order_id": order_id,
            "refund_type": "partial" if partial_amount is not None else "full",
            "requested_amount": partial_amount if partial_amount is not None else float(order.total),
            "refunded_amount": 0.0,
            "reason": reason,
            "payment_id": order.metadata.get("payment_id", ""),
            "new_status": current_status_name,
            "error": error_msg,
        }

    # ------------------------------------------------------------------ #
    # 1. Validate: refund is only allowed after payment has been captured  #
    # ------------------------------------------------------------------ #
    REFUNDABLE_STATUSES = {"paid", "shipped", "delivered"}
    if current_status_name not in REFUNDABLE_STATUSES:
        return _failure(
            f"Refund not allowed in status '{current_status_name}'. "
            f"Order must be in one of: {sorted(REFUNDABLE_STATUSES)}."
        )

    if not reason or not reason.strip():
        return _failure("Refund reason must not be empty.")

    payment_id: str = order.metadata.get("payment_id", "")
    if not payment_id:
        return _failure("No payment_id found in order.metadata; cannot execute refund.")

    payment_system = order.metadata.get("payment_system")
    if payment_system is None:
        return _failure("No payment_system found in order.metadata; cannot execute refund.")

    # ------------------------------------------------------------------ #
    # 2. Determine refund amount                                           #
    # ------------------------------------------------------------------ #
    total = float(order.total)
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
    # 4. Update order state via the State pattern                          #
    # ------------------------------------------------------------------ #
    # Import lazily so this function remains portable across graph nodes.
    from order import OrderStatus, RefundedState  # type: ignore[import]

    old_status = order.status

    if is_partial:
        # Partial refund: order stays in current lifecycle state but we record
        # the partial refund in metadata so downstream logic can inspect it.
        order.metadata["partially_refunded"] = True
        order.metadata["partial_refund_amount"] = order.metadata.get(
            "partial_refund_amount", 0.0
        ) + refunded_amount
        new_status_name = current_status_name + "_partially_refunded"
        # Publish status-changed event manually since no dedicated state transition exists.
        from event_bus import EventBus  # type: ignore[import]
        EventBus().publish(
            "order_status_changed",
            order_id=order_id,
            old=old_status.name,
            new=new_status_name,
        )
    else:
        # Full refund: transition to the terminal Refunded state.
        order._set_state(RefundedState(), OrderStatus.REFUNDED)
        new_status_name = order.status.name.lower()

    # ------------------------------------------------------------------ #
    # 5. Publish a dedicated refund event via EventBus                     #
    # ------------------------------------------------------------------ #
    from event_bus import EventBus  # type: ignore[import]

    EventBus().publish(
        "order_refunded",
        order_id=order_id,
        refund_type=refund_type,
        refunded_amount=refunded_amount,
        reason=reason,
        payment_id=payment_id,
    )

    # ------------------------------------------------------------------ #
    # 6. Return detailed result                                            #
    # ------------------------------------------------------------------ #
    return {
        "success": True,
        "order_id": order_id,
        "refund_type": refund_type,
        "requested_amount": amount_to_refund,
        "refunded_amount": refunded_amount,
        "reason": reason,
        "payment_id": payment_id,
        "new_status": new_status_name,
        "error": None,
    }
