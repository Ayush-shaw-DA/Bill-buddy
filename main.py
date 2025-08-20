import sys
import os
import sqlite3
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
import csv

"""
FMCG Billing Software (Sunil Stores) - Main Application Entry Point

This is the main file for the Sunil Stores Billing Software.
It implements a desktop-based billing and inventory management system using Python, PyQt5, and SQLite.

Modules:
- Item Master (Add/Edit Items, Units, Pricing)
- Billing (Sales, Fast Item Entry, Receipt Printing)
- Customer Management (Add/Edit Customers)
- Purchase Entry (Stock Inward)
- Stock Management (View/Adjust Stock, Export)
- Utility Features (Shortcuts, Export, Search)

Author: [Your Name]
Date: [2024-06-XX]
"""


# --- Database Initialization ---
DB_PATH = os.path.join(os.path.expanduser("~"), "sunilstores.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Items Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS Items (
        ItemID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Code TEXT UNIQUE,
        Category TEXT,
        HSN TEXT,
        BaseUnit TEXT NOT NULL,
        SecondaryUnit TEXT,
        ConversionRate REAL,
        RateA REAL NOT NULL,
        RateB REAL,
        RateC REAL,
        PurchaseRate REAL,
        StockQty REAL DEFAULT 0,
        AlertLevel REAL DEFAULT 0,
        ImagePath TEXT
    )
    """)
    # Customers Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS Customers (
        CustomerID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL UNIQUE,
        GSTIN TEXT,
        Area TEXT
    )
    """)
    # Purchases Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS Purchases (
        PurchaseID INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT,
        Supplier TEXT,
        ItemID INTEGER,
        Unit TEXT,
        Qty REAL,
        Rate REAL,
        FOREIGN KEY(ItemID) REFERENCES Items(ItemID)
    )
    """)
    # Stock Adjustments Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS StockAdjustments (
        AdjID INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT,
        ItemID INTEGER,
        QtyChange REAL,
        Unit TEXT,
        Reason TEXT,
        FOREIGN KEY(ItemID) REFERENCES Items(ItemID)
    )
    """)
    # Settings Table (for Bill Number)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Settings (
        Key TEXT PRIMARY KEY,
        Value TEXT
    )
    """)
    # Initialize Bill Number if not present
    c.execute("INSERT OR IGNORE INTO Settings (Key, Value) VALUES ('LastBillNo', '1000')")
    # Add BillNumbers table for daily bill numbers
    c.execute("""
    CREATE TABLE IF NOT EXISTS BillNumbers (
        BillDate TEXT PRIMARY KEY,
        LastBillNo INTEGER
    )
    """)
    conn.commit()
    conn.close()

# --- Utility Functions ---
def get_next_bill_no():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT Value FROM Settings WHERE Key='LastBillNo'")
    last_no = int(c.fetchone()[0])
    next_no = last_no + 1
    c.execute("UPDATE Settings SET Value=? WHERE Key='LastBillNo'", (str(next_no),))
    conn.commit()
    conn.close()
    return next_no

# --- Main Window ---
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sunil Stores Billing Software")
        self.setWindowIcon(QtGui.QIcon())  # Add your icon path if needed
        self.resize(1100, 700)
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tabs
        self.billing_tab = BillingTab()
        self.items_tab = ItemsTab()
        self.customers_tab = CustomersTab()
        self.purchases_tab = PurchasesTab()
        self.stock_tab = StockTab()

        self.tabs.addTab(self.billing_tab, "Billing (F1)")
        self.tabs.addTab(self.items_tab, "Items (F2)")
        self.tabs.addTab(self.purchases_tab, "Purchase Entry (F3)")
        self.tabs.addTab(self.stock_tab, "Stock (F4)")
        self.tabs.addTab(self.customers_tab, "Customers")

        # Shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("F1"), self, activated=lambda: self.tabs.setCurrentWidget(self.billing_tab))
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=lambda: self.tabs.setCurrentWidget(self.items_tab))
        QtWidgets.QShortcut(QtGui.QKeySequence("F3"), self, activated=lambda: self.tabs.setCurrentWidget(self.purchases_tab))
        QtWidgets.QShortcut(QtGui.QKeySequence("F4"), self, activated=lambda: self.tabs.setCurrentWidget(self.stock_tab))

# --- Billing Tab ---
class BillingTab(QtWidgets.QWidget):
    stock_updated = QtCore.pyqtSignal()  # Add this line at the top of BillingTab

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        # Bill Header
        header_panel = QtWidgets.QWidget()
        header_panel.setObjectName("billHeader")
        header_layout = QtWidgets.QHBoxLayout(header_panel)
        self.bill_no = QtWidgets.QLabel(f"Bill No: {get_next_bill_no()}")
        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setEditable(True)
        self.load_customers()
        self.date_edit = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.date_edit.setDisplayFormat("dd-MM-yyyy hh:mm AP")
        header_layout.addWidget(self.bill_no)
        header_layout.addWidget(QtWidgets.QLabel("Customer:"))
        header_layout.addWidget(self.customer_combo)
        header_layout.addWidget(QtWidgets.QLabel("Date:"))
        header_layout.addWidget(self.date_edit)
        layout.addWidget(header_panel)

        # Item Entry Table
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Item", "Unit", "Rate", "Qty", "Total", ""])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Manual Refresh Button
        refresh_btn = QtWidgets.QPushButton("Refresh Stock/Items")
        refresh_btn.setToolTip("Click to manually refresh the item list and stock info in case it does not update automatically.")
        refresh_btn.clicked.connect(self.manual_refresh)
        layout.addWidget(refresh_btn, alignment=QtCore.Qt.AlignLeft)

        self.add_item_row()

        # Bill Summary
        summary = QtWidgets.QHBoxLayout()
        self.subtotal_lbl = QtWidgets.QLabel("Subtotal: ₹0")
        self.totalqty_lbl = QtWidgets.QLabel("Total Qty: 0")
        self.discount_edit = QtWidgets.QLineEdit("0")
        self.discount_edit.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        self.discount_edit.setMaximumWidth(80)
        self.discount_edit.textChanged.connect(self.update_totals)
        self.grandtotal_lbl = QtWidgets.QLabel("Grand Total: ₹0")
        summary.addWidget(self.subtotal_lbl)
        summary.addWidget(self.totalqty_lbl)
        summary.addWidget(QtWidgets.QLabel("Discount:"))
        summary.addWidget(self.discount_edit)
        summary.addWidget(self.grandtotal_lbl)
        layout.addLayout(summary)

        # Print & Finish Button
        self.print_btn = QtWidgets.QPushButton("Print & Finish")
        self.print_btn.clicked.connect(self.print_and_finish)
        layout.addWidget(self.print_btn, alignment=QtCore.Qt.AlignRight)

        # Connect the signal to refresh stock if parent is MainWindow
        self.stock_updated.connect(self._refresh_stock_tab)

        # Add F3 shortcut for editing price in billing table
        QtWidgets.QShortcut(QtGui.QKeySequence("F3"), self, activated=self.edit_selected_price)

        # Printer selection button
        printer_btn = QtWidgets.QPushButton("Select Printer")
        printer_btn.clicked.connect(self.select_printer)
        layout.addWidget(printer_btn, alignment=QtCore.Qt.AlignLeft)

    def _refresh_stock_tab(self):
        # Find the main window and call stock_tab.load_stock()
        mw = self.parentWidget()
        while mw and not isinstance(mw, MainWindow):
            mw = mw.parentWidget()
        if mw and hasattr(mw, "stock_tab"):
            mw.stock_tab.load_stock()

    def load_customers(self):
        self.customer_combo.clear()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name FROM Customers ORDER BY Name")
        customers = [row[0] for row in c.fetchall()]
        self.customer_combo.addItems([""] + customers)
        conn.close()

    def add_item_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Item Combo
        item_combo = QtWidgets.QComboBox()
        item_combo.setEditable(True)
        self.load_items(item_combo)
        item_combo.currentIndexChanged.connect(lambda: self.update_item_row(row, trigger="item"))
        item_combo.view().pressed.connect(lambda _: self.on_item_combo_clicked(item_combo))
        self.table.setCellWidget(row, 0, item_combo)
        # Unit Combo
        unit_combo = QtWidgets.QComboBox()
        unit_combo.currentIndexChanged.connect(lambda: self.update_item_row(row, trigger="unit"))
        self.table.setCellWidget(row, 1, unit_combo)
        # Rate Combo
        rate_combo = QtWidgets.QComboBox()
        rate_combo.currentIndexChanged.connect(lambda: self.update_item_row(row, trigger="rate"))
        self.table.setCellWidget(row, 2, rate_combo)
        # Qty Edit
        qty_edit = QtWidgets.QLineEdit("1")
        qty_edit.setValidator(QtGui.QDoubleValidator(0, 999999, 3))
        qty_edit.textChanged.connect(lambda: self.update_item_row(row, trigger="qty"))
        self.table.setCellWidget(row, 3, qty_edit)
        # Total Label
        total_lbl = QtWidgets.QLabel("0")
        self.table.setCellWidget(row, 4, total_lbl)
        # Remove Button
        remove_btn = QtWidgets.QPushButton("X")
        remove_btn.clicked.connect(lambda: self.remove_item_row(row))
        self.table.setCellWidget(row, 5, remove_btn)

    def load_items(self, combo):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name FROM Items ORDER BY Name")
        items = [row[0] for row in c.fetchall()]
        combo.addItems([""] + items)
        conn.close()

    def update_item_row(self, row, trigger="item"):
        item_combo = self.table.cellWidget(row, 0)
        unit_combo = self.table.cellWidget(row, 1)
        rate_widget = self.table.cellWidget(row, 2)
        qty_edit = self.table.cellWidget(row, 3)
        total_lbl = self.table.cellWidget(row, 4)
        item_name = item_combo.currentText()
        if not item_name:
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT BaseUnit, SecondaryUnit, ConversionRate, RateA, RateB, RateC FROM Items WHERE Name=?", (item_name,))
        rowdata = c.fetchone()
        conn.close()
        if not rowdata:
            return
        base, sec, conv, ratea, rateb, ratec = rowdata

        # --- Units ---
        prev_unit = unit_combo.currentText()
        unit_combo.blockSignals(True)
        unit_combo.clear()
        units = [base]
        if sec:
            units.append(sec)
        unit_combo.addItems(units)
        # Restore previous unit selection if possible
        if trigger == "unit" and prev_unit in units:
            unit_combo.setCurrentText(prev_unit)
        elif trigger != "unit" and prev_unit in units:
            unit_combo.setCurrentText(prev_unit)
        else:
            unit_combo.setCurrentIndex(0)
        unit_combo.blockSignals(False)

        # --- Rates ---
        rate = 0  # <-- Always initialize rate
        if isinstance(rate_widget, QtWidgets.QComboBox):
            prev_rate_index = rate_widget.currentIndex()
            rate_widget.blockSignals(True)
            rate_widget.clear()
            selected_unit = unit_combo.currentText() or base
            rates = []
            # Conversion logic: if selected unit is secondary, divide rates by conversion
            if selected_unit == sec and conv and conv != 0:
                if ratea is not None:
                    rates.append(f"Rate A: ₹{round(ratea/conv,2)}")
                if rateb is not None:
                    rates.append(f"Rate B: ₹{round(rateb/conv,2)}")
                if ratec is not None:
                    rates.append(f"Rate C: ₹{round(ratec/conv,2)}")
            else:
                if ratea is not None:
                    rates.append(f"Rate A: ₹{ratea}")
                if rateb is not None:
                    rates.append(f"Rate B: ₹{rateb}")
                if ratec is not None:
                    rates.append(f"Rate C: ₹{ratec}")
            rate_widget.addItems(rates)
            # Restore previous rate selection if possible
            if 0 <= prev_rate_index < len(rates):
                rate_widget.setCurrentIndex(prev_rate_index)
            else:
                rate_widget.setCurrentIndex(0)
            rate_widget.blockSignals(False)
            # Set rate from selected combo
            if rates:
                try:
                    rate = float(rate_widget.currentText().split("₹")[-1])
                except:
                    rate = 0
        elif isinstance(rate_widget, QtWidgets.QLabel):
            try:
                rate = float(rate_widget.text())
            except:
                rate = 0
        elif isinstance(rate_widget, QtWidgets.QLineEdit):
            try:
                rate = float(rate_widget.text())
            except:
                rate = 0

        # --- Total ---
        try:
            qty = float(qty_edit.text())
        except:
            qty = 0
        total = qty * rate
        total_lbl.setText(str(int(total) if total == int(total) else round(total, 2)))
        self.update_totals()
        # Auto-add a new row if this is the last row and has a valid item
        if row == self.table.rowCount() - 1:
            item_combo = self.table.cellWidget(row, 0)
            qty_edit = self.table.cellWidget(row, 3)
            if item_combo.currentText() and qty_edit.text() and float(qty_edit.text()) > 0:
                self.add_item_row()

    def remove_item_row(self, row):
        self.table.removeRow(row)
        self.update_totals()

    def update_totals(self):
        subtotal = 0
        totalqty = 0
        for row in range(self.table.rowCount()):
            total_lbl = self.table.cellWidget(row, 4)
            qty_edit = self.table.cellWidget(row, 3)
            try:
                subtotal += float(total_lbl.text())
                totalqty += float(qty_edit.text())
            except:
                pass
        self.subtotal_lbl.setText(f"Subtotal: ₹{subtotal}")
        self.totalqty_lbl.setText(f"Total Qty: {totalqty}")
        try:
            discount = float(self.discount_edit.text())
        except:
            discount = 0
        grand = subtotal - discount
        self.grandtotal_lbl.setText(f"Grand Total: ₹{grand}")

    def print_and_finish(self):
        # Gather bill data
        bill_no = self.bill_no.text().split(":")[1].strip()
        customer = self.customer_combo.currentText()
        date = self.date_edit.dateTime().toString("dd-MM-yyyy hh:mm AP")
        items = []
        for row in range(self.table.rowCount()):
            item = self.table.cellWidget(row, 0).currentText()
            unit = self.table.cellWidget(row, 1).currentText()
            rate_widget = self.table.cellWidget(row, 2)
            # Read rate from either combo, label, or lineedit
            if isinstance(rate_widget, QtWidgets.QComboBox):
                rate = rate_widget.currentText().split("₹")[-1]
            elif isinstance(rate_widget, QtWidgets.QLabel):
                rate = rate_widget.text()
            elif isinstance(rate_widget, QtWidgets.QLineEdit):
                rate = rate_widget.text()
            else:
                rate = "0"
            qty = self.table.cellWidget(row, 3).text()
            total = self.table.cellWidget(row, 4).text()
            if item and qty and float(qty) > 0:
                items.append((item, unit, qty, rate, total))
        subtotal = self.subtotal_lbl.text().split("₹")[-1]
        totalqty = self.totalqty_lbl.text().split(":")[-1].strip()
        discount = self.discount_edit.text()
        grand = self.grandtotal_lbl.text().split("₹")[-1]

        # Print receipt (simulate, or integrate with ESC/POS printer)
        try:
            print_receipt(bill_no, customer, date, items, totalqty, grand)
            for item, unit, qty, rate, total in items:
                update_stock(item, unit, -float(qty))
            self.bill_no.setText(f"Bill No: {get_next_bill_no()}")
            self.table.setRowCount(0)
            self.add_item_row()
            self.reload_all_item_combos()
            self.update_totals()
            self.stock_updated.emit()  # <-- Emit signal to refresh stock tab
            QtWidgets.QMessageBox.information(self, "Success", "Bill printed and stock updated.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Printing failed: {e}")

    def reload_all_item_combos(self):
        # Reload items in all item combo boxes in the billing table
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, 0)
            if isinstance(item_combo, QtWidgets.QComboBox):
                current = item_combo.currentText()
                self.load_items(item_combo)
                # Try to restore previous selection
                idx = item_combo.findText(current)
                if idx >= 0:
                    item_combo.setCurrentIndex(idx)

    def on_item_combo_clicked(self, combo):
        self.load_items(combo)

    def manual_refresh(self):
        """Manually refresh all item combos and stock info in the billing table."""
        self.reload_all_item_combos()
        QtWidgets.QMessageBox.information(self, "Refreshed", "Item list and stock info refreshed.")

    def edit_selected_price(self):
        row = self.table.currentRow()
        if row < 0:
            return
        rate_widget = self.table.cellWidget(row, 2)
        # If already editing, do nothing
        if isinstance(rate_widget, QtWidgets.QLineEdit):
            rate_widget.setFocus()
            return
        # Get current rate value
        if isinstance(rate_widget, QtWidgets.QComboBox):
            current_rate_str = rate_widget.currentText().split("₹")[-1]
        elif isinstance(rate_widget, QtWidgets.QLabel):
            current_rate_str = rate_widget.text()
        else:
            current_rate_str = ""
        # Replace with QLineEdit for editing
        new_rate_edit = QtWidgets.QLineEdit(current_rate_str)
        new_rate_edit.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        new_rate_edit.setStyleSheet("background:#fffbe6;")  # Visual indicator for custom price
        self.table.setCellWidget(row, 2, new_rate_edit)
        new_rate_edit.setFocus()
        new_rate_edit.editingFinished.connect(lambda: self.finish_edit_price(row, new_rate_edit))

    def finish_edit_price(self, row, edit):
        new_rate = edit.text()
        # Replace QLineEdit with QLabel showing custom price
        new_rate_lbl = QtWidgets.QLabel(new_rate)
        new_rate_lbl.setStyleSheet("background:#fffbe6; font-weight:bold; color:#1565c0;")
        self.table.setCellWidget(row, 2, new_rate_lbl)
        self.update_item_row(row, trigger="rate")

    def select_printer(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.printer = printer
            self.detect_printer_features(printer)
            QtWidgets.QMessageBox.information(self, "Printer Selected", f"Printer: {printer.printerName()}")
        else:
            self.printer = None

    def detect_printer_features(self, printer):
        # Example: Detect page size and color support
        page_size = printer.pageRect().size()
        color_supported = printer.colorMode() == QPrinter.Color
        msg = f"Page Size: {page_size.width()}x{page_size.height()} px\n"
        msg += f"Color Supported: {'Yes' if color_supported else 'No'}"
        QtWidgets.QMessageBox.information(self, "Printer Features", msg)

# --- Items Tab ---
class ItemsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        # Table of items
        self.table = QtWidgets.QTableWidget()
        layout.addWidget(self.table)
        # Add/Edit Buttons
        btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add New Item")
        add_btn.clicked.connect(self.add_item)
        edit_btn = QtWidgets.QPushButton("Edit Selected Item")
        edit_btn.clicked.connect(self.edit_item)
        btns.addWidget(add_btn)
        btns.addWidget(edit_btn)
        layout.addLayout(btns)
        self.load_items()

    def load_items(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name, Code, Category, BaseUnit, SecondaryUnit, RateA, RateB, RateC, StockQty, AlertLevel FROM Items")
        rows = c.fetchall()
        conn.close()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["Name", "Code", "Category", "BaseUnit", "SecondaryUnit", "RateA", "RateB", "RateC", "StockQty", "AlertLevel"])
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QtWidgets.QTableWidgetItem(str(val)))

    def add_item(self):
        dlg = ItemDialog()
        if dlg.exec_():
            self.load_items()

    def edit_item(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        dlg = ItemDialog(name)
        if dlg.exec_():
            self.load_items()

class ItemDialog(QtWidgets.QDialog):
    def __init__(self, item_name=None):
        super().__init__()
        self.setWindowTitle("Item Details")
        layout = QtWidgets.QFormLayout(self)

        unit_options = ["Bag", "Box", "Kg", "Piece", "Pcs", "Dozen", "Litre", "Gram", "Packet", "Bottle", "Meter", "Set", "Carton", "Roll", "Other"]

        self.name = QtWidgets.QLineEdit()
        self.code = QtWidgets.QLineEdit()
        self.category = QtWidgets.QLineEdit()
        self.hsn = QtWidgets.QLineEdit()
        self.baseunit = QtWidgets.QComboBox()
        self.baseunit.addItems(unit_options)
        self.baseunit.setEditable(True)
        self.secondaryunit = QtWidgets.QComboBox()
        self.secondaryunit.addItems([""] + unit_options)
        self.secondaryunit.setEditable(True)
        self.conversion = QtWidgets.QLineEdit()
        self.conversion.setValidator(QtGui.QDoubleValidator(0, 999999, 3))
        self.ratea = QtWidgets.QLineEdit()
        self.ratea.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        self.rateb = QtWidgets.QLineEdit()
        self.rateb.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        self.ratec = QtWidgets.QLineEdit()
        self.ratec.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        self.purchaserate = QtWidgets.QLineEdit()
        self.purchaserate.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        self.stockqty = QtWidgets.QLineEdit()
        self.stockqty.setValidator(QtGui.QDoubleValidator(0, 999999, 3))
        self.alertlevel = QtWidgets.QLineEdit()
        self.alertlevel.setValidator(QtGui.QDoubleValidator(0, 999999, 3))
        self.imagepath = QtWidgets.QLineEdit()

        # Display for converted rates
        self.converted_ratea = QtWidgets.QLabel("")
        self.converted_rateb = QtWidgets.QLabel("")
        self.converted_ratec = QtWidgets.QLabel("")

        # Connect for auto conversion
        self.baseunit.currentIndexChanged.connect(self.update_converted_rates)
        self.secondaryunit.currentIndexChanged.connect(self.update_converted_rates)
        self.conversion.textChanged.connect(self.update_converted_rates)
        self.ratea.textChanged.connect(self.update_converted_rates)
        self.rateb.textChanged.connect(self.update_converted_rates)
        self.ratec.textChanged.connect(self.update_converted_rates)

        layout.addRow("Name*", self.name)
        layout.addRow("Code", self.code)
        layout.addRow("Category", self.category)
        layout.addRow("HSN", self.hsn)
        layout.addRow("Base Unit*", self.baseunit)
        layout.addRow("Secondary Unit", self.secondaryunit)
        layout.addRow("Conversion Rate", self.conversion)
        layout.addRow("Sale Rate A*", self.ratea)
        layout.addRow("Sale Rate B", self.rateb)
        layout.addRow("Sale Rate C", self.ratec)
        layout.addRow("A in Secondary Unit", self.converted_ratea)
        layout.addRow("B in Secondary Unit", self.converted_rateb)
        layout.addRow("C in Secondary Unit", self.converted_ratec)
        layout.addRow("Purchase Rate", self.purchaserate)
        layout.addRow("Opening Stock", self.stockqty)
        layout.addRow("Stock Alert Level", self.alertlevel)
        layout.addRow("Image Path", self.imagepath)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)
        if item_name:
            self.load_item(item_name)
        self.update_converted_rates()

    def update_converted_rates(self):
        try:
            conv = float(self.conversion.text())
        except:
            conv = None
        sec_unit = self.secondaryunit.currentText()
        if not sec_unit or not conv or conv == 0:
            self.converted_ratea.setText("")
            self.converted_rateb.setText("")
            self.converted_ratec.setText("")
            return
        try:
            ra = float(self.ratea.text())
            self.converted_ratea.setText(f"{sec_unit}: {round(ra/conv,2)}")
        except:
            self.converted_ratea.setText("")
        try:
            rb = float(self.rateb.text())
            self.converted_rateb.setText(f"{sec_unit}: {round(rb/conv,2)}")
        except:
            self.converted_rateb.setText("")
        try:
            rc = float(self.ratec.text())
            self.converted_ratec.setText(f"{sec_unit}: {round(rc/conv,2)}")
        except:
            self.converted_ratec.setText("")

    def accept(self):
        # Validate and save
        if not self.name.text() or not self.baseunit.currentText() or not self.ratea.text():
            QtWidgets.QMessageBox.warning(self, "Validation", "Name, Base Unit, and Rate A are required.")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            if self.name.text() in [row[0] for row in c.execute("SELECT Name FROM Items")]:
                # Update
                c.execute("""
                UPDATE Items SET Code=?, Category=?, HSN=?, BaseUnit=?, SecondaryUnit=?, ConversionRate=?, RateA=?, RateB=?, RateC=?, PurchaseRate=?, StockQty=?, AlertLevel=?, ImagePath=?
                WHERE Name=?
                """, (self.code.text(), self.category.text(), self.hsn.text(), self.baseunit.currentText(), self.secondaryunit.currentText(),
                      self.conversion.text(), self.ratea.text(), self.rateb.text(), self.ratec.text(), self.purchaserate.text(),
                      self.stockqty.text(), self.alertlevel.text(), self.imagepath.text(), self.name.text()))
            else:
                # Insert
                c.execute("""
                INSERT INTO Items (Name, Code, Category, HSN, BaseUnit, SecondaryUnit, ConversionRate, RateA, RateB, RateC, PurchaseRate, StockQty, AlertLevel, ImagePath)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.name.text(), self.code.text(), self.category.text(), self.hsn.text(), self.baseunit.currentText(), self.secondaryunit.currentText(),
                      self.conversion.text(), self.ratea.text(), self.rateb.text(), self.ratec.text(), self.purchaserate.text(),
                      self.stockqty.text(), self.alertlevel.text(), self.imagepath.text()))
            conn.commit()
            super().accept()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Error", "Duplicate item code or name.")
        finally:
            conn.close()

    def load_item(self, name):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM Items WHERE Name=?", (name,))
        row = c.fetchone()
        conn.close()
        if row:
            _, n, code, cat, hsn, base, sec, conv, ra, rb, rc, pr, sq, al, img = row
            self.name.setText(n)
            self.code.setText(code or "")
            self.category.setText(cat or "")
            self.hsn.setText(hsn or "")
            self.baseunit.setCurrentText(base or "")
            self.secondaryunit.setCurrentText(sec or "")
            self.conversion.setText(str(conv or ""))
            self.ratea.setText(str(ra or ""))
            self.rateb.setText(str(rb or ""))
            self.ratec.setText(str(rc or ""))
            self.purchaserate.setText(str(pr or ""))
            self.stockqty.setText(str(sq or ""))
            self.alertlevel.setText(str(al or ""))
            self.imagepath.setText(img or "")

