"""Interface desktop do FinanCerto, desenvolvida com Tkinter.

Execute com: py app.py (Windows) ou python app.py (outros sistemas)
Requer Python 3.10+ e Tkinter (biblioteca padrão do Python).
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from database import (
    DatabaseError,
    FinanceDatabase,
    cents_to_brl,
    money_to_cents,
    validate_iso_date,
)


# Paleta simples para manter a interface consistente e legível.
COLORS = {
    "background": "#F3F6FA",
    "surface": "#FFFFFF",
    "sidebar": "#172B4D",
    "sidebar_text": "#DCE6F2",
    "primary": "#176B5B",
    "primary_hover": "#115448",
    "text": "#172B4D",
    "muted": "#66758A",
    "border": "#E1E7EF",
    "income": "#16845B",
    "expense": "#C24B4B",
    "soft_green": "#E8F5EF",
    "soft_red": "#FBEDED",
    "soft_blue": "#EAF0F8",
}

FONT = "Arial"


def month_range(month_text: str) -> tuple[str, str]:
    """Valida AAAA-MM e devolve o primeiro e o último dia do mês."""
    try:
        year_text, month_number_text = month_text.strip().split("-")
        year, month_number = int(year_text), int(month_number_text)
        first = date(year, month_number, 1)
    except (ValueError, TypeError) as exc:
        raise ValueError("Informe o mês no formato AAAA-MM, por exemplo 2026-11.") from exc

    if month_number == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month_number + 1, 1)
    last = date.fromordinal(next_month.toordinal() - 1)
    return first.isoformat(), last.isoformat()


def date_to_br(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
        return parsed.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return value


def database_transaction_payload(form_data: dict[str, Any]) -> dict[str, Any]:
    """Adapta os campos do formulário aos nomes esperados pela camada SQLite.

    A interface usa a chave ``type`` para exibir/editar o tipo do lançamento,
    enquanto FinanceDatabase recebe esse argumento como ``transaction_type``.
    """
    return {
        "description": form_data["description"],
        "amount_cents": form_data["amount_cents"],
        "transaction_type": form_data["type"],
        "category_id": form_data["category_id"],
        "transaction_date": form_data["transaction_date"],
        "notes": form_data.get("notes", ""),
    }


class TransactionDialog(tk.Toplevel):
    """Janela de cadastro/edição de uma movimentação."""

    def __init__(
        self,
        parent: "FinanCertoApp",
        db: FinanceDatabase,
        transaction: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.parent_app = parent
        self.db = db
        self.transaction = transaction
        self.result: dict[str, Any] | None = None
        self.title("Editar lançamento" if transaction else "Novo lançamento")
        self.configure(bg=COLORS["background"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.type_var = tk.StringVar(value=(transaction or {}).get("type", "DESPESA"))
        self.category_var = tk.StringVar()
        self.description_var = tk.StringVar(value=(transaction or {}).get("description", ""))
        self.amount_var = tk.StringVar(
            value=(
                f"{transaction['amount_cents'] // 100},{transaction['amount_cents'] % 100:02d}"
                if transaction else ""
            )
        )
        self.date_var = tk.StringVar(value=(transaction or {}).get("transaction_date", date.today().isoformat()))
        self.notes_var = tk.StringVar(value=(transaction or {}).get("notes", ""))
        self.category_lookup: dict[str, int] = {}

        self._build()
        self._load_categories(
            selected_id=(transaction or {}).get("category_id")
        )
        self.update_idletasks()
        self._center(parent)

    def _center(self, parent: tk.Misc) -> None:
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _build(self) -> None:
        outer = tk.Frame(self, bg=COLORS["surface"], padx=26, pady=24)
        outer.pack(fill="both", expand=True)
        tk.Label(
            outer,
            text="Dados da movimentação",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=(FONT, 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        self._field_label(outer, "Tipo", 1, 0)
        type_box = ttk.Combobox(
            outer, textvariable=self.type_var,
            values=("DESPESA", "RECEITA"), state="readonly", width=32,
        )
        type_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._load_categories())

        self._field_label(outer, "Descrição", 3, 0)
        description_entry = ttk.Entry(outer, textvariable=self.description_var, width=38)
        description_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._field_label(outer, "Valor (R$)", 5, 0)
        self._field_label(outer, "Data (AAAA-MM-DD)", 5, 1)
        ttk.Entry(outer, textvariable=self.amount_var, width=17).grid(
            row=6, column=0, sticky="ew", padx=(0, 8), pady=(0, 12)
        )
        ttk.Entry(outer, textvariable=self.date_var, width=19).grid(
            row=6, column=1, sticky="ew", padx=(8, 0), pady=(0, 12)
        )

        self._field_label(outer, "Categoria", 7, 0)
        self.category_box = ttk.Combobox(
            outer, textvariable=self.category_var, state="readonly", width=36
        )
        self.category_box.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._field_label(outer, "Observações", 9, 0)
        ttk.Entry(outer, textvariable=self.notes_var, width=38).grid(
            row=10, column=0, columnspan=2, sticky="ew", pady=(0, 20)
        )

        buttons = tk.Frame(outer, bg=COLORS["surface"])
        buttons.grid(row=11, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Salvar lançamento", style="Primary.TButton", command=self._save).pack(side="left")
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        description_entry.focus_set()

    @staticmethod
    def _field_label(parent: tk.Misc, text: str, row: int, column: int) -> None:
        tk.Label(
            parent, text=text, bg=COLORS["surface"], fg=COLORS["muted"],
            font=(FONT, 9, "bold"),
        ).grid(row=row, column=column, sticky="w", pady=(0, 5), padx=(0, 8) if column == 0 else (8, 0))

    def _load_categories(self, selected_id: int | None = None) -> None:
        categories = self.db.list_categories(self.type_var.get())
        self.category_lookup = {item["name"]: item["id"] for item in categories}
        names = list(self.category_lookup)
        self.category_box.configure(values=names)
        selected_name = next(
            (name for name, category_id in self.category_lookup.items() if category_id == selected_id),
            None,
        )
        self.category_var.set(selected_name or (names[0] if names else ""))

    def _save(self) -> None:
        try:
            description = self.description_var.get().strip()
            if not description:
                raise ValueError("Informe a descrição da movimentação.")
            amount_cents = money_to_cents(self.amount_var.get())
            transaction_date = validate_iso_date(self.date_var.get().strip())
            category_id = self.category_lookup.get(self.category_var.get())
            if category_id is None:
                raise ValueError("Selecione uma categoria válida.")

            self.result = {
                "description": description,
                "amount_cents": amount_cents,
                "type": self.type_var.get(),
                "category_id": category_id,
                "transaction_date": transaction_date,
                "notes": self.notes_var.get().strip(),
            }
            self.destroy()
        except ValueError as exc:
            messagebox.showwarning("Confira os dados", str(exc), parent=self)


class CategoryDialog(tk.Toplevel):
    """Janela para cadastrar uma categoria personalizada."""

    def __init__(self, parent: "FinanCertoApp") -> None:
        super().__init__(parent)
        self.result: tuple[str, str] | None = None
        self.title("Nova categoria")
        self.configure(bg=COLORS["surface"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = tk.Frame(self, bg=COLORS["surface"], padx=24, pady=22)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Cadastrar categoria", bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 15, "bold")).pack(anchor="w", pady=(0, 16))
        tk.Label(frame, text="Nome", bg=COLORS["surface"], fg=COLORS["muted"],
                 font=(FONT, 9, "bold")).pack(anchor="w")
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(frame, textvariable=self.name_var, width=34)
        name_entry.pack(fill="x", pady=(5, 12))
        tk.Label(frame, text="Tipo", bg=COLORS["surface"], fg=COLORS["muted"],
                 font=(FONT, 9, "bold")).pack(anchor="w")
        self.type_var = tk.StringVar(value="DESPESA")
        ttk.Combobox(frame, textvariable=self.type_var, values=("DESPESA", "RECEITA"),
                     state="readonly", width=31).pack(fill="x", pady=(5, 18))
        actions = tk.Frame(frame, bg=COLORS["surface"])
        actions.pack(anchor="e")
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Salvar categoria", style="Primary.TButton", command=self._save).pack(side="left")
        name_entry.focus_set()

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Campo obrigatório", "Informe o nome da categoria.", parent=self)
            return
        self.result = (name, self.type_var.get())
        self.destroy()


class FinanCertoApp(tk.Tk):
    def __init__(self, db_path: str | None = None) -> None:
        super().__init__()
        self.title("FinanCerto | Gestão Financeira Pessoal")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg=COLORS["background"])
        self.db = FinanceDatabase(db_path) if db_path else FinanceDatabase()
        self.current_page = "dashboard"
        self._configure_styles()
        self._build_shell()
        self.show_dashboard()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TEntry", padding=8, fieldbackground=COLORS["surface"], font=(FONT, 10))
        style.configure("TCombobox", padding=7, font=(FONT, 10))
        style.configure("TButton", padding=(12, 8), font=(FONT, 9, "bold"))
        style.configure("Primary.TButton", background=COLORS["primary"], foreground="white")
        style.map("Primary.TButton", background=[("active", COLORS["primary_hover"])])
        style.configure(
            "Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
            foreground=COLORS["text"], rowheight=34, font=(FONT, 9), borderwidth=0,
        )
        style.configure(
            "Treeview.Heading", background=COLORS["soft_blue"], foreground=COLORS["text"],
            font=(FONT, 9, "bold"), padding=9, relief="flat",
        )
        style.map("Treeview", background=[("selected", "#DCEBE6")], foreground=[("selected", COLORS["text"])])

    def _build_shell(self) -> None:
        shell = tk.Frame(self, bg=COLORS["background"])
        shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(shell, bg=COLORS["sidebar"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="FinanCerto", bg=COLORS["sidebar"], fg="white",
                 font=(FONT, 20, "bold")).pack(anchor="w", padx=24, pady=(28, 3))
        tk.Label(self.sidebar, text="GESTÃO FINANCEIRA PESSOAL", bg=COLORS["sidebar"],
                 fg="#9FB1C8", font=(FONT, 7, "bold")).pack(anchor="w", padx=25, pady=(0, 32))

        self.nav_buttons: dict[str, tk.Button] = {}
        nav_items = [
            ("dashboard", "▦   Visão geral"),
            ("transactions", "⇄   Lançamentos"),
            ("categories", "▤   Categorias"),
        ]
        for key, label in nav_items:
            button = tk.Button(
                self.sidebar, text=label, anchor="w", relief="flat", bd=0,
                bg=COLORS["sidebar"], fg=COLORS["sidebar_text"], activebackground="#294365",
                activeforeground="white", font=(FONT, 10), padx=22, pady=13,
                command=lambda page=key: self.navigate(page), cursor="hand2",
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button

        footer = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        footer.pack(side="bottom", fill="x", padx=24, pady=22)
        tk.Label(footer, text="DADOS ARMAZENADOS LOCALMENTE", bg=COLORS["sidebar"],
                 fg="#9FB1C8", font=(FONT, 7, "bold")).pack(anchor="w")
        tk.Label(footer, text="Python  •  SQLite", bg=COLORS["sidebar"],
                 fg=COLORS["sidebar_text"], font=(FONT, 9)).pack(anchor="w", pady=(5, 0))

        self.main = tk.Frame(shell, bg=COLORS["background"])
        self.main.pack(side="left", fill="both", expand=True)

    def navigate(self, page: str) -> None:
        if page == "dashboard":
            self.show_dashboard()
        elif page == "transactions":
            self.show_transactions()
        elif page == "categories":
            self.show_categories()

    def _prepare_page(self, page: str, title: str, subtitle: str) -> tk.Frame:
        self.current_page = page
        for child in self.main.winfo_children():
            child.destroy()
        for key, button in self.nav_buttons.items():
            active = key == page
            button.configure(bg="#294365" if active else COLORS["sidebar"],
                             fg="white" if active else COLORS["sidebar_text"])

        wrapper = tk.Frame(self.main, bg=COLORS["background"], padx=30, pady=26)
        wrapper.pack(fill="both", expand=True)
        top = tk.Frame(wrapper, bg=COLORS["background"])
        top.pack(fill="x", pady=(0, 22))
        title_box = tk.Frame(top, bg=COLORS["background"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(title_box, text=title, bg=COLORS["background"], fg=COLORS["text"],
                 font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(title_box, text=subtitle, bg=COLORS["background"], fg=COLORS["muted"],
                 font=(FONT, 9)).pack(anchor="w", pady=(5, 0))
        return wrapper

    @staticmethod
    def _card(parent: tk.Misc, title: str, value: str, subtitle: str, accent: str) -> tk.Frame:
        card = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        stripe = tk.Frame(card, bg=accent, height=4)
        stripe.pack(fill="x")
        body = tk.Frame(card, bg=COLORS["surface"], padx=18, pady=15)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title.upper(), bg=COLORS["surface"], fg=COLORS["muted"],
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(body, text=value, bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 18, "bold")).pack(anchor="w", pady=(8, 3))
        tk.Label(body, text=subtitle, bg=COLORS["surface"], fg=COLORS["muted"],
                 font=(FONT, 8)).pack(anchor="w")
        return card

    def show_dashboard(self) -> None:
        wrapper = self._prepare_page("dashboard", "Visão geral", "Acompanhe o resumo das suas finanças.")
        controls = tk.Frame(wrapper, bg=COLORS["background"])
        controls.pack(fill="x", pady=(0, 16))
        tk.Label(controls, text="Mês de referência", bg=COLORS["background"], fg=COLORS["muted"],
                 font=(FONT, 9, "bold")).pack(side="left", padx=(0, 8))
        month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        month_entry = ttk.Entry(controls, textvariable=month_var, width=10)
        month_entry.pack(side="left")
        ttk.Button(controls, text="Atualizar", command=lambda: self._refresh_dashboard(month_var.get(), wrapper)).pack(side="left", padx=8)
        ttk.Button(controls, text="+ Novo lançamento", style="Primary.TButton",
                   command=self.open_transaction_dialog).pack(side="right")
        self._refresh_dashboard(month_var.get(), wrapper, create=True)

    def _refresh_dashboard(self, month_text: str, wrapper: tk.Frame, create: bool = False) -> None:
        try:
            start, end = month_range(month_text)
        except ValueError as exc:
            messagebox.showwarning("Mês inválido", str(exc), parent=self)
            return

        # Limpa apenas o conteúdo variável abaixo dos controles.
        if create:
            data_area = tk.Frame(wrapper, bg=COLORS["background"])
            data_area.pack(fill="both", expand=True)
        else:
            children = wrapper.winfo_children()
            data_area = children[-1] if children else None
            if data_area is None:
                return
            for child in data_area.winfo_children():
                child.destroy()

        summary = self.db.get_summary(start, end)
        cards = tk.Frame(data_area, bg=COLORS["background"])
        cards.pack(fill="x", pady=(0, 18))
        balance = summary["balance_cents"]
        card_data = [
            ("Saldo do mês", cents_to_brl(balance), "Receitas menos despesas", COLORS["primary"]),
            ("Receitas", cents_to_brl(summary["income_cents"]), "Entradas no período", COLORS["income"]),
            ("Despesas", cents_to_brl(summary["expenses_cents"]), "Saídas no período", COLORS["expense"]),
        ]
        for index, (title, value, subtitle, accent) in enumerate(card_data):
            card = self._card(cards, title, value, subtitle, accent)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 7 if index < 2 else 0))
            cards.columnconfigure(index, weight=1, uniform="cards")

        lower = tk.Frame(data_area, bg=COLORS["background"])
        lower.pack(fill="both", expand=True)
        chart_panel = tk.Frame(lower, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        chart_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))
        recent_panel = tk.Frame(lower, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        recent_panel.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(chart_panel, text="Despesas por categoria", bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(chart_panel, text="Distribuição dos gastos no mês selecionado", bg=COLORS["surface"],
                 fg=COLORS["muted"], font=(FONT, 8)).pack(anchor="w", padx=18)
        chart = tk.Canvas(chart_panel, height=245, bg=COLORS["surface"], highlightthickness=0)
        chart.pack(fill="both", expand=True, padx=12, pady=12)
        chart.bind("<Configure>", lambda event, canvas=chart, s=start, e=end: self._draw_expense_chart(canvas, s, e))
        self._draw_expense_chart(chart, start, end)

        tk.Label(recent_panel, text="Últimos lançamentos", bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        latest = self.db.list_transactions(start, end)[:6]
        if not latest:
            tk.Label(recent_panel, text="Nenhuma movimentação registrada neste mês.",
                     bg=COLORS["surface"], fg=COLORS["muted"], font=(FONT, 9),
                     wraplength=300, justify="left").pack(anchor="w", padx=18, pady=12)
        else:
            for item in latest:
                row = tk.Frame(recent_panel, bg=COLORS["surface"])
                row.pack(fill="x", padx=18, pady=8)
                left = tk.Frame(row, bg=COLORS["surface"])
                left.pack(side="left", fill="x", expand=True)
                tk.Label(left, text=item["description"], bg=COLORS["surface"], fg=COLORS["text"],
                         font=(FONT, 9, "bold")).pack(anchor="w")
                tk.Label(left, text=f"{item['category_name']}  •  {date_to_br(item['transaction_date'])}",
                         bg=COLORS["surface"], fg=COLORS["muted"], font=(FONT, 8)).pack(anchor="w", pady=(3, 0))
                sign = "+ " if item["type"] == "RECEITA" else "− "
                color = COLORS["income"] if item["type"] == "RECEITA" else COLORS["expense"]
                tk.Label(row, text=sign + cents_to_brl(item["amount_cents"]), bg=COLORS["surface"],
                         fg=color, font=(FONT, 9, "bold")).pack(side="right", padx=(8, 0))
                tk.Frame(recent_panel, bg=COLORS["border"], height=1).pack(fill="x", padx=18)

    def _draw_expense_chart(self, canvas: tk.Canvas, start: str, end: str) -> None:
        canvas.delete("all")
        try:
            expenses = [item for item in self.db.list_transactions(start, end, "DESPESA")]
        except Exception:
            return
        totals: dict[str, int] = {}
        for item in expenses:
            totals[item["category_name"]] = totals.get(item["category_name"], 0) + item["amount_cents"]
        top_items = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:6]
        width = max(canvas.winfo_width(), 320)
        if not top_items:
            canvas.create_text(width / 2, 100, text="Sem despesas para exibir", fill=COLORS["muted"],
                               font=(FONT, 10))
            return
        max_value = max(value for _, value in top_items) or 1
        y = 18
        label_width = 105
        bar_width = max(80, width - label_width - 115)
        for name, value in top_items:
            canvas.create_text(8, y + 10, anchor="w", text=name[:17], fill=COLORS["text"], font=(FONT, 8))
            canvas.create_rectangle(label_width, y + 3, label_width + bar_width, y + 19,
                                    fill="#EEF2F6", outline="")
            fill_width = bar_width * value / max_value
            canvas.create_rectangle(label_width, y + 3, label_width + fill_width, y + 19,
                                    fill=COLORS["primary"], outline="")
            canvas.create_text(label_width + bar_width + 8, y + 11, anchor="w",
                               text=cents_to_brl(value), fill=COLORS["muted"], font=(FONT, 8))
            y += 34

    def show_transactions(self) -> None:
        wrapper = self._prepare_page("transactions", "Lançamentos", "Consulte, filtre, edite ou exclua movimentações.")
        toolbar = tk.Frame(wrapper, bg=COLORS["surface"], padx=14, pady=14,
                           highlightbackground=COLORS["border"], highlightthickness=1)
        toolbar.pack(fill="x", pady=(0, 14))
        self.search_var = tk.StringVar()
        self.month_filter_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self.type_filter_var = tk.StringVar(value="Todos")
        ttk.Entry(toolbar, textvariable=self.search_var, width=27).pack(side="left", padx=(0, 8))
        ttk.Entry(toolbar, textvariable=self.month_filter_var, width=10).pack(side="left", padx=4)
        ttk.Combobox(toolbar, textvariable=self.type_filter_var,
                     values=("Todos", "RECEITA", "DESPESA"), state="readonly", width=12).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Filtrar", command=self._refresh_transaction_table).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Limpar", command=self._clear_transaction_filters).pack(side="left", padx=3)
        ttk.Button(toolbar, text="+ Novo lançamento", style="Primary.TButton",
                   command=self.open_transaction_dialog).pack(side="right")

        table_panel = tk.Frame(wrapper, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        table_panel.pack(fill="both", expand=True)
        actions = tk.Frame(table_panel, bg=COLORS["surface"], padx=14, pady=12)
        actions.pack(fill="x")
        tk.Label(actions, text="Movimentações registradas", bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 11, "bold")).pack(side="left")
        ttk.Button(actions, text="Excluir selecionado", command=self.delete_selected_transaction).pack(side="right")
        ttk.Button(actions, text="Editar selecionado", command=self.edit_selected_transaction).pack(side="right", padx=8)

        columns = ("date", "description", "category", "type", "amount")
        self.transaction_tree = ttk.Treeview(table_panel, columns=columns, show="headings", selectmode="browse")
        headings = {"date": "Data", "description": "Descrição", "category": "Categoria",
                    "type": "Tipo", "amount": "Valor"}
        widths = {"date": 105, "description": 260, "category": 170, "type": 100, "amount": 135}
        for column in columns:
            self.transaction_tree.heading(column, text=headings[column])
            self.transaction_tree.column(column, width=widths[column], anchor="w" if column in ("description", "category") else "center")
        self.transaction_tree.column("amount", anchor="e")
        self.transaction_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._refresh_transaction_table()

    def _refresh_transaction_table(self) -> None:
        if not hasattr(self, "transaction_tree") or not self.transaction_tree.winfo_exists():
            return
        month = self.month_filter_var.get().strip()
        try:
            start, end = month_range(month)
            type_value = self.type_filter_var.get()
            records = self.db.list_transactions(start, end, None if type_value == "Todos" else type_value)
        except ValueError as exc:
            messagebox.showwarning("Filtro inválido", str(exc), parent=self)
            return
        query = self.search_var.get().strip().casefold()
        for item in self.transaction_tree.get_children():
            self.transaction_tree.delete(item)
        for record in records:
            searchable = f"{record['description']} {record['category_name']}".casefold()
            if query and query not in searchable:
                continue
            self.transaction_tree.insert(
                "", "end", iid=str(record["id"]),
                values=(date_to_br(record["transaction_date"]), record["description"],
                        record["category_name"], "Receita" if record["type"] == "RECEITA" else "Despesa",
                        cents_to_brl(record["amount_cents"])),
            )

    def _clear_transaction_filters(self) -> None:
        self.search_var.set("")
        self.month_filter_var.set(date.today().strftime("%Y-%m"))
        self.type_filter_var.set("Todos")
        self._refresh_transaction_table()

    def _selected_transaction(self) -> dict[str, Any] | None:
        if not hasattr(self, "transaction_tree"):
            return None
        selection = self.transaction_tree.selection()
        if not selection:
            messagebox.showinfo("Selecione um lançamento", "Selecione uma movimentação na tabela.", parent=self)
            return None
        transaction_id = int(selection[0])
        return next((item for item in self.db.list_transactions() if item["id"] == transaction_id), None)

    def edit_selected_transaction(self) -> None:
        transaction = self._selected_transaction()
        if transaction:
            self.open_transaction_dialog(transaction)

    def delete_selected_transaction(self) -> None:
        transaction = self._selected_transaction()
        if not transaction:
            return
        confirm = messagebox.askyesno(
            "Confirmar exclusão",
            f"Deseja excluir o lançamento '{transaction['description']}'?",
            parent=self,
        )
        if confirm:
            try:
                self.db.delete_transaction(transaction["id"])
                self._refresh_transaction_table()
                messagebox.showinfo("Lançamento excluído", "A movimentação foi excluída.", parent=self)
            except DatabaseError as exc:
                messagebox.showerror("Não foi possível excluir", str(exc), parent=self)

    def open_transaction_dialog(self, transaction: dict[str, Any] | None = None) -> None:
        dialog = TransactionDialog(self, self.db, transaction)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        data = database_transaction_payload(dialog.result)
        try:
            if transaction:
                self.db.update_transaction(transaction["id"], **data)
                message = "Lançamento atualizado com sucesso."
            else:
                self.db.add_transaction(**data)
                message = "Lançamento cadastrado com sucesso."
            messagebox.showinfo("FinanCerto", message, parent=self)
            self.navigate(self.current_page)
        except (ValueError, DatabaseError) as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=self)

    def show_categories(self) -> None:
        wrapper = self._prepare_page("categories", "Categorias", "Organize as movimentações por tipo de receita ou despesa.")
        toolbar = tk.Frame(wrapper, bg=COLORS["background"])
        toolbar.pack(fill="x", pady=(0, 14))
        ttk.Button(toolbar, text="+ Nova categoria", style="Primary.TButton",
                   command=self.open_category_dialog).pack(side="right")
        panel = tk.Frame(wrapper, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="Categorias disponíveis", bg=COLORS["surface"], fg=COLORS["text"],
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=16, pady=14)
        columns = ("name", "type")
        self.category_tree = ttk.Treeview(panel, columns=columns, show="headings")
        self.category_tree.heading("name", text="Nome da categoria")
        self.category_tree.heading("type", text="Classificação")
        self.category_tree.column("name", width=400, anchor="w")
        self.category_tree.column("type", width=180, anchor="center")
        self.category_tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for category in self.db.list_categories():
            self.category_tree.insert("", "end", values=(category["name"],
                                        "Receita" if category["type"] == "RECEITA" else "Despesa"))

    def open_category_dialog(self) -> None:
        dialog = CategoryDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            try:
                self.db.add_category(*dialog.result)
                self.show_categories()
            except (ValueError, DatabaseError) as exc:
                messagebox.showerror("Não foi possível cadastrar", str(exc), parent=self)


def main() -> None:
    app = FinanCertoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
