{
    'name' : 'Pos ScanQR Customer',
    'version': '1.0',
    'summary': 'Scan QR Code In POS',
    'author': "~Mohammad Husen S",
    'sequence': 1,
    'description': """ This Module is inherit pos module and add one new field in pos customer selection and customer can select via scan qr code
""",
    'category': 'Point Of Sale',
    'website': 'https://areterix.com',
    'depends': ['point_of_sale','web'],
    'data': [
        'data/sevrer_actions.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # 'https://cdnjs.cloudflare.com/ajax/libs/quaggajs/0.12.1/quagga.min.js',
            'custom_scanqr/static/src/xml/action_pad_inherit.xml',
            'custom_scanqr/static/src/js/actionpad_inherit.js',
            'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
