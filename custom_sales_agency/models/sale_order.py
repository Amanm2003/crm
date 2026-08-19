# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # NOTE: Confirm with client whether this default should be True or False.
    # Current default = False. Change here if the client requires the
    # checkbox to be checked by default.
    x_agency_order = fields.Boolean(string='Agency Order', default=False)
    x_agency_id = fields.Many2one('sale.agency', string='Agency')

    @api.onchange('partner_id')
    def _onchange_partner_id_agency(self):
        for order in self:
            if order.partner_id and order.partner_id.x_agency_id:
                order.x_agency_id = order.partner_id.x_agency_id

    @api.onchange('x_agency_order')
    def _onchange_x_agency_order(self):
        for order in self:
            if not order.x_agency_order:
                order.x_agency_id = False
                
    def action_confirm(self):
        for order in self:
            if order.x_agency_order and not order.x_agency_id:
                raise UserError(_(
                    "Agency Order is checked but no Agency is selected.\n"
                    "Please select an Agency or uncheck Agency Order."
                ))

            if (
                order.x_agency_order
                and order.partner_id
                and order.partner_id.x_agency_id
                and not order.partner_id.x_agency_verified
            ):
                raise ValidationError(_(
                    "The customer '%s' has not yet been verified by the assigned agency."
                ) % order.partner_id.name)

        # Update customer agency
        for order in self:
            if order.x_agency_order and order.x_agency_id and order.partner_id:
                order.partner_id.x_agency_id = order.x_agency_id
        
        for order in self:
            order._check_agency_overdue_payment()

        return super().action_confirm()
    
    def _check_agency_overdue_payment(self):
        """Block confirmation if this order's customer belongs to an
        Agency (partner.x_agency_id) and ANY customer under that same
        agency (agency.customer_ids) has overdue (unpaid, past due
        date) invoices."""
        self.ensure_one()
        customer = self.partner_id
        agency = customer.x_agency_id if customer else False
        if not agency:
            return
        
        tolerance_days = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'sale_agency.overdue_tolerance_days', default=0
            )
        )
        today = fields.Date.context_today(self)
        cutoff_date = today - timedelta(days=tolerance_days)
 
        # today = fields.Date.context_today(self)
        overdue_invoices = self.env['account.move'].sudo().search([
            ('partner_id', 'in', agency.customer_ids.ids),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'in_payment', 'reversed')),
            ('invoice_date_due', '<', cutoff_date),
        ])
 
        if overdue_invoices:
            details = ', '.join(
                '%s (%s)' % (inv.name, inv.partner_id.name) for inv in overdue_invoices
            )
            raise UserError(_(
                "Cannot confirm this Sales Order.\n\n"
                "Agency '%(agency)s' has overdue unpaid invoice(s) among its customers: %(invoices)s.\n"
                "All customers under this agency are blocked from new order confirmations "
                "until the overdue payment(s) are cleared."
            ) % {
                'agency': agency.name,
                'invoices': details,
            })

    # def action_confirm(self):
    #     for order in self:
    #         if order.x_agency_order and not order.x_agency_id:
    #             raise UserError(_(
    #                 'Agency Order is checked but no Agency is selected. '
    #                 'Please select an Agency or uncheck Agency Order.'
    #             ))
        
    #     for order in self:
    #         if order.x_agency_order and order.x_agency_id and order.partner_id:
    #             order.partner_id.x_agency_id = order.x_agency_id.id
    #     # return super().action_confirm()

    #     res = super().action_confirm()
        
    #     for order in res:
    #         partner = order.partner_id
    #         if partner.x_agency_id and not partner.x_agency_verified:
    #             raise ValidationError(
    #                 "This customer has not yet been verified by the assigned agency."
    #             )

    #     # Commission = self.env['sale.agency.commission']

    #     # for order in self:
    #     #     if not order.x_agency_order:
    #     #         continue

    #     #     # Prevent duplicate commission records
    #     #     existing = Commission.search([
    #     #         ('so_id', '=', order.id)
    #     #     ], limit=1)

    #     #     if existing:
    #     #         continue

    #     #     commission_amount = (
    #     #         order.amount_untaxed *
    #     #         order.x_agency_id.commission_pct / 100.0
    #     #     )

    #     #     Commission.create({
    #     #         'agency_id': order.x_agency_id.id,
    #     #         'so_id': order.id,
    #     #         'partner_id': order.partner_id.id,
    #     #         'currency_id': order.currency_id.id,
    #     #         'commission_amount': commission_amount,
    #     #         'state': 'draft',
    #     #     })

    #     return res
    
    
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        

        for order in orders:
            if order.partner_id.x_agency_id:
                order._send_agency_order_mail()

        return orders
    
    


    def _send_agency_order_mail(self):
        self.ensure_one()

        agency = self.partner_id.x_agency_id
        if not agency or not agency.partner_id.email:
            return

        agency_partner = agency.partner_id

        subject = f"New Order Created - {self.name or ''}"

        body_html = Markup("""
            <p>Dear %s,</p>
            <p>
            This is to inform you that an order has been created for one of your customers.
            </p>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><td><b>Order</b></td><td>%s</td></tr>
                <tr><td><b>Customer</b></td><td>%s</td></tr>
                <tr><td><b>Order Date</b></td><td>%s</td></tr>
                <tr><td><b>Total Amount</b></td><td>%s</td></tr>
                <tr><td><b>Salesperson</b></td><td>%s</td></tr>
            </table>
            <br/>
            <p>
            An agency order has been placed for your customer. Please coordinate with the customer if any additional assistance or follow-up is required.
            </p>
            <p>Thank you.</p>
        """) % (
            agency_partner.name or '',
            self.name or '',
            self.partner_id.name or '',
            self.date_order.strftime('%d-%m-%Y %H:%M') if self.date_order else '',
            f"{self.amount_total:,.2f} {self.currency_id.symbol or ''}",
            self.user_id.name or '',
        )

        mail_values = {
            "subject": subject,
            "body_html": body_html,
            "email_from": self.env.user.email_formatted,
            "email_to": agency_partner.email,
            "auto_delete": True,
        }

        self.env["mail.mail"].sudo().create(mail_values).send()
