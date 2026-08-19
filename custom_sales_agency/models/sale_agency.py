# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleAgency(models.Model):
    _name = 'sale.agency'
    _description = 'Sales Agency'
    _order = 'name'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, string='Agency Name', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Agency Vendor', tracking=True, required=True, domain=[('is_agentt', '=', True)],)
    commission_pct = fields.Float(string='Commission %', digits=(5, 2))
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    agency_category = fields.Selection(
        [
            ('wholesaler', 'Wholesaler Agency'),
            ('retailer', 'Retailer Agency'),
        ],
        string='Agency Category',
        required=True,
        default='wholesaler',
        tracking=True,
    )
    
    @api.onchange('agency_category')
    def _onchange_agency_category(self):
        """Pre-fill commission % from the configurable default for this
        category. User can still override it manually afterwards."""
        for rec in self:
            rec.commission_pct = rec._get_default_commission_pct(rec.agency_category)
 
    @api.model
    def _get_default_commission_pct(self, category):
        """Read the configurable default commission % (system parameter)
        for the given category. Falls back to 2% / 3% if not configured."""
        icp = self.env['ir.config_parameter'].sudo()
        if category == 'wholesaler':
            return float(icp.get_param('sale_agency.wholesaler_commission_pct', default=2.0))
        elif category == 'retailer':
            return float(icp.get_param('sale_agency.retailer_commission_pct', default=3.0))
        return 0.0

    # Customers linked to this agency via res.partner.x_agency_id
    customer_ids = fields.One2many(
        'res.partner', 'x_agency_id', string='Customers'
    )
    customer_count = fields.Integer(
        string='Customer Count', compute='_compute_customer_count'
    )
    
    bill_count = fields.Integer(
        string='Bill Count', compute='_compute_bill_count'
    )

    # Commission records
    commission_ids = fields.One2many(
        'sale.agency.commission', 'agency_id', string='Commission Records'
    )
    commission_count = fields.Integer(
        string='Commission Count', compute='_compute_commission_count'
    )

    # Commission summary totals
    total_commission_due = fields.Monetary(
        string='Total Commission Due',
        compute='_compute_commission_totals',
        currency_field='currency_id',
        help="Sum of commissions currently in 'Customer Payment Received' state.",
    )
    total_commission_paid = fields.Monetary(
        string='Total Commission Paid',
        compute='_compute_commission_totals',
        currency_field='currency_id',
        help="Sum of commissions in 'Commission Paid to Agency' state.",
    )
    total_commission_negative = fields.Monetary(
        string='Total Commission Reversed',
        compute='_compute_commission_totals',
        currency_field='currency_id',
        help="Sum of all negative commissions (returns / credit notes).",
    )

    @api.depends('customer_ids')
    def _compute_customer_count(self):
        for agency in self:
            agency.customer_count = len(agency.customer_ids)

    @api.depends('commission_ids')
    def _compute_commission_count(self):
        for agency in self:
            agency.commission_count = len(agency.commission_ids)
    
    def _compute_bill_count(self):
        for agency in self:
            agency.bill_count = self.env['account.move'].search_count([
                ('move_type', 'in', ('in_invoice', 'in_refund')),
                ('x_agency_id', '=', agency.id),
            ])

    def _compute_commission_totals(self):
        """Compute live commission due/paid amounts.

        Commission records in Draft/Bill Created are eligible as due. For bills
        created from the Agency form, the amount moves from Due to Paid only when
        the vendor bill reaches In Payment/Paid. Partial payments move only the
        actually paid portion.
        """
        AccountMove = self.env['account.move']
        for agency in self:
            raw_due = sum(agency.commission_ids.filtered(
                lambda c: c.state in ('draft', 'payment_received')
            ).mapped('commission_amount'))
            legacy_paid = sum(agency.commission_ids.filtered(
                lambda c: c.state == 'commission_paid'
            ).mapped('commission_amount'))

            summary_bills = AccountMove.search([
                ('x_agency_id', '=', agency.id),
                ('x_is_agency_summary_bill', '=', True),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('partial', 'in_payment', 'paid')),
            ])

            paid_from_bills = 0.0
            for bill in summary_bills:
                # Bills are created in agency currency. For a partial payment,
                # only the settled portion is moved to Total Commission Paid.
                if bill.payment_state in ('in_payment', 'paid'):
                    paid_from_bills += bill.amount_total
                elif bill.payment_state == 'partial':
                    paid_from_bills += max(bill.amount_total - bill.amount_residual, 0.0)

            agency.total_commission_due = max(raw_due - paid_from_bills, 0.0)
            agency.total_commission_paid = legacy_paid + paid_from_bills
            agency.total_commission_negative = 0.0

    def action_view_customers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'base.action_partner_form'
        )
        action['domain'] = [('x_agency_id', '=', self.id)]
        action['context'] = {'default_x_agency_id': self.id}
        return action

    def action_view_commissions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'custom_sales_agency.action_sale_agency_commission'
        )
        action['domain'] = [('agency_id', '=', self.id)]
        action['context'] = {'default_agency_id': self.id}
        return action
    
    def action_view_bills(self):
        self.ensure_one()

        bills = self.env['account.move'].search([
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('x_agency_id', '=', self.id),
        ])

        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        action['domain'] = [('id', 'in', bills.ids)]
        action['context'] = {
            'default_move_type': 'in_invoice',
            'default_x_agency_id': self.id,
        }

        if len(bills) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = bills.id

        return action

    def action_create_bill(self):
        """Create one draft vendor bill for the current commission due.

        If a summary commission bill is already open (draft/posted but not yet
        in payment), open that bill instead of creating a duplicate.
        """
        self.ensure_one()

        if not self.partner_id:
            raise UserError("Please select an Agency Vendor first.")

        existing_bill = self.env['account.move'].search([
            ('x_agency_id', '=', self.id),
            ('x_is_agency_summary_bill', '=', True),
            ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel'),
            ('payment_state', 'not in', ('in_payment', 'paid')),
        ], order='id desc', limit=1)
        if existing_bill:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Agency Commission Bill',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': existing_bill.id,
                'target': 'current',
            }

        amount = self.total_commission_due
        if amount <= 0:
            raise UserError("There is no commission due to create a bill.")

        account_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'custom_sales_agency.agency_commission_account_id', 0
            ) or 0
        )
        if not account_id:
            raise UserError(
                "Please configure the Agency Commission Expense Account in Settings."
            )

        expense_account = self.env['account.account'].browse(account_id).exists()
        if not expense_account:
            raise UserError("Configured Agency Commission Expense Account is invalid.")

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'x_agency_id': self.id,
            'x_is_agency_summary_bill': True,
            'invoice_origin': f'Agency Commission - {self.name}',
            'invoice_line_ids': [(0, 0, {
                'name': f'Agency Commission - {self.name}',
                'quantity': 1.0,
                'price_unit': amount,
                'account_id': expense_account.id,
            })],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Agency Commission Bill',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("partner_id").write({"is_agentt": True})
        return records
