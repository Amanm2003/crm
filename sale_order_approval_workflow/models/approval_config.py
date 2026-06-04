from odoo import models, fields


class SaleApprovalConfig(models.Model):
    _name = "sale.approval.config"
    _description = "Sales Approval Configuration"
    _order = "sequence"

    name = fields.Char(required=True)

    sequence = fields.Integer(default=10)

    min_amount = fields.Float()

    max_amount = fields.Float()

    risk_category = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ])

    credit_limit_breach = fields.Boolean()

    approver_ids = fields.Many2many(
        'res.users',
        string='Approvers'
    )

    active = fields.Boolean(default=True)