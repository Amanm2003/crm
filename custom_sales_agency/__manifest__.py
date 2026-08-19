# -*- coding: utf-8 -*-
{
    'name': 'Sales Agency & Commission Management',
    'version': '19.0.1.1.0',
    'category': 'Sales',
    'summary': 'Manage sales agencies/agents and automatic commission calculation on invoices.',
    'description': """
Sales Agency and Commission Management
=======================================
- Maintain a master list of Sales Agencies / Agents with a commission percentage.
- Link customers to an Agency (res.partner).
- Flag Sales Orders as "Agency Orders" and link them to an Agency.
- Automatically create a commission record when a customer invoice linked to an
  Agency Order is posted.
- Automatically create a NEGATIVE (reversal) commission record when a Credit Note
  linked to an Agency is posted.
- Agency form with smart buttons for Customers and Commission Records, plus a
  summary of commission due / paid / reversed.
- Agency field is intentionally NOT printed on the customer invoice/credit note
  report - it is for internal (backend) use only.

NOTE: By default the "Is Agency Order" checkbox on the Sales Order defaults to
False. Confirm with the client whether this should default to True instead -
see x_agency_order field default in models/sale_order.py.
    """,
    'author': 'Custom Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'account','purchase'],
    'data': [
        'report/sale_agency_commission_report.xml',
        'report/report_sale_agency_commission.xml',
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/sale_agency_views.xml',
        'views/sale_agency_commission_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/purchase_order_view.xml',
        'report/account_invoice_report_inherit.xml',
        'menus/menus.xml',
        'data/sequence.xml',
        
    ],
    'assets': {
        'web.assets_backend': [
            'custom_sales_agency/static/src/js/dashboard.js',
            'custom_sales_agency/static/src/xml/dashboard.xml',
            'custom_sales_agency/static/src/scss/dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
