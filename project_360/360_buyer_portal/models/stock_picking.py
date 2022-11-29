# -*- coding: utf-8 -*-
# Copyright 2022 360 ERP (<https://www.360erp.nl>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _valid_field_parameter(self, field, name):
        return name == 'limit' or super()._valid_field_parameter(field, name)

    supplier_packlist_number = fields.Char(string='Supplier Packlist Number', limit=18, copy=True)
    unique_picking_number = fields.Char(compute='_compute_unique_picking_number', store=True, readonly=True)
    date_departure = fields.Date(string='Departure Date')

    @api.depends('supplier_packlist_number', 'purchase_id')
    def _compute_unique_picking_number(self):
        for picking in self:
            name = False
            if picking.purchase_id:
                if not picking.supplier_packlist_number:
                    raise ValidationError(_('Please provide a supplier packlist number'))
                name = '%s-%s' % (picking.purchase_id.name, picking.supplier_packlist_number)
                if len(name) > 23:
                    raise ValidationError(_('Unique PO number is limited to 23 characters'))
            picking.unique_picking_number = name
