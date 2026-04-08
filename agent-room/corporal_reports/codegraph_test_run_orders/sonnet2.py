def process_bulk_orders(orders: list[Order], payment_method: str) -> dict:
    """
    Processes multiple orders in bulk using the given payment method.

    For each order:
      - Runs the full validation chain
      - If valid, places the order via PlaceOrderCommand (confirm + reserve + pay)
      - On payment failure, undoes via CommandHistory.pop_undo() to keep state consistent
      - Subscribes to "fraud_alert" to capture fraud-rejected payments per order

    Returns an aggregated report dict with:
      - "processed": total number of orders attempted
      - "succeeded": number of successfully paid orders
      - "failed": number of orders that failed (validation, payment, or fraud)
      - "total_revenue": sum of order.total for succeeded orders
      - "errors": dict mapping order_id -> list[str] of error messages
      - "succeeded_ids": list of order_ids that succeeded
      - "failed_ids": list of order_ids that failed
      - "fraud_detected": list of order_ids rejected due to fraud threshold
    """
    validator = build_validation_chain()
    warehouse = LegacyWarehouseAdapter()
    cmd_history = CommandHistory()
    event_bus = EventBus()

    succeeded_ids: list[int] = []
    failed_ids: list[int] = []
    fraud_ids: list[int] = []
    errors: dict[int, list[str]] = {}
    total_revenue: float = 0.0

    # Track fraud alerts raised during the current order execution.
    # PaymentProxy publishes "fraud_alert" before returning False,
    # so we intercept it to distinguish fraud-failures from other failures.
    _current_fraud: list[bool] = []

    def _on_fraud_alert(**data):
        _current_fraud.append(True)

    event_bus.subscribe("fraud_alert", _on_fraud_alert)

    for order in orders:
        # --- Validation ---
        validation_errors = validator.handle(order)
        if validation_errors:
            errors[order.order_id] = validation_errors
            failed_ids.append(order.order_id)
            continue

        # --- Execution ---
        _current_fraud.clear()
        payment = PaymentProxy(payment_method)
        cmd = PlaceOrderCommand(order, payment, warehouse)

        try:
            cmd_history.push(cmd)  # executes: confirm + reserve + pay
        except RuntimeError as exc:
            # Payment returned False (fraud or hard failure); undo everything.
            try:
                cmd_history.pop_undo()
            except IndexError:
                pass  # nothing pushed, nothing to undo

            if _current_fraud:
                fraud_ids.append(order.order_id)
                errors[order.order_id] = [f"fraud_alert: {exc}"]
            else:
                errors[order.order_id] = [str(exc)]
            failed_ids.append(order.order_id)
            continue
        except InvalidStateTransition as exc:
            # Order was already in an incompatible state.
            errors[order.order_id] = [f"invalid_transition: {exc}"]
            failed_ids.append(order.order_id)
            continue
        except Exception as exc:
            errors[order.order_id] = [str(exc)]
            failed_ids.append(order.order_id)
            continue

        succeeded_ids.append(order.order_id)
        total_revenue += order.total

    return {
        "processed": len(orders),
        "succeeded": len(succeeded_ids),
        "failed": len(failed_ids),
        "total_revenue": total_revenue,
        "errors": errors,
        "succeeded_ids": succeeded_ids,
        "failed_ids": failed_ids,
        "fraud_detected": fraud_ids,
    }
