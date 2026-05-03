import csv
import shutil
from sqlalchemy import text
from database.models import Expense, Gain, Transfer


def export_data_to_csv(db_session, filepath):
    """Pure logic to export database contents to a detailed CSV file."""
    try:
        expenses = db_session.query(Expense).all()
        gains = db_session.query(Gain).all()
        transfers = db_session.query(Transfer).all()

        all_transactions = []

        # --- 1. Process Expenses ---
        for e in expenses:
            entity = e.vendor.name if e.vendor else "Unknown Vendor"
            cat_stream = e.category.name if e.category else "Uncategorized"
            acc_pm = e.payment_method.name if e.payment_method else "Unknown PM"
            project = e.project.name if e.project else ""
            split = f"Yes ({e.split_num_instalments})" if e.split_bool else "No"

            all_transactions.append([
                "Expense",
                e.timestamp.strftime('%Y-%m-%d %H:%M'),
                entity,
                cat_stream,
                acc_pm,
                project,
                f"-{e.amount:.2f}",
                e.currency_code,
                e.fx_rate if e.fx_rate else 1.0,
                f"-{e.converted_amount:.2f}",
                split,
                e.description or ""
            ])

        # --- 2. Process Gains ---
        for g in gains:
            entity = g.payer.name if g.payer else "Unknown Payer"
            cat_stream = g.stream.name if g.stream else "Uncategorized"
            acc_pm = g.account.name if g.account else "Unknown Account"
            project = g.project.name if g.project else ""
            split = f"Yes ({g.split_num_instalments})" if g.split_bool else "No"

            all_transactions.append([
                "Income",
                g.timestamp.strftime('%Y-%m-%d %H:%M'),
                entity,
                cat_stream,
                acc_pm,
                project,
                f"+{g.amount:.2f}",
                g.currency_code,
                g.fx_rate if g.fx_rate else 1.0,
                f"+{g.converted_amount:.2f}",
                split,
                g.description or ""
            ])

        # --- 3. Process Transfers ---
        for t in transfers:
            acc_pm = f"{t.origin_account.name} -> {t.destination_account.name}" if (
                        t.origin_account and t.destination_account) else "Unknown Transfer"
            currency = t.origin_account.currency_code if t.origin_account else "EUR"

            all_transactions.append([
                "Transfer",
                t.timestamp.strftime('%Y-%m-%d %H:%M'),
                "Internal",
                "Transfer",
                acc_pm,
                "",  # No project for transfers currently
                f"{t.amount_origin:.2f}",
                currency,
                "",  # No specific FX rate stored directly on Transfer
                f"{t.amount_destination:.2f}",  # You can log destination amount here
                "No",
                t.description or ""
            ])

        # --- 4. Sort and Write ---
        # Sort by date (Index 1), newest first
        all_transactions.sort(key=lambda x: x[1], reverse=True)

        with open(filepath, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Write the header row
            writer.writerow([
                "Type", "Date", "Entity (Vendor/Payer)", "Category/Stream",
                "Account/PM", "Project", "Original Amount", "Currency",
                "FX Rate", "Amount (EUR/Dest)", "Split", "Description"
            ])
            # Write the data
            writer.writerows(all_transactions)

        return True, f"Successfully exported {len(all_transactions)} transactions!"

    except Exception as e:
        return False, f"An error occurred during export:\n{e}"

def backup_sqlite_db(db_session, source_db_path, dest_filepath):
    """Pure logic to force a WAL checkpoint and copy the database file."""
    try:
        # Force SQLite to merge the WAL file into the main database
        db_session.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
        db_session.commit()

        # Safely copy the updated main database file
        shutil.copy2(source_db_path, dest_filepath)

        return True, "Your database has been safely backed up."

    except Exception as e:
        return False, f"An error occurred during backup:\n{e}"