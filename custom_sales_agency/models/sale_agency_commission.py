# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleAgencyCommission(models.Model):
    _name = 'sale.agency.commission'
    _description = 'Sales Agency Commission'
    _order = 'commission_date desc, id desc'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'seq_id'
    
    seq_id = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )

    agency_id = fields.Many2one(
        'sale.agency', string='Agency', required=True, ondelete='cascade'
    )
    so_id = fields.Many2one('sale.order', string='Sales Order')
    # sale_order_ids = fields.Many2many(
    #     'sale.order',
    #     'sale_agency_commission_sale_order_rel',
    #     'commission_id',
    #     'sale_order_id',
    #     string='Sales Orders',
    #     domain="[('x_agency_id', '=', agency_id)]",
    # )
    invoice_id = fields.Many2one('account.move', string='Invoice')
    partner_id = fields.Many2one('res.partner', string='Customer')

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    # Can be negative for return / credit note reversals.
    commission_amount = fields.Monetary(
        string='Commission Amount', currency_field='currency_id'
    )
    state = fields.Selection(
        [   ('draft','Draft'),
            ('payment_received', 'Bill Created'),
            ('commission_paid', 'Commission Paid to Agency'),
            ('commission_reversed','Commission Reversed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking =True,
    )
    commission_date = fields.Date(
        string='Commission Date', default=fields.Date.context_today, tracking=True
    )
    notes = fields.Text(string='Notes', tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    bill_count = fields.Integer(
        compute="_compute_bill_count",
        string="Bills",
    )

    @api.depends("invoice_id")
    def _compute_bill_count(self):
        for rec in self:
            rec.bill_count = 1 if rec.invoice_id else 0
    
    agency_bill_count = fields.Integer(
        compute="_compute_agent_bill_count",
        string="Bills",
    )

    @api.depends('invoice_id')
    def _compute_agent_bill_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            rec.agency_bill_count = AccountMove.search_count([
                ("move_type", "=", "in_invoice"),
                ("invoice_origin", "=", f"Commission-{rec.id}"),
            ])
            
    def action_view_agency_bill(self):
        self.ensure_one()

        bill = self.env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("invoice_origin", "=", f"Commission-{self.id}")
        ], limit=1)

        if not bill:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": "Vendor Bill",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": bill.id,
            "target": "current",
        }

    def action_view_bill(self):
        self.ensure_one()

        if not self.invoice_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": "Vendor Bill",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }
    agency_note_count = fields.Integer(
        string="Agency Debit Notes",
        compute="_compute_agency_note_count"
    )
    @api.depends("invoice_id")
    def _compute_agency_note_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            rec.agency_note_count = AccountMove.search_count([
                ("move_type", "=", "in_refund"),
                ("invoice_origin", "=", f"Commission-{rec.id}"),
            ])
        
    def action_view_agency_note(self):
        self.ensure_one()
        bill = self.env["account.move"].search([
            ("move_type", "=", "in_refund"),
            ("invoice_origin", "=", f"Commission-{self.id}")
        ], limit=1)

        if not bill:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Agency Debit Note',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': bill.id,
            'target': 'current',
        }
    
    def action_mark_commission_paid(self):
        self.write({
            'state': 'commission_paid'
        })


    def action_mark_reversed(self):
        self.write({
            'state': 'commission_reversed',
            'commission_amount': self.commission_amount *(-1),
        })
        
    def action_mark_customer_paid(self):
        self.write({
            'state':'payment_received',
        })

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        for record in self:
            if record.invoice_id:
                record.partner_id = record.invoice_id.partner_id
                record.currency_id = record.invoice_id.currency_id
                
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("seq_id", "New") == "New":
                vals["seq_id"] = self.env["ir.sequence"].next_by_code("sale.agency.commission") or 'New'
        records = super().create(vals_list)
        # for vals in vals_list:
        #     if vals.get("seq_id", "New") == "New":
        #         vals["seq_id"] = self.env["ir.sequence"].next_by_code("sale.agency.commission") or 'New'

        for rec in records:
            if rec.state == 'payment_received':
                rec._create_commission_vendor_bill()

        return records

    def write(self, vals):
        res = super().write(vals)

        if 'state' in vals:
            for rec in self:
                if rec.state == 'payment_received':
                    rec._create_commission_vendor_bill()

        return res
    
    def _create_commission_vendor_bill(self):
        AccountMove = self.env['account.move']

        for rec in self:
            if not rec.agency_id.partner_id:
                continue

            # Avoid duplicate bills
            existing_bill = AccountMove.search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_origin', '=', f'Commission-{rec.id}')
            ], limit=1)

            if existing_bill:
                continue

            # expense_account = self.env['account.account'].search([
            #     ('account_type', '=', 'expense')
            # ], limit=1)
            account_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("custom_sales_agency.agency_commission_account_id", 0)
            )

            if not account_id:
                raise UserError("Please configure the Agency Commission Expense Account in Settings.")

            expense_account = self.env["account.account"].browse(account_id)

            if not expense_account:
                continue

            # so_names = ', '.join(rec.sale_order_ids.mapped('name'))
            if rec.commission_amount>=0:

                bill = AccountMove.create({
                    'move_type': 'in_invoice',
                    'x_agency_id':self.agency_id.id,
                    'partner_id': rec.agency_id.partner_id.id,
                    'invoice_origin': f'Commission-{rec.id}',
                    'invoice_line_ids': [(0, 0, {
                        'name': f'Commission for {self.so_id.name}',
                        'quantity': 1,
                        'price_unit': rec.commission_amount,
                        'account_id': expense_account.id,
                    })]
                })
            else:
                bill = AccountMove.create({
                    'move_type': 'in_refund',   # Vendor Debit Note
                    'x_agency_id': self.agency_id.id,
                    'partner_id': rec.agency_id.partner_id.id,
                    'invoice_origin': f'Commission-{rec.id}',
                    'invoice_line_ids': [(0, 0, {
                        'name': f'Return for {self.so_id.name}',
                        'quantity': 1,
                        'price_unit': rec.commission_amount *(-1),
                        'account_id': expense_account.id,
                    })]
                })

                # bill.action_post()    
                

            rec.notes = f"Agency Bill created."