# -*- coding: utf-8 -*-
# Copyright 2022 360 ERP (<https://www.360erp.nl>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import models, fields


class CreateManualStockPickingWizard(models.TransientModel):
    _inherit = 'create.stock.picking.wizard'

    def _valid_field_parameter(self, field, name):
        return name == 'limit' or super()._valid_field_parameter(field, name)

    supplier_packlist_number = fields.Char(string='Supplier Packlist Number', limit=18, copy=True, required=False)

    def _prepare_picking(self):
        res = super(CreateManualStockPickingWizard, self)._prepare_picking()
        res['supplier_packlist_number'] = self.supplier_packlist_number
        return res
