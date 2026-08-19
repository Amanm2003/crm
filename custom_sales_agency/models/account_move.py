# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_agency_id = fields.Many2one('sale.agency', string='Agency')
    x_is_agency_summary_bill = fields.Boolean(
        string='Agency Commission Summary Bill',
        default=False,
        copy=False,
        index=True,
    )

    @api.onchange('invoice_line_ids', 'invoice_origin')
    def _onchange_agency_from_sale_order(self):
        """Auto-populate x_agency_id from the linked Sales Order(s), if any."""
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            sale_orders = move.invoice_line_ids.sale_line_ids.order_id
            agency_orders = sale_orders.filtered('x_agency_id')
            if agency_orders and not move.x_agency_id:
                move.x_agency_id = agency_orders[0].x_agency_id

    # def action_post(self):
    #     res = super().action_post()
    #     for move in self:
    #         if move.move_type == 'out_invoice' and move.x_agency_id:
    #             move._create_agency_commission()
    #         elif move.move_type == 'out_refund' and move.x_agency_id:
    #             move._create_agency_commission_reversal()
    #     return res
    
    def action_post(self):
        res = super().action_post()

        for move in self:
            # Only customer invoices and customer credit notes
            if move.move_type not in ("out_invoice", "out_refund"):
                continue

            # Ignore if already created
            existing = self.env["sale.agency.commission"].search([
                ("invoice_id", "=", move.id)
            ], limit=1)

            if existing:
                continue

            for so in move.invoice_line_ids.sale_line_ids.order_id:

                if not so.x_agency_id:
                    continue

                commission_amount = (
                    self.amount_untaxed
                    * so.x_agency_id.commission_pct
                    / 100.0
                )

                state = "draft"

                # Credit Note / Debit Note
                if move.move_type == "out_refund":
                    commission_amount *= -1 
                    state = "draft"
                    self.env["sale.agency.commission"].create({
                        "agency_id": so.x_agency_id.id,
                        "so_id": so.id,
                        "invoice_id": move.id,
                        "partner_id": move.partner_id.id,
                        "currency_id": move.currency_id.id,
                        "commission_amount": commission_amount,
                        "commission_date": move.invoice_date,
                        "state": state,
                    })
                    return res

                self.env["sale.agency.commission"].create({
                    "agency_id": so.x_agency_id.id,
                    "so_id": so.id,
                    "invoice_id": move.id,
                    "partner_id": move.partner_id.id,
                    "currency_id": move.currency_id.id,
                    "commission_amount": commission_amount,
                    "commission_date": move.invoice_date,
                    "state": state,
                })
        for move in self.filtered(lambda m: m.move_type == "in_invoice"):
            if move.invoice_origin and move.invoice_origin.startswith("Commission-"):
                commission_id = int(move.invoice_origin.split("-")[1])

                commission = self.env["sale.agency.commission"].browse(commission_id)
                if commission.exists():
                    commission.action_mark_commission_paid()
        for move in self.filtered(lambda m: m.move_type == "in_refund"):
            if move.invoice_origin and move.invoice_origin.startswith("Commission-"):
                commission_id = int(move.invoice_origin.split("-")[1])

                commission = self.env["sale.agency.commission"].browse(commission_id)
                if commission.exists():
                    commission.action_mark_commission_paid()
        

        return res

    def _get_related_sale_order(self):
        self.ensure_one()
        return self.invoice_line_ids.sale_line_ids.order_id[:1]

    def _create_agency_commission(self):
        """Create a commission record when a Customer Invoice linked to an
        Agency is posted. The commission is initially in the
        'payment_received' state, to be updated to 'commission_paid' once
        the agency has actually been paid.
        """
        self.ensure_one()
        # sudo(): commission creation is a system-triggered side effect of
        # posting an invoice and should not require the Agency Manager
        # group on the user posting the invoice.
        Commission = self.env['sale.agency.commission'].sudo()
        # Avoid creating duplicate commissions if action_post runs more than once.
        existing = Commission.search([
            ('invoice_id', '=', self.id),
            ('commission_amount', '>=', 0),
        ], limit=1)
        if existing:
            return existing

        agency = self.x_agency_id
        so = self._get_related_sale_order()
        commission_amount = self.amount_total * (agency.commission_pct / 100.0)
        return Commission.create({
            'agency_id': agency.id,
            'invoice_id': self.id,
            'so_id': so.id if so else False,
            'partner_id': self.partner_id.id,
            'commission_amount': commission_amount,
            'currency_id': self.currency_id.id,
            'state': 'payment_received',
            'commission_date': fields.Date.context_today(self),
        })

    def _create_agency_commission_reversal(self):
        """Create a NEGATIVE commission record when a Credit Note linked to
        an Agency is posted, reversing the commission previously earned.
        """
        self.ensure_one()
        Commission = self.env['sale.agency.commission'].sudo()
        existing = Commission.search([
            ('invoice_id', '=', self.id),
            ('commission_amount', '<', 0),
        ], limit=1)
        if existing:
            return existing

        agency = self.x_agency_id
        so = self._get_related_sale_order()
        commission_amount = -(self.amount_total * (agency.commission_pct / 100.0))
        return Commission.create({
            'agency_id': agency.id,
            'invoice_id': self.id,
            'so_id': so.id if so else False,
            'partner_id': self.partner_id.id,
            'commission_amount': commission_amount,
            'currency_id': self.currency_id.id,
            'state': 'payment_received',
            'commission_date': fields.Date.context_today(self),
            'notes': 'Commission reversal due to customer return',
        })
