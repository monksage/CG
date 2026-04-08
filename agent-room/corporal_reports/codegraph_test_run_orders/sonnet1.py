def process_bulk_orders(orders: list[Order], payment_method: str) -> dict:
    """
    Processes multiple orders in bulk using the given payment method.

    For each order:
      - Runs the validation chain
      - If valid, places the order via PlaceOrderCommand (confirm + reserve + pay)
      - Tracks success/failure per order

    Returns an aggregated report dict with:
      - "processed": total number of orders attempted
      - "succeeded": number of successfully paid orders
      - "failed": number of orders that failed (validation or payment)
      - "total_revenue": sum of totals for succeeded orders
      - "errors": dict mapping order_id to list of error messages
      - "succeeded_ids": list of order_ids that succeeded
      - "failed_ids": list of order_ids that failed
    """
    validator = build_validation_chain()
    warehouse = LegacyWarehouseAdapter(LegacyWarehouseAPI())
    history = OrderHistory()
    cmd_history = CommandHistory()

    succeeded = []
    failed = []
    errors: dict[int, list[str]] = {}

    for order in orders:
        validation_errors = validator.handle(order)
        if validation_errors:
            errors[order.order_id] = validation_errors
            failed.append(order.order_id)
            continue

        payment = PaymentProxy(payment_method)
        cmd = PlaceOrderCommand(order, payment, warehouse)
        try:
            cmd_history.push(cmd)
            history.add(order)
            succeeded.append(order.order_id)
        except Exception as exc:
            errors[order.order_id] = [str(exc)]
            failed.append(order.order_id)

    return {
        "processed": len(orders),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "total_revenue": history.total_revenue(),
        "errors": errors,
        "succeeded_ids": succeeded,
        "failed_ids": failed,
    }
