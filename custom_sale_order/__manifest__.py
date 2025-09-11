{
    'name': "Ecommerce Odoo Integration",
    'version': '1.0',
    'summary': "Sync Customers, Sale Orders & Auto Generate Delivery Orders, Invoices and Payments.",
    'author': "~Areterix Technologies LLP",
    'website': "https://areterix.com",
    'category': 'Sales',
    'license': 'LGPL-3',
    'description': """
        This module helps Sync Customers, Sale Orders & Auto Generate Delivery Orders, Invoices and Payments from any Ecommerce Store
    """,
    'depends': ['base', 'sale', 'product', 'stock','point_of_sale','mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/customer_creator_button_view.xml',
        'views/customer_creator_tree_view.xml',
        'views/product_template_views.xml',
        'views/mrp_bom_inherit.xml',
        'report/ir_actions_report.xml',
    ],
    'demo': [],
    'images': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
