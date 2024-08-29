# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Pos ScanQR Customer',
    'summary': '',
    'sequence': 1,
    'description': """
""",
    'category': '',
    'website': '',
    'depends': ['point_of_sale','web'],
    'data': [
        'data/sevrer_actions.xml',
        'views/res_partner_view.xml',
        'reports/qr_code_report.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # 'https://cdnjs.cloudflare.com/ajax/libs/quaggajs/0.12.1/quagga.min.js',
            'ensigncode_scanqr_customer_autoscan/static/src/xml/action_pad_inherit.xml',
            'ensigncode_scanqr_customer_autoscan/static/src/js/actionpad_inherit.js',
            'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js',
            'https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
