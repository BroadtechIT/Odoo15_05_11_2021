# -*- coding: utf-8 -*-
{
    'name': "Syncoria Canada Post Integration",
    'version': '15.0.1.0.0',
    'summary': """Syncoria Canada Post Integration""",
    'description': """Syncoria Canada Post Integration""",
    'category': 'Extra Tools',
    'author': "Syncoria Inc.",
    'website': "https://www.syncoria.com",
    'company': 'Syncoria Inc.',
    'depends': ['delivery', 'mail','website_sale','website_sale_delivery','web'],
    'images': [
        'static/description/banner.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/services.xml',
        'data/canada_post.xml',
        'views/delivery_canada_post.xml',
        'views/choose_delivery_carrier.xml',
        'views/webclient_templates.xml',
        'views/sale_order.xml',
        'views/res_company.xml',
         'views/product.xml',
    ],
    'demo':[
         'demo/demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'delivery_canada_post/static/src/css/delivery_canada_post.css',
            'delivery_canada_post/static/src/js/widget.js',
            
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
