# -*- coding: utf-8 -*-
from odoo import fields, models,api
from markupsafe import Markup


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_agency_id = fields.Many2one(
        'sale.agency',
        string='Agency/Agent',
        help='If this customer belongs to a Sales Agency, select it here. '
             'Sales Orders created for this customer will automatically '
             'default to this Agency.',
    )
    x_agency_verified = fields.Boolean(
        string="Agency Verified",
        default=False,
        tracking=True,
        help="Checked when the agency verifies this customer."
    )

    x_agency_verified_date = fields.Datetime(
        string="Verified On",
        readonly=True,
    )

    x_agency_verified_by = fields.Many2one(
        "res.users",
        string="Verified By",
        readonly=True,
    )
    
    is_agentt = fields.Boolean(string='Is Agent')
    
    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)

        for partner in partners:
            if (
                partner.x_agency_id
                and partner.email
            ):
                partner._send_agency_verification_mail()

        return partners
    
    # def _send_agency_verification_mail(self):
    #     self.ensure_one()

    #     agency = self.x_agency_id
    #     if not agency:
    #         return

    #     agency_partner = agency.partner_id
    #     if not agency_partner.email:
    #         return

    #     template = self.env.ref(
    #         "custom_sales_agency.mail_template_agency_customer_verification",
    #         raise_if_not_found=False,
    #     )
    #     if not template:
    #         return

    #     template.sudo().send_mail(
    #         self.id,
    #         force_send=True,
    #         email_values={"email_to": agency_partner.email},
    #     )
    def write(self, vals):
        if "x_agency_id" in vals:
            if not self.x_agency_verified:
                vals.update({
                    "x_agency_verified": False,
                    "x_agency_verified_date": False,
                    "x_agency_verified_by": False,
                })
        result = super().write(vals)

        if "x_agency_id" in vals:
            for partner in self:
                if partner.x_agency_id and not partner.x_agency_verified:
                    partner._send_agency_verification_mail()

        return result
    
    def action_verify_agency_customer(self):
        for partner in self:
            partner.write({
                "x_agency_verified": True,
                "x_agency_verified_date": fields.Datetime.now(),
                "x_agency_verified_by": self.env.user.id,
            })
    


    def _send_agency_verification_mail(self):
        self.ensure_one()

        agency = self.x_agency_id
        if not agency:
            return

        agency_partner = agency.partner_id
        if not agency_partner.email:
            return

        subject = f"Customer Verification & Credit Limit Request - {self.name or ''}"

        body_html = Markup("""
            <p>Dear %s,</p>
            <p>A new customer has been registered under your agency.</p>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><td><b>Customer Name</b></td><td>%s</td></tr>
                <tr><td><b>Email</b></td><td>%s</td></tr>
                <tr><td><b>Phone</b></td><td>%s</td></tr>
                <tr><td><b>Company</b></td><td>%s</td></tr>
            </table>
            <br/>
            <p>Kindly verify this customer and provide the recommended credit limit.</p>
            <p>Please reply to this email with:</p>
            <ul>
                <li>Customer verification status</li>
                <li>Recommended credit limit</li>
                <li>Any remarks or observations</li>
            </ul>
            <br/>
            <p>Thank you.</p>
        """) % (
            agency_partner.name or '',
            self.name or '',
            self.email or '',
            self.phone or '',
            self.parent_id.name or self.company_name or '',
        )

        mail_values = {
            "subject": subject,
            "body_html": body_html,
            "email_from": self.env.user.email_formatted,
            "email_to": agency_partner.email,
            "auto_delete": True,
        }

        self.env["mail.mail"].sudo().create(mail_values).send()