# --- Customers Tab ---
class CustomersTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        layout.addWidget(self.table)
        btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add Customer")
        add_btn.clicked.connect(self.add_customer)
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        edit_btn.clicked.connect(self.edit_customer)
        btns.addWidget(add_btn)
        btns.addWidget(edit_btn)
        layout.addLayout(btns)
        self.load_customers()

    def load_customers(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name, GSTIN, Area FROM Customers")
        rows = c.fetchall()
        conn.close()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "GSTIN", "Area"])
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QtWidgets.QTableWidgetItem(str(val)))

    def add_customer(self):
        dlg = CustomerDialog()
        if dlg.exec_():
            self.load_customers()

    def edit_customer(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        dlg = CustomerDialog(name)
        if dlg.exec_():
            self.load_customers()

class CustomerDialog(QtWidgets.QDialog):
    def __init__(self, name=None):
        super().__init__()
        self.setWindowTitle("Customer Details")
        layout = QtWidgets.QFormLayout(self)
        self.name = QtWidgets.QLineEdit()
        self.gstin = QtWidgets.QLineEdit()
        self.area = QtWidgets.QLineEdit()
        layout.addRow("Name*", self.name)
        layout.addRow("GSTIN", self.gstin)
        layout.addRow("Area", self.area)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)
        if name:
            self.load_customer(name)

    def accept(self):
        if not self.name.text():
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            if self.name.text() in [row[0] for row in c.execute("SELECT Name FROM Customers")]:
                c.execute("UPDATE Customers SET GSTIN=?, Area=? WHERE Name=?", (self.gstin.text(), self.area.text(), self.name.text()))
            else:
                c.execute("INSERT INTO Customers (Name, GSTIN, Area) VALUES (?, ?, ?)", (self.name.text(), self.gstin.text(), self.area.text()))
            conn.commit()
            super().accept()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Error", "Duplicate customer name.")
        finally:
            conn.close()

    def load_customer(self, name):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name, GSTIN, Area FROM Customers WHERE Name=?", (name,))
        row = c.fetchone()
        conn.close()
        if row:
            self.name.setText(row[0])
            self.gstin.setText(row[1] or "")
            self.area.setText(row[2] or "")

