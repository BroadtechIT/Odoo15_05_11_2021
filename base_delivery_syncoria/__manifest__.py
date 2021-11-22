# -*- coding: utf-8 -*-
{
    'name': "Base Delivery Module for Delivery",
    'version': '14.0.2.0.0',
    'summary': 'Send your shippings through Purolator and track them online',
    'description': "Send your shippings through Purolator and track them online",
    'category': 'Extra Tools',
    'author': "Syncoria Inc.",
    'website': "https://www.syncoria.com",
    'company': 'Syncoria Inc.',
    'maintainer': 'Syncoria Inc.',
    'depends': ['delivery','website_sale','website_sale_delivery'],
    'images': [
    ],
    'data': [
        'views/assets.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            '/base_delivery_syncoria/static/src/js/widget.js',
            # 'delivery_canada_post/static/src/js/widget.js',
            
        ],
        
    },
    'price': 400,
    'currency': 'USD',
    'license': 'OPL-1',
    'support': "support@syncoria.com",
    'installable': True,
    'application': False,
    'auto_install': False,
    # 'uninstall_hook': 'uninstall_hook',
}
