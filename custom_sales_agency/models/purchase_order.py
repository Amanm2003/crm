# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # NOTE: Confirm with client whether this default should be True or False.
    # Current default = False. Change here if the client requires the
    # checkbox to be checked by default.
    x_agency_order = fields.Boolean(string='Agency Order', default=True)
    x_agency_id = fields.Many2one('sale.agency', string='Agency')