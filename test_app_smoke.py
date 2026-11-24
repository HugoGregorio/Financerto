"""Teste básico de inicialização/navegação da interface (requer display Tk)."""

import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk
except Exception:  # pragma: no cover - ambiente sem Tk
    tk = None

from app import FinanCertoApp


@unittest.skipIf(tk is None, "Tkinter não está disponível")
class AppSmokeTests(unittest.TestCase):
    def test_app_pages_render_and_navigate(self):
        # Em ambientes sem servidor gráfico (por exemplo, CI/headless), pule o teste de Tk.
        try:
            probe = tk.Tk()
            probe.withdraw()
            probe.destroy()
        except tk.TclError:
            self.skipTest("Não há ambiente gráfico disponível para testar Tkinter")

        with tempfile.TemporaryDirectory() as folder:
            app = FinanCertoApp(str(Path(folder) / "ui-test.db"))
            try:
                app.update_idletasks()
                self.assertEqual(app.current_page, "dashboard")
                app.show_transactions()
                app.update_idletasks()
                self.assertEqual(app.current_page, "transactions")
                app.show_categories()
                app.update_idletasks()
                self.assertEqual(app.current_page, "categories")
                app.show_dashboard()
                app.update_idletasks()
                self.assertEqual(app.current_page, "dashboard")
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
