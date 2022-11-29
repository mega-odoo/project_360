# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from operator import itemgetter

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.tools import groupby


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # ==== Business fields ====
    date_departure = fields.Datetime(string='ETD', copy=False, index=True)
    edi_message_lines = fields.One2many(
        comodel_name='vendor.edi.message.line', inverse_name='po_line_id',
        string="EDI Message Lines", readonly=True, copy=False)
    is_completed = fields.Boolean(string='Completed', default=False)

    @api.model
    def _get_date_planned(self, seller, po=False):
        res = super(PurchaseOrderLine, self)._get_date_planned(seller, po=False)
        date_planned = po.date_planned if po else self.order_id.date_planned
        if date_planned:
            return date_planned
        else:
            return res

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(PurchaseOrderLine, self)._onchange_quantity()
        if not self.date_planned:
            self.date_planned = self.order_id.date_planned
        return res

    # Do not change pickings when updating POL
    def _create_or_update_picking(self):
        return True

    @api.depends('qty_received_method', 'qty_received_manual')
    def _compute_qty_received(self):
        res = super(PurchaseOrderLine, self)._compute_qty_received()
        for line in self:
            if line.qty_received != 0 and line.qty_received >= line.product_qty:
                line.is_completed = True
            else:
                line.is_completed = False
        return res

    def create_edi_messages(self):
        edi_message_vals = dict()
        params = self.env['ir.config_parameter']
        weeks = params.get_param('360_buyer_portal.edi_week_delta')
        interval_day = params.get_param('360_buyer_portal.po_status_interval')
        today = fields.Date.today()
        lines = self.search([]).filtered(lambda p: p.state == 'purchase' and not p.is_completed and p.qty_received > 0 and p.date_departure).sorted('order_id')
        for order_id, order_line in groupby(lines, itemgetter('order_id')):
            line = self.env['purchase.order.line'].concat(*order_line)
            for date_departure, date_departure_line in groupby(line, itemgetter('date_departure')):
                group_etd_lines = self.env['purchase.order.line'].concat(*date_departure_line)
                if today == date_departure.date():
                    edi_message_vals = order_id._prepare_edi_message_data(lines=group_etd_lines, message_type="shipping")
                else:
                    if not order_id.last_po_status_message:
                        order_id.last_po_status_message = today
                        edi_message_vals = order_id._prepare_edi_message_data(lines=group_etd_lines, message_type="po")
                    elif order_id.last_po_status_message:
                        days_to_date = order_id.last_po_status_message.date() + relativedelta(days=int(interval_day))
                        if today == days_to_date:
                            order_id.last_po_status_message = today
                            edi_message_vals = order_id._prepare_edi_message_data(lines=group_etd_lines, message_type="po")
                self.env['vendor.edi.message'].create(edi_message_vals)

    def _prepare_order_line_data_for_xlsx_report(self, txt, date_style):
        self.ensure_one()
        return (
            (self.product_id.default_code or '', txt),
            (self.product_id.name, txt),
            (self.product_qty, txt),
            (self.price_unit, txt),
            (self.date_departure or '', date_style),
            (self.price_subtotal, txt)
        )
