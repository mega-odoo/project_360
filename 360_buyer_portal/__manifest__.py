{
    #  Information
    'name': '360 - Buyer Portal',
    'version': '1.2',
    'summary': 'Change RFQ/PO Details from Websit portal for related EDI Message.',
    'description': """
Change RFQ/PO Line Details from Websit portal for related EDI Message.
""",
    'category': 'Customizations',

    # Author
    'author': 'Odoo India',
    'website': 'https://www.odoo.com/',
    'license': 'LGPL-3',

    # Dependency
    'depends': [
        'purchase',
        'web',
        'purchase_manual_delivery'],
    'data': [
        'data/create_po.xml',
        'data/edi_data.xml',
        'data/vendor_edi_cron.xml',
        'data/cron.xml',
        'security/vendor_edi_security.xml',
        'security/ir.model.access.csv',
        'views/vendor_edi_message_views.xml',
        'views/purchase_views.xml',
        'views/portal_template.xml',
        'views/stock_picking.xml',
        'views/res_config_settings_views.xml',
        'wizards/create_manual_stock_picking.xml',
        'reports/purchase_reports_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            '360_buyer_portal/static/src/js/edi_message_line_update.js',
        ]
    },

    # Other
    'installable': True,
    'auto_install': False,
}
