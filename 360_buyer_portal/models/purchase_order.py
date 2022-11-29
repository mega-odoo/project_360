# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io

from odoo import api, fields, models
from odoo.tools.misc import xlsxwriter
from datetime import timedelta


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # ==== Business fields ====
    date_departure = fields.Datetime(string='ETD', index=True, copy=False)
    edi_message_count = fields.Integer(
        compute="_compute_edi_messages", string='EDI Message Count',
        copy=False, default=0)
    edi_message_ids = fields.Many2many(
        comodel_name='vendor.edi.message',
        compute="_compute_edi_messages", string='EDI Messages', copy=False)
    last_po_status_message = fields.Datetime(string='Last PO Status Message')

    last_po_status_update = fields.Datetime(string="Last send PO update request", help="Pleae provide your new ETD since a delay has been reported")
    next_po_status_update = fields.Datetime(string="Next PO status update", readonly=True,
                                            help="Pleae provide your new ETD since a delay has been reported",
                                            compute="_compute_next_po_status_date")

    @api.onchange('last_po_status_update')
    def _compute_next_po_status_date(self):
        params = self.env['ir.config_parameter']
        cyclic_po_status_frequency = params.get_param('360_buyer_portal.cyclic_po_status_frequency')
        for po in self:
            if po.state in ['draft', 'sent', 'cancel', 'done']:
                self.next_po_status_update = None
            else:
                po.next_po_status_update = po.last_po_status_update + timedelta(days=int(cyclic_po_status_frequency))

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends('order_line.edi_message_lines.edi_message_id')
    def _compute_edi_messages(self):
        for order in self:
            edi_messages = order.mapped('order_line.edi_message_lines.edi_message_id')
            order.edi_message_ids = edi_messages
            order.edi_message_count = len(edi_messages)

    def _prepare_edi_message_data(self, lines=False, message_type="rfq"):
        lines = self.order_line if not lines else lines
        return {
            'purchase_id': self.id,
            'user_id': self.user_id.id,
            'partner_id': self.partner_id.id,
            'partner_ref': self.partner_ref,
            'state': 'ready',
            'message_type': message_type,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'date_order': self.date_order,
            'edi_message_line_ids': [(0, 0, {
                'display_type': line.display_type,
                'description': line.name,
                'po_line_id': line.id,
                'product_id': line.product_id.id,
                'product_qty': line.product_qty,
                'price_unit': line.price_unit,
                'date_planned': line.date_planned,
                'date_departure': line.date_departure,
                'po_line_qty': line.product_qty,
                'po_line_price_unit': line.price_unit,
                'po_line_date_planned': line.date_planned,
                'po_line_date_departure': line.date_departure
                }) for line in lines]
        }

    # -------------------------------------------------------------------------
    # Button Action
    # -------------------------------------------------------------------------

    def action_create_edi_message(self):
        """
        This method will create the EDI Message for Purchase Order and update the
        details related to it in PO/RFQ.
        """
        self.ensure_one()
        edi_msg_vals = self._prepare_edi_message_data()
        self.env['vendor.edi.message'].create(edi_msg_vals)

    def action_view_edi_message(self):
        """
        Open the EDI Message related to this PO

        Returns:
            dict: action to open vendor EDI Message for this PO/RFQ.
        """
        result = self.env['ir.actions.act_window']._for_xml_id('360_buyer_portal.vendor_edi_message_action')
        # choose the view_mode accordingly
        edi_messages = self.edi_message_ids
        if len(edi_messages) > 1:
            result['domain'] = [('id', 'in', edi_messages.ids)]
        elif len(edi_messages) == 1:
            res = self.env.ref('360_buyer_portal.vendor_edi_message_view_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state, view) for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = edi_messages.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def _set_order_line_header(self, sheet, text_style):
        sheet.write('A18', 'Internal Reference', text_style)
        sheet.write('B18', 'Description', text_style)
        sheet.write('C18', 'Quantity', text_style)
        sheet.write('D18', 'Unit Price', text_style)
        sheet.write('E18', 'ETD', text_style)
        sheet.write('F18', 'Amount', text_style)

    def _prepare_po_xlsx_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self.name)
        date_style = workbook.add_format({'num_format': 'dd/mm/yyyy', 'align': 'left'})
        head = workbook.add_format({'align': 'center', 'bold': True, 'font_size': '20'})
        text_style = workbook.add_format({'align': 'left', 'bold': True, 'font_size': '11'})
        txt = workbook.add_format({'font_size': '11', 'align': 'left'})
        sheet.merge_range('A2:K3', 'Purchase Order' if self.state in ('purchase', 'done', 'cancel') else 'Request for Quotation', head)
        sheet.write('A5', 'Purchase Order Name:' if self.state in ('purchase', 'done', 'cancel') else 'Request for Quotation Name:', text_style)
        sheet.write('B5', (self.name or ''), txt)
        sheet.write('A6', 'Order Date:', text_style)
        sheet.write('B6', (self.date_order or ''), date_style)
        sheet.write('A8', 'From:', text_style)
        sheet.write('B8', self.company_id.partner_id.name, txt)
        sheet.write('B9', self.company_id.partner_id.country_id.name, txt)
        sheet.write('A11', 'Confirmation Date:', text_style)
        sheet.write('B11', (self.date_approve or ''), date_style)
        sheet.write('A13', 'Receipt Date:', text_style)
        sheet.write('B13', (self.date_planned or ''), date_style)
        sheet.write('A16', 'Pricing', text_style)

        self._set_order_line_header(sheet, text_style)
        row = 18

        for line in self.order_line:
            data = line._prepare_order_line_data_for_xlsx_report(txt, date_style)
            for idx, value in enumerate(data):
                sheet.set_column(row, idx, 12)
                sheet.write(row, idx, value[0],  value[1])
            row += 1
        workbook.close()
        return output.getvalue()

    def create_edi(self):
        for po in self.env['purchase.order'].search([('state', '=', 'purchase')]):
            if po.next_po_status_update.date() <= fields.Date.today():
                po.last_po_status_update = fields.Date.today()
                edi_message_vals = po._prepare_edi_message_data(message_type="po")
                self.env['vendor.edi.message'].create(edi_message_vals)

    def create_po(self):
        for po in self.env['purchase.order'].search([('state', '=', 'purchase')]):
            po.last_po_status_update = fields.Date.today()
            edi_message_vals = po._prepare_edi_message_data(message_type="po")
            self.env['vendor.edi.message'].create(edi_message_vals)
