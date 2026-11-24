"""Testes de integração entre os dados do formulário e o SQLite."""

import tempfile
import unittest
from pathlib import Path

from app import database_transaction_payload
from database import FinanceDatabase


class TransactionPayloadTests(unittest.TestCase):
    def test_create_and_update_transaction_from_form_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            db = FinanceDatabase(Path(folder) / "integration.db")
            category = next(c for c in db.list_categories("DESPESA") if c["name"] == "Alimentação")
            form_data = {
                "description": "Compra de mercado",
                "amount_cents": 12590,
                "type": "DESPESA",
                "category_id": category["id"],
                "transaction_date": "2026-11-23",
                "notes": "Teste de persistência",
            }

            payload = database_transaction_payload(form_data)
            transaction_id = db.add_transaction(**payload)
            saved = db.list_transactions()
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["description"], "Compra de mercado")
            self.assertEqual(saved[0]["amount_cents"], 12590)

            form_data["description"] = "Mercado atualizado"
            db.update_transaction(transaction_id, **database_transaction_payload(form_data))
            updated = db.list_transactions()[0]
            self.assertEqual(updated["description"], "Mercado atualizado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
