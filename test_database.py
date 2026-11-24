"""Testes básicos da camada SQLite do FinanCerto."""

import tempfile
import unittest
from pathlib import Path

from database import FinanceDatabase, cents_to_brl, money_to_cents


class FinanceDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = FinanceDatabase(Path(self.temp_dir.name) / "test.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_money_conversion(self) -> None:
        self.assertEqual(money_to_cents("1.234,56"), 123456)
        self.assertEqual(money_to_cents("25.90"), 2590)
        self.assertEqual(cents_to_brl(123456), "R$ 1.234,56")

    def test_add_transaction_and_summary(self) -> None:
        salary = next(c for c in self.db.list_categories("RECEITA") if c["name"] == "Salário")
        food = next(c for c in self.db.list_categories("DESPESA") if c["name"] == "Alimentação")
        self.db.add_transaction("Salário de teste", 300000, "RECEITA", salary["id"], "2026-11-01")
        self.db.add_transaction("Mercado", 45000, "DESPESA", food["id"], "2026-11-02")
        summary = self.db.get_summary("2026-11-01", "2026-11-30")
        self.assertEqual(summary["income_cents"], 300000)
        self.assertEqual(summary["expenses_cents"], 45000)
        self.assertEqual(summary["balance_cents"], 255000)

    def test_type_and_category_must_match(self) -> None:
        salary = next(c for c in self.db.list_categories("RECEITA") if c["name"] == "Salário")
        with self.assertRaises(Exception):
            self.db.add_transaction("Erro de categoria", 1000, "DESPESA", salary["id"], "2026-11-03")


if __name__ == "__main__":
    unittest.main(verbosity=2)
