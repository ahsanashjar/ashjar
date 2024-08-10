{
    'name': "Ecommerce Odoo Integration",
    'version': '1.1',
    'summary': "Sync Customers, Sale Orders & Auto Generate Delivery Orders, Invoices and Payments.",
    'author': "~Areterix Technologies LLP",
    'website': "https://areterix.com",
    'category': 'Sales',
    'license': 'LGPL-3',
    'description': """
        This module helps Sync Customers, Sale Orders & Auto Generate Delivery Orders, Invoices and Payments from any Ecommerce Store
    """,
    'depends': ['base', 'sale', 'product', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_creator_button_view.xml',
        'views/customer_creator_tree_view.xml',
        'views/product_template_views.xml',
    ],
    'demo': [],
    'images': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
