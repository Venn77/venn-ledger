from sqlalchemy import func
from models import session, Account, Expense, Gain, Transfer, PaymentMethod
from decimal import Decimal, ROUND_HALF_UP


def run_global_audit():
    print(f"{'Account Name':<20} | {'Stored Bal':>12} | {'Calc Bal':>12} | {'Status':<10}")
    print("-" * 70)

    accounts = session.query(Account).all()

    for acc in accounts:
        # 1. Sum of Gains (Inflow)
        total_gains = session.query(func.sum(Gain.amount)).filter_by(account_id=acc.id).scalar() or 0

        # 2. Sum of Expenses (Outflow)
        total_expenses = (
                session.query(func.sum(Expense.amount))
                .join(PaymentMethod)
                .filter(PaymentMethod.account_id == acc.id)
                .scalar() or 0
            )

        # 3. Sum of Transfers
        transfers_in = session.query(func.sum(Transfer.amount_destination)).filter_by(
            destination_account_id=acc.id).scalar() or 0
        transfers_out = session.query(func.sum(Transfer.amount_origin)).filter_by(
            origin_account_id=acc.id).scalar() or 0

        # Theoretical Balance calculation
        # Starting balance (from when you created the account) + Inflows - Outflows
        calc_bal = Decimal(str(acc.initial_balance if acc.initial_balance else 0)) + \
                   Decimal(str(total_gains)) + \
                   Decimal(str(transfers_in)) - \
                   Decimal(str(total_expenses)) - \
                   Decimal(str(transfers_out))

        calc_bal = calc_bal.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        stored_bal = Decimal(str(acc.balance)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

        diff = stored_bal - calc_bal
        status = "✅ OK" if diff == 0 else f"❌ ERR ({diff})"

        print(f"{acc.name:<20} | {float(stored_bal):>12.2f} | {float(calc_bal):>12.2f} | {status}")


if __name__ == "__main__":
    run_global_audit()