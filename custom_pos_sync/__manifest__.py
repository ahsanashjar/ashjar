{
    'name' : 'Customer & POS API',
    'version': '1.0',
    'summary': 'Sync Customer,Leaf Balance',
    'author': "~Mohammad Husen S",
    'website': "https://areterix.com",
    'sequence': 1,
    'description': """ This Module is create a external apis for leaf balance and sync the customer from odoo to endpoint
""",
    'category': 'Point Of Sale',
    'depends': ['web','portal','point_of_sale','contacts'],
    'data': [
            'security/ir.model.access.csv',
            'views/generate_token.xml',
            'views/leaf_history_views.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
