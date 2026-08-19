from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    agency_commission_account_id = fields.Many2one(
        "account.account",
        string="Agency Commission Expense Account",
        config_parameter="custom_sales_agency.agency_commission_account_id",
        domain="[('active', '=', True)]",
    )
    agency_overdue_tolerance_days = fields.Integer(
        string='Overdue Tolerance (Days)',
        config_parameter='sale_agency.overdue_tolerance_days',
        default=0,
        help='Number of days past the invoice due date that are still '
             'allowed before agency customers get blocked from new sales '
             'order confirmations. E.g. 5 means an invoice overdue by up '
             'to 5 days will NOT block confirmation; on day 6 it will.',
    )