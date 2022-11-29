# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edi_week_delta = fields.Integer(string='ETD Week Delta', config_parameter='360_buyer_portal.edi_week_delta', default=1)
    po_status_interval = fields.Integer(string="PO Status Interval", config_parameter='360_buyer_portal.po_status_interval', default=1)
    cyclic_po_status_frequency = fields.Integer(string="Cyclic PO Status Frequency", config_parameter='360_buyer_portal.cyclic_po_status_frequency', default=1)
