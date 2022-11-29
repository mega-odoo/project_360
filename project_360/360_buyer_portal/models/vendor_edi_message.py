# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from odoo import api, fields, models
from odoo.osv import expression
from odoo.tools.misc import format_date
from odoo.tools.misc import xlsxwriter


class VendorEDIMessage(models.Model):
    _name = "vendor.edi.message"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Vendor EDI Message"

    def _valid_field_parameter(self, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)

    def _filter_portal_contact(self):
        """
        Compute the domain for related vendor contects. We only needs the partner 
        which are of type `contact` and has related user with portal access.

        Need to get child of current partner this way as Odoo default is not giving
        the available contact from its `address_get` method for specifically 
        type `contact`.

        Returns:
            list: Domain to filter the vendor contacts
        """
        domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]
        if self.partner_id:
            child_contact_ids = self.partner_id.child_ids.filtered(lambda partner:partner.type == 'contact')
            portal_contact = child_contact_ids.mapped('user_ids').filtered(lambda user:user.share and user.has_group('base.group_portal'))
            if portal_contact:
                portal_partners = portal_contact.partner_id.ids
                domain = expression.AND([[('id','in',portal_partners)], domain])
        return domain


    READONLY_STATES = {
        'processed': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
        'error': [('readonly', True)],
    }

    # ==== Business fields ====
    name = fields.Char("Name", required=True, index=True, copy=False, default='New')
    purchase_id = fields.Many2one(comodel_name="purchase.order",
        string="Purchase Order", states=READONLY_STATES)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Vendor", states=READONLY_STATES)
    partner_ref = fields.Char(string = 'Vendor Reference', copy=False, tracking=True,
        help = "Reference of the purchase order in the system", states=READONLY_STATES)
    date_order = fields.Datetime(
        string='Order Deadline',
        required=True,
        states=READONLY_STATES,
        index=True,
        copy=False,
        default=fields.Datetime.now,
        help="The value will be fetched from the related Purchase Order/Quotation.")
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('processed', 'Processed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('error', 'Error')], string="State", default="draft", tracking=True)
    
    message_type = fields.Selection(selection=[
        ('rfq','RFQ'),
        ('po','PO'),
        ('shipping','Shipping')
    ], string= "Message Type", states=READONLY_STATES)
    vendor_contact_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="edi_message_vendor_contact_rel",
        column1="edi_message_id",
        column2="contact_id",
        string="Vendor Contact",
        domain=_filter_portal_contact,
        states=READONLY_STATES)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        index=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.id)
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string= 'Currency',
        required=True,
        states=READONLY_STATES,
        default=lambda self: self.env.company.currency_id.id)
    purchase_order_line = fields.One2many(
        comodel_name='purchase.order.line',
        related='purchase_id.order_line',
        string='Purchase Lines',
        states=READONLY_STATES,
        copy=True)
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Purchase Representative',
        index=True,
        tracking=True,
        default=lambda self: self.env.user, check_company=True)
    edi_message_line_ids = fields.One2many(
        comodel_name='vendor.edi.message.line',
        inverse_name='edi_message_id', string='EDI Message Lines',
        states=READONLY_STATES, tracking=True)
    edi_message_compare_line_ids = fields.One2many(
        comodel_name='vendor.edi.message.line',
        inverse_name='edi_message_id', string='EDI Message Lines',
        states=READONLY_STATES, tracking=True)
    qty_total = fields.Float(compute='_compute_qty_total', string='Total Quantity', copy=False)
    
    # -------------------------------------------------------------------------
    # ONCHANGE & COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('edi_message_line_ids.product_qty')
    def _compute_qty_total(self):
        for edi_message in self:
            edi_message.qty_total = sum(edi_message.edi_message_line_ids.mapped('product_qty'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Update the domain on vendor contact when partner is changed.
        Returns:
            dict: operation to perform when change in the partner.
        """
        if self.partner_id:
            partner_domain = self._filter_portal_contact()
            return {'domain': {'vendor_contact_ids': partner_domain}}
    
    def _compute_access_url(self):
        super(VendorEDIMessage, self)._compute_access_url()
        for message in self:
            message.access_url = '/my/message/%s' % (message.id)

    def button_done(self):
        self.write({'state': 'done'})

    def button_cancel(self):
        self.write({'state': 'cancel'})

    def button_error(self):
        self.write({'state': 'error'})

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------

    @api.model
    def create(self, vals):
        # Create EDI Message and Update the name with sequence.
        company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
        self_comp = self.with_company(company_id)
        if vals.get('name', 'New') == 'New':
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['name'] = self_comp.env['ir.sequence'].next_by_code('vendor.edi.message', sequence_date=seq_date) or '/'
        res = super(VendorEDIMessage, self_comp).create(vals)
        return res

    # -------------------------------------------------------------------------
    # BUTTON ACTION METHODS
    # -------------------------------------------------------------------------

    def action_confirm(self):
        self.state = "processed"

    def action_process_edi_message(self):
        for line in self.edi_message_line_ids.filtered(lambda l: l.is_process):
            update_vals = dict()
            if line.price_unit != line.po_line_id.price_unit:
                update_vals['price_unit'] = line.price_unit
            if line.product_qty != line.po_line_id.product_qty:
                update_vals['product_qty'] = line.product_qty
            if line.date_planned != line.po_line_id.date_planned:
                update_vals['date_planned'] = line.date_planned
            if line.date_departure != line.po_line_id.date_departure:
                update_vals['date_departure'] = line.date_departure
            line.po_line_id.write(update_vals)
        self.state = "done"
        return True
    
    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _is_need_to_process(self):
        return True if self.state == 'ready' else False

    def _set_edi_line_header(self, sheet, text_style):
        sheet.write('A20', 'Internal Reference', text_style)
        sheet.write('B20', 'Description', text_style)
        sheet.write('C20', 'barcode', text_style)
        sheet.write('D20', 'Quantity', text_style)
        sheet.write('E20', 'Unit Price', text_style)
        sheet.write('F20', 'ETD', text_style)

    def _prepare_xlsx_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self.name)
        date_style = workbook.add_format({'num_format': 'dd/mm/yyyy', 'align': 'left'})
        head = workbook.add_format({'align': 'center', 'bold': True, 'font_size': '20'})
        text_style = workbook.add_format({'align': 'left', 'bold': True, 'font_size': '11'})
        txt = workbook.add_format({'font_size': '11', 'align': 'left'})
        sheet.merge_range('A2:K3', 'Vendor EDI Message', head)
        sheet.write('A5', 'EDI Message Name:', text_style)
        sheet.write('B5', (self.name or ''), txt)
        sheet.write('A6', 'EDI Message Quotation/PO Date:', text_style)
        sheet.write('B6', (self.purchase_id.date_order or ''), date_style)
        sheet.write('A8', 'Vendor Reference:', text_style)
        sheet.write('B8', (self.partner_ref or ''), txt)
        sheet.write('A10', 'From:', text_style)
        sheet.write('B10', self.purchase_id.company_id.partner_id.name, txt)
        sheet.write('B11', self.purchase_id.company_id.partner_id.country_id.name, txt)
        sheet.write('A15', 'Confirmation Date:', text_style)
        sheet.write('B15', (self.purchase_id.date_approve or ''), date_style)
        sheet.write('A16', 'Receipt Date:', text_style)
        sheet.write('B16', (self.purchase_id.date_planned or ''), date_style)
        sheet.write('A19', 'Pricing', text_style)

        self._set_edi_line_header(sheet, text_style)
        row = 20
        
        for line in self.edi_message_line_ids:
            data = line._prepare_line_data_for_xlsx_report(txt, date_style)
            for idx, value in enumerate(data):
                sheet.set_column(row, idx, 12)
                sheet.write(row, idx, value[0],  value[1])
            row += 1
        workbook.close()
        return output.getvalue()

class VendorEDIMessageLine(models.Model):
    _name = 'vendor.edi.message.line'
    _description = "Vendor EDI Message Lines"
    _rec_name = 'name'

    def _valid_field_parameter(self, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)

    # ==== Business fields ====
    description = fields.Text(string='Description', required=False)
    edi_message_id = fields.Many2one(
        comodel_name='vendor.edi.message', string='EDI Message')
    po_line_id = fields.Many2one(
        comodel_name='purchase.order.line', string='PO Line')
    product_id = fields.Many2one(
        comodel_name='product.product', string='Product')
    name = fields.Char(related='product_id.name')
    product_qty = fields.Float(
        string='Quantity', digits='Product Unit of Measure', tracking=True)

    price_unit = fields.Float(
        string='Unit Price', required=True, digits='Product Price', tracking=True)
    date_planned = fields.Datetime(string='ETA', tracking=True)
    date_departure = fields.Datetime(string='ETD', copy=False, tracking=True)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    message_type = fields.Selection(related='edi_message_id.message_type', string= "Message Type")
    message_state = fields.Selection(
        related='edi_message_id.state', string='EDI Message Status', copy=False, store=True)
    purchase_id = fields.Many2one(related="edi_message_id.purchase_id",
        string="Purchase Order", store=True)
    partner_id = fields.Many2one(related="edi_message_id.partner_id", string="Vendor", store=True)
    partner_ref = fields.Char(related="edi_message_id.partner_ref", string = 'Vendor Reference',
        help = "Reference of the purchase order in the system", store=True)
    # Comparison fields with purchase order line.
    po_line_qty = fields.Float(
        string="RFQ Qty", digits="Product Unit of Measure")
    po_line_price_unit = fields.Float(
        string='RFQ Unit Price')
    po_line_date_planned = fields.Datetime(
        string="RFQ ETA")
    po_line_date_departure = fields.Datetime(
        string="RFQ ETD")
    is_process = fields.Boolean(string='Process', default=True)
    status_line = fields.Selection([
        ('on_track', 'On Track'),
        ('delay', 'Delayed')], string="State", default="on_track")
    delayed_date = fields.Datetime(string="New ETD", index=True, help="Pleae provide your new ETD since a delay has been reported")

    def _get_tracking_field_string(self, message, fields):
        """
        Generate Log Message String

        Args:
            message (str): The name of the EDI Message
            fields (list): List containing dictionary of values for preparing log message.

        Returns:
            str: Message prepared for logging at RFQ.
        """
        item = fields[0]
        redirect_link = '<a href=# data-oe-model=vendor.edi.message.line data-oe-id=%d>#%d</a>' % (item['line_id'], item['line_id'])
        ARROW_RIGHT = '<div class="o_Message_trackingValueSeparator o_Message_trackingValueItem fa fa-long-arrow-right" title="Changed" role="img"/>'
        msg = '<div class="o_Message_header mb-1">%s : Line Changed</div>' % (message)
        msg += '<div class="o_Message_prettyBody"><p>%s (%s)</p></div>' % (item['line_name'], redirect_link)
        msg += '<ul>'
        for field in fields:
            msg += '<li>%s: %s %s %s</li>' % (field['field_name'], field['old_value'], ARROW_RIGHT, field['new_value'])
        msg += '</ul>'
        return msg

    def _prepare_field_for_log(self, field, old_value, new_values):
        """
        The function will prepare the value for tracking purpose.

        Args:
            field (str): Name of the field for which we prepare log
            old_value (float/datetime): The Old value
            new_values (float/datetime): The New value

        Returns:
            dict: The values prepared for log.
        """
        self.ensure_one()
        values = dict()
        #  Get the fields details
        ref_fields = self.fields_get(field)
        if ref_fields[field].get('type') in ('date', 'datetime'):
            old_value  =  format_date(self.env, fields.Datetime.from_string(old_value))
            new_values  =  format_date(self.env, fields.Datetime.from_string(new_values))
        values.update({
            'field_name': ref_fields[field].get('string'),
            'line_id': self.id,
            'line_name': self.name,
            'old_value': old_value,
            'new_value': new_values
        })
        return values

    def _prepare_line_data_for_xlsx_report(self, txt, date_style):
        self.ensure_one()
        return (
            (self.product_id.default_code or '', txt),
            (self.product_id.name, txt),
            (self.product_id.barcode, txt),
            (self.product_qty, txt),
            (self.price_unit, txt),
            (self.date_departure or '', date_style)
        )
