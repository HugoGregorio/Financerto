"""Camada de persistência do FinanCerto (Python + SQLite).

Os valores monetários são armazenados em centavos (inteiros), por exemplo:
R$ 25,90 -> 2590. Isso evita erros de precisão de ponto flutuante.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "financerto.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

DEFAULT_CATEGORIES = (
    ("Salário", "RECEITA"),
    ("Renda extra", "RECEITA"),
    ("Investimentos", "RECEITA"),
    ("Alimentação", "DESPESA"),
    ("Moradia", "DESPESA"),
    ("Transporte", "DESPESA"),
    ("Saúde", "DESPESA"),
    ("Educação", "DESPESA"),
    ("Lazer", "DESPESA"),
    ("Contas e serviços", "DESPESA"),
    ("Outros", "DESPESA"),
)


class DatabaseError(Exception):
    """Erro controlado relacionado aos dados do FinanCerto."""


def money_to_cents(value: str | int | float | Decimal) -> int:
    """Converte um valor monetário em reais para centavos, sem usar float internamente.

    Exemplos: "125,90" -> 12590; "125.90" -> 12590.
    """
    raw = str(value).strip().replace("R$", "").replace(" ", "")
    if not raw:
        raise ValueError("Informe um valor monetário.")

    # Aceita formatos brasileiros (1.234,56) e internacionais (1234.56).
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")

    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Valor monetário inválido.") from exc

    if not amount.is_finite() or amount <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    return int(amount * 100)


def cents_to_brl(cents: int) -> str:
    """Formata centavos como moeda brasileira, por exemplo R$ 1.234,56."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    whole, fractional = divmod(cents, 100)
    whole_text = f"{whole:,}".replace(",", ".")
    return f"{sign}R$ {whole_text},{fractional:02d}"


def validate_iso_date(value: str) -> str:
    """Valida e devolve uma data no formato AAAA-MM-DD."""
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Data inválida. Use o formato AAAA-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError("Data inválida. Use o formato AAAA-MM-DD.")
    return value


class FinanceDatabase:
    """Acesso ao banco de dados SQLite do FinanCerto."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Abre uma conexão SQLite e garante commit/rollback e fechamento."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Cria as tabelas, índices e categorias iniciais, se necessário."""
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Arquivo de estrutura não encontrado: {SCHEMA_PATH}")
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)
            connection.executemany(
                "INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)",
                DEFAULT_CATEGORIES,
            )

    def add_category(self, name: str, category_type: str) -> int:
        name = name.strip()
        category_type = category_type.upper().strip()
        if not name:
            raise ValueError("O nome da categoria é obrigatório.")
        if category_type not in {"RECEITA", "DESPESA"}:
            raise ValueError("O tipo deve ser RECEITA ou DESPESA.")
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO categories (name, type) VALUES (?, ?)",
                    (name, category_type),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("Já existe uma categoria com esse nome e tipo.") from exc

    def list_categories(self, category_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT id, name, type FROM categories"
        params: tuple[Any, ...] = ()
        if category_type:
            category_type = category_type.upper().strip()
            if category_type not in {"RECEITA", "DESPESA"}:
                raise ValueError("O tipo deve ser RECEITA ou DESPESA.")
            query += " WHERE type = ?"
            params = (category_type,)
        query += " ORDER BY name COLLATE NOCASE"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def add_transaction(
        self,
        description: str,
        amount_cents: int,
        transaction_type: str,
        category_id: int,
        transaction_date: str,
        notes: str = "",
    ) -> int:
        description = description.strip()
        transaction_type = transaction_type.upper().strip()
        if not description:
            raise ValueError("A descrição é obrigatória.")
        if transaction_type not in {"RECEITA", "DESPESA"}:
            raise ValueError("O tipo deve ser RECEITA ou DESPESA.")
        if not isinstance(amount_cents, int) or amount_cents <= 0:
            raise ValueError("O valor em centavos deve ser um inteiro maior que zero.")
        if not isinstance(category_id, int) or category_id <= 0:
            raise ValueError("Selecione uma categoria válida.")
        transaction_date = validate_iso_date(transaction_date)
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """INSERT INTO transactions
                       (description, amount_cents, type, category_id, transaction_date, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (description, amount_cents, transaction_type, category_id,
                     transaction_date, notes.strip()),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(
                "Não foi possível salvar. Verifique se a categoria corresponde ao tipo do lançamento."
            ) from exc

    def update_transaction(
        self,
        transaction_id: int,
        description: str,
        amount_cents: int,
        transaction_type: str,
        category_id: int,
        transaction_date: str,
        notes: str = "",
    ) -> None:
        description = description.strip()
        transaction_type = transaction_type.upper().strip()
        if not description:
            raise ValueError("A descrição é obrigatória.")
        if transaction_type not in {"RECEITA", "DESPESA"}:
            raise ValueError("O tipo deve ser RECEITA ou DESPESA.")
        if not isinstance(amount_cents, int) or amount_cents <= 0:
            raise ValueError("O valor em centavos deve ser um inteiro maior que zero.")
        transaction_date = validate_iso_date(transaction_date)
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """UPDATE transactions
                       SET description = ?, amount_cents = ?, type = ?, category_id = ?,
                           transaction_date = ?, notes = ?
                       WHERE id = ?""",
                    (description, amount_cents, transaction_type, category_id,
                     transaction_date, notes.strip(), transaction_id),
                )
                if cursor.rowcount == 0:
                    raise DatabaseError("Lançamento não encontrado.")
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("A categoria selecionada não corresponde ao tipo do lançamento.") from exc

    def delete_transaction(self, transaction_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,)
            )
            if cursor.rowcount == 0:
                raise DatabaseError("Lançamento não encontrado.")

    def list_transactions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        transaction_type: str | None = None,
        category_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if start_date:
            conditions.append("t.transaction_date >= ?")
            params.append(validate_iso_date(start_date))
        if end_date:
            conditions.append("t.transaction_date <= ?")
            params.append(validate_iso_date(end_date))
        if transaction_type:
            transaction_type = transaction_type.upper().strip()
            if transaction_type not in {"RECEITA", "DESPESA"}:
                raise ValueError("O tipo deve ser RECEITA ou DESPESA.")
            conditions.append("t.type = ?")
            params.append(transaction_type)
        if category_id is not None:
            conditions.append("t.category_id = ?")
            params.append(category_id)

        query = """SELECT t.id, t.description, t.amount_cents, t.type,
                          t.category_id, c.name AS category_name,
                          t.transaction_date, t.notes, t.created_at
                   FROM transactions t
                   JOIN categories c ON c.id = t.category_id"""
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY t.transaction_date DESC, t.id DESC"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def get_summary(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, int]:
        conditions: list[str] = []
        params: list[Any] = []
        if start_date:
            conditions.append("transaction_date >= ?")
            params.append(validate_iso_date(start_date))
        if end_date:
            conditions.append("transaction_date <= ?")
            params.append(validate_iso_date(end_date))
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""SELECT
                    COALESCE(SUM(CASE WHEN type = 'RECEITA' THEN amount_cents ELSE 0 END), 0) AS income,
                    COALESCE(SUM(CASE WHEN type = 'DESPESA' THEN amount_cents ELSE 0 END), 0) AS expenses
                  FROM transactions{where}"""
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        income = int(row["income"])
        expenses = int(row["expenses"])
        return {"income_cents": income, "expenses_cents": expenses,
                "balance_cents": income - expenses}
