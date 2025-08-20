# Bill-buddy
Billing software
SUNIL STORES - Desktop Billing Software
A comprehensive desktop billing software for FMCG stores built with Python Tkinter and SQLite.

Features
1. Item Master Management
Add/Edit/Delete items with multiple attributes
HSN Code, Category, Item Code support
Multiple units (Base unit + Secondary unit with conversion)
Three-tier pricing (Rate A, Rate B, Rate C)
Stock management with alert levels
Image support for items
2. Billing Module
Customer selection with quick add functionality
Auto-incrementing bill numbers
Item selection with unit and rate options
Real-time total calculation
Thermal print format (3-inch)
Automatic stock deduction
No permanent sales history (as per requirement)
3. Purchase Entry
Supplier management
Item-wise purchase recording
Automatic stock updates
Auto-create items if not exists
4. Stock Management
Current stock view with status indicators
Manual stock adjustments
Reason tracking for adjustments
Export to CSV/Excel functionality
5. Customer & Supplier Management
Customer database with GSTIN support
Supplier database
Quick add functionality during billing
6. Keyboard Shortcuts
F1: Billing
F2: Item Master
F3: Purchase
F4: Stock
Installation
Ensure Python 3.7+ is installed
Install required packages:
pip install -r requirements.txt
Run the application:
python main.py
Database
The application uses SQLite database (sunil_stores.db) which is automatically created on first run.

Thermal Printing
The application generates thermal print format for 3-inch printers. Currently saves to text files for preview. For actual thermal printing, integrate with:

python-escpos
win32print (Windows)
CUPS (Linux)
Usage
Setup Items: Start by adding your inventory items in the Item Master tab
Add Customers: Create customer database for faster billing
Purchase Entry: Record your purchases to maintain stock
Billing: Select customer, add items, and print bills
Stock Management: Monitor stock levels and make adjustments
Features NOT Included (As Per Requirements)
❌ Permanent sales history
❌ Online sync
❌ GST calculations
❌ Store address/phone on invoice
Customization
The software can be customized for:

Additional fields
Different print formats
Integration with barcode scanners
Network/cloud sync (if needed later)
Support
For technical support or customization requests, contact the developer.
