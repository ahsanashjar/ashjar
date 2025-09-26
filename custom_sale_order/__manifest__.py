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
    'depends': ['base', 'sale', 'product', 'stock', 'point_of_sale', 'mrp','web'],

    'data': [
        'security/ir.model.access.csv',
        'views/customer_creator_button_view.xml',
        'views/customer_creator_tree_view.xml',
        'views/product_template_views.xml',
        'views/mrp_bom_inherit.xml',
        'report/ir_actions_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_sale_order/static/src/js/bom_button.js',
            'custom_sale_order/static/src/xml/mrp_bom_list_buttons.xml',
        ],
    },
    'demo': [],
    'images': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
