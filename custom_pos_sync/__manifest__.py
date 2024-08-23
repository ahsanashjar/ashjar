{
    'name' : 'Customer & POS API',
    'version': '1.0',
    'summary': 'Sync Customer,Leaf Balance',
    'author': "~Areterix Technologies LLP",
    'website': "https://areterix.com",
    'sequence': 1,
    'description': """ This Module is create a external apis for leaf balance and sync the customer from odoo to endpoint
""",
    'category': 'Point Of Sale',
    'depends': ['web','portal'],
    'data': [
            'security/ir.model.access.csv',
            'views/generate_token.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