# --- Purchases Tab ---
class PurchasesTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QFormLayout(self)
        self.supplier = QtWidgets.QLineEdit()
        self.item_combo = QtWidgets.QComboBox()
        self.item_combo.setEditable(True)  # <-- Allow typing/searching
        self.load_items()
        self.unit_combo = QtWidgets.QComboBox()
        self.qty = QtWidgets.QLineEdit("1")
        self.qty.setValidator(QtGui.QDoubleValidator(0, 999999, 3))
        self.rate = QtWidgets.QLineEdit()
        self.rate.setValidator(QtGui.QDoubleValidator(0, 999999, 2))
        add_btn = QtWidgets.QPushButton("Add Stock")
        add_btn.clicked.connect(self.add_stock)
        layout.addRow("Supplier", self.supplier)
        layout.addRow("Item", self.item_combo)
        layout.addRow("Unit", self.unit_combo)
        layout.addRow("Qty", self.qty)
        layout.addRow("Purchase Rate", self.rate)
        layout.addRow(add_btn)
        self.item_combo.currentIndexChanged.connect(self.update_units)

    def load_items(self):
        self.item_combo.clear()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name FROM Items ORDER BY Name")
        items = [row[0] for row in c.fetchall()]
        self.item_combo.addItems([""] + items)
        conn.close()

    def update_units(self):
        item = self.item_combo.currentText()
        self.unit_combo.clear()
        if not item:
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT BaseUnit, SecondaryUnit FROM Items WHERE Name=?", (item,))
        row = c.fetchone()
        conn.close()
        if row:
            base, sec = row
            units = [base]
            if sec:
                units.append(sec)
            self.unit_combo.addItems(units)

    def add_stock(self):
        item = self.item_combo.currentText()
        unit = self.unit_combo.currentText()
        qty = self.qty.text()
        rate = self.rate.text()
        supplier = self.supplier.text()
        if not item or not unit or not qty:
            QtWidgets.QMessageBox.warning(self, "Validation", "Item, Unit, and Qty required.")
            return
        # Update stock
        update_stock(item, unit, float(qty))
        # Log purchase
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT ItemID FROM Items WHERE Name=?", (item,))
        itemid = c.fetchone()[0]
        c.execute("INSERT INTO Purchases (Date, Supplier, ItemID, Unit, Qty, Rate) VALUES (?, ?, ?, ?, ?, ?)",
                  (QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"), supplier, itemid, unit, qty, rate))
        conn.commit()
        conn.close()
        QtWidgets.QMessageBox.information(self, "Success", "Stock updated.")

# --- Stock Tab ---
class StockTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        layout.addWidget(self.table)
        btns = QtWidgets.QHBoxLayout()
        adj_btn = QtWidgets.QPushButton("Adjust Stock")
        adj_btn.clicked.connect(self.adjust_stock)
        export_btn = QtWidgets.QPushButton("Export Stock Report")
        export_btn.clicked.connect(self.export_stock)
        btns.addWidget(adj_btn)
        btns.addWidget(export_btn)
        layout.addLayout(btns)
        self.load_stock()

    def load_stock(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name, Code, Category, StockQty, BaseUnit, AlertLevel FROM Items")
        rows = c.fetchall()
        conn.close()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Code", "Category", "StockQty", "BaseUnit", "AlertLevel"])
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(val))
                # Highlight if below alert
                if j == 3:
                    try:
                        stock_qty = float(val) if val not in ("", None) else 0
                        alert_level = float(rows[i][5]) if rows[i][5] not in ("", None) else 0
                        if stock_qty <= alert_level:
                            item.setBackground(QtGui.QColor("red"))
                    except Exception:
                        pass
                self.table.setItem(i, j, item)

    def adjust_stock(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        dlg = StockAdjustDialog(name)
        if dlg.exec_():
            self.load_stock()

    def export_stock(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Stock", "", "CSV Files (*.csv)")
        if not path:
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT Name, Code, Category, StockQty, BaseUnit, AlertLevel FROM Items")
        rows = c.fetchall()
        conn.close()
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Code", "Category", "StockQty", "BaseUnit", "AlertLevel"])
            writer.writerows(rows)
        QtWidgets.QMessageBox.information(self, "Export", "Stock exported.")

class StockAdjustDialog(QtWidgets.QDialog):
    def __init__(self, item_name):
        super().__init__()
        self.setWindowTitle("Stock Adjustment")
        layout = QtWidgets.QFormLayout(self)
        self.item = QtWidgets.QLabel(item_name)
        self.qty = QtWidgets.QLineEdit()
        self.qty.setValidator(QtGui.QDoubleValidator(-999999, 999999, 3))
        self.unit = QtWidgets.QLineEdit()
        self.reason = QtWidgets.QLineEdit()
        layout.addRow("Item", self.item)
        layout.addRow("Qty Change (+/-)", self.qty)
        layout.addRow("Unit", self.unit)
        layout.addRow("Reason*", self.reason)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def accept(self):
        if not self.qty.text() or not self.reason.text():
            QtWidgets.QMessageBox.warning(self, "Validation", "Qty and Reason required.")
            return
        update_stock(self.item.text(), self.unit.text(), float(self.qty.text()))
        # Log adjustment
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT ItemID FROM Items WHERE Name=?", (self.item.text(),))
        itemid = c.fetchone()[0]
        c.execute("INSERT INTO StockAdjustments (Date, ItemID, QtyChange, Unit, Reason) VALUES (?, ?, ?, ?, ?)",
                  (QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"), itemid, self.qty.text(), self.unit.text(), self.reason.text()))
        conn.commit()
        conn.close()
        super().accept()

# --- Stock Update Helper ---
def update_stock(item_name, unit, qty_change):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT StockQty, BaseUnit, SecondaryUnit, ConversionRate FROM Items WHERE Name=?", (item_name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    stock, base, sec, conv = row
    # Convert to base unit if needed
    if unit == sec and conv:
        qty_change = float(qty_change) / float(conv)
    c.execute("UPDATE Items SET StockQty=StockQty+? WHERE Name=?", (qty_change, item_name))
    conn.commit()
    conn.close()

# --- Receipt Printing (Simulated) ---
def print_receipt(bill_no, customer, date, items, totalqty, grand):
    # 4-inch thermal printer: ~48 chars per line
    width = 48
    receipt = []
    receipt.append("-" * width)
    receipt.append("        SUNIL STORES".center(width))
    receipt.append("-" * width)
    receipt.append(f"Bill No: {bill_no}".ljust(width//2) + f"Customer: {customer}".rjust(width//2))
    receipt.append(f"Date: {date}")
    receipt.append("-" * width)
    # Column headers
    receipt.append(f"{'Item':16}{'Unit':6}{'Qty':6}{'Rate':8}{'Total':8}")
    receipt.append("-" * width)
    for item, unit, qty, rate, total in items:
        # Truncate/align fields for 4-inch printer
        item_str = str(item)[:16].ljust(16)
        unit_str = str(unit)[:6].ljust(6)
        qty_str = str(qty)[:6].rjust(6)
        rate_str = str(rate)[:8].rjust(8)
        total_str = str(total)[:8].rjust(8)
        line = f"{item_str}{unit_str}{qty_str}{rate_str}{total_str}"
        receipt.append(line)
    receipt.append("-" * width)
    receipt.append(f"Total Qty: {totalqty}".ljust(width//2) + f"Grand: ₹{grand}".rjust(width//2))
    receipt.append("-" * width)
    receipt.append("         THANK YOU FOR SHOPPING".center(width))
    receipt.append("-" * width)
    # Simulate print (replace with actual printer code)
    print("\n".join(receipt))

# --- Main ---
if __name__ == "__main__":
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont()
    font.setPointSize(12)  # Bigger font
    app.setFont(font)
    app.setStyleSheet("""
        QLabel {
            color: #222;
            font-weight: 600;
            font-size: 14pt;
        }
        QHeaderView::section {
            background: #1565c0;
            color: #fff;
            font-size: 13pt;
            font-weight: bold;
            padding: 8px;
            border-radius: 5px;
        }
        QWidget#billHeader {
            background: #eef4fa;
            border: 1.5px solid #bcdff1;
            border-radius: 12px;
            padding: 10px 20px;
            margin-bottom: 10px;
        }
        QTableWidget {
            background: #fff;
            alternate-background-color: #f3f7fa;
            border-radius: 8px;
            gridline-color: #bcdff1;
        }
        QTableWidget::item:selected {
            background: #bcdff1;
        }
        QPushButton {
            border-radius: 8px;
            font-weight: bold;
            font-size: 12pt;
            padding: 6px 18px;
        }
        QLineEdit, QComboBox {
            border: 1.2px solid #bdbdbd;
            border-radius: 6px;
            padding: 3px 8px;
            background: #f9fafb;
            font-size: 12pt;
        }
        QGroupBox {
            background: #eef4fa;
            border: 1.5px solid #bcdff1;
            border-radius: 12px;
            padding: 10px 20px;
            margin-bottom: 10px;
        }
    """)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())