# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from datetime import datetime
from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import Response, request, content_disposition
from odoo.tools import image_process
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager, get_records_pager
from odoo.tools.float_utils import float_repr
from odoo.osv.expression import OR, AND
from odoo.tools import groupby as groupbyelem
from operator import itemgetter
from collections import OrderedDict


class CustomerPortalEDI(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'edi_message_count' in counters:
            edi_message_count = request.env['vendor.edi.message'].search_count(self._get_edi_message_domain()) \
                if request.env['vendor.edi.message'].check_access_rights('read', raise_exception=False) else 0
            values['edi_message_count'] = edi_message_count
        return values

    def _get_edi_message_domain(self):
        return [('state', 'in', ('ready', 'processed', 'done'))]
    
    def _edi_message_get_page_view_values(self, message, access_token, **kwargs):
        def resize_to_48(b64source):
            if not b64source:
                b64source = base64.b64encode(request.env['ir.http']._placeholder())
            return image_process(b64source, size=(48, 48))

        values = {
            'message': message,
            'resize_to_48': resize_to_48,
            'report_type': 'html',
        }
        history = 'my_messages_history'
        return self._get_page_view_values(message, access_token, values, history, False, **kwargs)

    def _message_get_searchbar_inputs(self):
        values = {
            'edi_num': {'input': 'edi_number', 'label': _('EDI Number'), 'order': 1},
            'po_num': {'input': 'po_number', 'label': _('PO Number'), 'order': 2}
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _message_get_search_domain(self, search_in, search):
        search_domain = []
        if search_in in ('edi_number', 'all'):
            search_domain.append([('name', 'ilike', search)])
        if search_in in ('po_number', 'all'):
            search_domain.append([('purchase_id', 'ilike', search)])

        return OR(search_domain)

    def _message_get_searchbar_groupby(self):
        values = {
            'none': {'input': 'none', 'label': _('None'), 'order': 1},
            'message_type': {'input': 'message_type', 'label': _('Message Type'), 'order': 2},
            'state': {'input': 'state', 'label': _('State'), 'order': 3},
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _message_get_order(self, order, groupby):
        groupby_mapping = {
            'message_type': 'message_type',
            'state': 'state',
        }
        field_name = groupby_mapping.get(groupby, '')
        if not field_name:
            return order
        return '%s, %s' % (field_name, order)

    # TODO: Improve further with search and filter options
    def _render_edi_message_portal(self, template, page, sortby, domain, url, history, page_name, key, search, search_in, groupby, filterby):
        values = self._prepare_portal_layout_values()
        VendorEDIMessage = request.env['vendor.edi.message']

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'old_date': {'label': _('Oldest'), 'order': 'create_date asc, id asc'},
        }

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'ready': {'label': _('State = Ready'), 'domain': [('state', '=', 'ready')]},
            'processed': {'label': _('State = Processed'), 'domain': [('state', '=', 'processed')]},
            'rfq': {'label': _('Message Type = RFQ'), 'domain': [('message_type', '=', 'rfq')]},
            'po': {'label': _('Message Type = PO'), 'domain': [('message_type', '=', 'po')]},
        }

        searchbar_inputs = self._message_get_searchbar_inputs()
        searchbar_groupby = self._message_get_searchbar_groupby()

        # default sort
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters.get(filterby, searchbar_filters.get('all'))['domain']

        # default group by value
        if not groupby:
            groupby = 'message_type'

        # search
        if search and search_in:
            domain += self._message_get_search_domain(search_in, search)
        domain = AND([domain, request.env['ir.rule']._compute_domain(VendorEDIMessage._name, 'read')])

        # count for pager
        count = VendorEDIMessage.search_count(domain)

        # make pager
        pager = portal_pager(
            url=url,
            url_args={'sortby': sortby, 'filterby': filterby, 'groupby': groupby, 'search_in': search_in, 'search': search},
            total=count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        order = self._message_get_order(order, groupby)

        # search the purchase orders to display, according to the pager data
        messages = VendorEDIMessage.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        request.session[history] = messages.ids[:100]

        groupby_mapping = {
            'message_type': 'message_type',
            'state': 'state'
        }
        group = groupby_mapping.get(groupby)
        if group:
            grouped_messages = [VendorEDIMessage.concat(*g) for k, g in groupbyelem(messages, itemgetter(group))]
        else:
            grouped_messages = [messages]

        values.update({
            key: messages,
            'grouped_messages': grouped_messages,
            'page_name': page_name,
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'search': search,
            'sortby': sortby,
            'groupby': groupby,
            'searchbar_filters': OrderedDict(searchbar_filters.items()),
            'filterby': filterby,
            'default_url': url,
        })
        return request.render(template, values)

    @http.route(['/my/messages', '/my/messages/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_edi_messages(self, page=1, sortby=None, search=None, search_in='edi_number', groupby=None, filterby=None, **kw):
        return self._render_edi_message_portal(
            "360_buyer_portal.portal_my_edi_messages",
            page,sortby,
            self._get_edi_message_domain(),
            "/my/messages",
            'my_messages_history',
            'edi_messages',
            'messages',
            search,search_in,groupby,filterby
        )

    @http.route(['/my/message/<int:message_id>'], type='http', auth="user", website=True)
    def portal_my_edi_message(self, message_id=None, access_token=None, **kw):
        try:
            message_sudo = self._document_check_access('vendor.edi.message', message_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        confirm_type = kw.get('confirm')
        if confirm_type == 'reminder':
            message_sudo.confirm_reminder_mail(kw.get('confirmed_date'))
        if confirm_type == 'reception':
            message_sudo._confirm_reception_mail()

        values = self._edi_message_get_page_view_values(message_sudo, access_token, **kw)
        values['update_dates'] = True
        history = request.session.get('my_messages_history', [])
        values.update(get_records_pager(history, message_sudo))
        values['is_shipping_type'] = message_sudo.message_type == 'shipping' 
        update_date = kw.get('update')
        if message_sudo.company_id:
            values['res_company'] = message_sudo.company_id
        if update_date == 'True':
            return request.render("360_buyer_portal.portal_my_edi_message_update_date", values)
        return request.render("360_buyer_portal.portal_my_edi_message", values)

    @http.route(['/my/message/<int:message_id>/update_line_dict'], type='json', auth="user", website=True)
    def update_line_dict(self, line_id, message_id=None, access_token=None,
                         product_qty_vendor=False, price_unit_vendor=False, **kwargs):
        try:
            message_sudo = self._document_check_access(
                'vendor.edi.message', message_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        write_vals = {}
        fields_logging = []
        if message_sudo.state != "ready":
            return False
        edi_message_line = request.env['vendor.edi.message.line'].sudo().browse(int(line_id))

        if product_qty_vendor:
            formated_price_value = float_repr( price_unit_vendor, message_sudo.currency_id.decimal_places)
            write_vals.update({'product_qty': product_qty_vendor})
            fields_logging.append(
                edi_message_line._prepare_field_for_log('product_qty', edi_message_line.product_qty, product_qty_vendor)
            )

        if price_unit_vendor:
            formated_price_value = float_repr(price_unit_vendor,  message_sudo.currency_id.decimal_places)
            write_vals.update({'price_unit': formated_price_value})
            fields_logging.append(
                edi_message_line._prepare_field_for_log('price_unit', edi_message_line.price_unit, formated_price_value)
            )

        try:
            edi_message_line.write(write_vals)
            msg = edi_message_line._get_tracking_field_string(message_sudo.name, fields_logging)
            message_sudo.purchase_id.message_post(body=msg,
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                            author_id=request.env.user.partner_id.id,
                            partner_ids=message_sudo.vendor_contact_ids.sudo().user_ids.ids)
            return Response(status=204)
        except ValueError:
            return request.redirect(message_sudo.get_portal_url())

    @http.route(['/my/message/<int:message_id>/update_dates'], type='json', auth="user", website=True)
    def portal_my_edi_message_update_dates(self, message_id=None, access_token=None, **kw):
        """User update vendor ETD date on purchase order line related to EDI Message.
        """
        try:
            message_sudo = self._document_check_access('vendor.edi.message', message_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        fields_logging = []
        
        if kw.get('line_id'):
            try:
                line_id = int(kw.get('line_id'))
                line = request.env['vendor.edi.message.line'].sudo().browse(line_id)
                if kw.get('date_departure'):
                    updated_date = line.po_line_id._convert_to_middle_of_day(datetime.strptime(kw.get('date_departure'), '%Y-%m-%d'))
                    fields_logging.append(line._prepare_field_for_log('date_departure', line.date_departure, updated_date))
                    line.write({'date_departure':updated_date})
                if kw.get('date_planned'):
                    updated_date = line.po_line_id._convert_to_middle_of_day(datetime.strptime(kw.get('date_planned'), '%Y-%m-%d'))
                    fields_logging.append(line._prepare_field_for_log('date_planned', line.date_planned, updated_date))
                    line.write({'date_planned':updated_date})
                msg = line._get_tracking_field_string(message_sudo.name, fields_logging)
                message_sudo.purchase_id.message_post(body=msg,
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                            author_id=request.env.user.partner_id.id,
                            partner_ids=message_sudo.vendor_contact_ids.sudo().user_ids.ids)
                return Response(status=204)
            except ValueError:
                return request.redirect(message_sudo.get_portal_url())

    @http.route(['/my/message/<int:message_id>/update_vendor_ref'], type='json', auth="user", website=True)
    def portal_my_edi_message_update_vendor_ref(self, message_id=None, access_token=None, **kw):
        """User update vendor ETD date on purchase order line related to EDI Message.
        """
        try:
            message_sudo = self._document_check_access('vendor.edi.message', message_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if kw.get('vendor_ref'):
            message_sudo.write({'partner_ref': kw.get('vendor_ref')})
        return Response(status=204)

    @http.route(['/my/message/<int:message_id>/confirm'], type='json', auth="user", website=True)
    def portal_my_edi_message_confirmation(self, message_id=None, access_token=None, **kw):
        try:
            message_sudo = self._document_check_access('vendor.edi.message', message_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        message_sudo.action_confirm()
        request.env.cr.commit()
        # Updating the partner reference in the related PO/RFQ
        message_sudo.purchase_id.partner_ref = message_sudo.partner_ref

        body = _('EDI Messsage is Processed For %s', message_sudo.partner_id.name)
        message_sudo.message_post(body=body,
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                            author_id=request.env.user.partner_id.id,
                            partner_ids=message_sudo.vendor_contact_ids.sudo().user_ids.ids)

        query_string = '&message=processed'
        return {
            'force_refresh': True,
            'redirect_url': message_sudo.get_portal_url(query_string=query_string),
        }


    @http.route('/my/message/<int:message_id>/export', type='http', auth='user')
    def export_xls(self, message_id=None, access_token=None, **kw):
        try:
            message_sudo = self._document_check_access('vendor.edi.message', message_id, access_token=access_token)
            xlsx_data = message_sudo._prepare_xlsx_report()
            report_name = 'Vendor EDI Message'
            return request.make_response(
                xlsx_data,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disposition(report_name + '.xlsx'))
                ]
            )
        except (AccessError, MissingError):
            return request.redirect('/my')
