from odoo import http, _
from odoo.http import request, content_disposition
from odoo.exceptions import AccessError, MissingError
from odoo.addons.purchase.controllers import portal


class CustomerPortalInherit(portal.CustomerPortal):

    @http.route()
    def portal_my_purchase_orders(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        return self._render_portal(
            "purchase.portal_my_purchase_orders",
            page, date_begin, date_end, sortby, filterby,
            [],
            {
                'all': {'label': _('All'), 'domain': [('state', 'in', ['purchase', 'done', 'cancel'])]},
                'purchase': {'label': _('Purchase Order'), 'domain': [('state', '=', 'purchase')]},
                'waiting': {'label': _('Waiting Another Operation'), 'domain': [('picking_ids.state', '=', 'waiting')]},
                'confirmed': {'label': _('Waiting'), 'domain': [('picking_ids.state', '=', 'confirmed')]},
                'assigned': {'label': _('Ready'), 'domain': [('picking_ids.state', '=', 'assigned')]},
                'cancel': {'label': _('Cancelled'), 'domain': ['|', ('state', '=', 'cancel'), ('picking_ids.state', '=', 'cancel')]},
                'done': {'label': _('Locked'), 'domain': ['|', ('state', '=', 'done'), ('picking_ids.state', '=', 'done')]},
                'cancelled': {'label': _('Reception Status = cancelled'), 'domain': [('reception_status', '=', 'cancel')]},
                'Nothing': {'label': _('Reception Status = Nothing'), 'domain': [('reception_status', '=', 'no')]},
                'partial received': {'label': _('Reception Status = partial received'), 'domain': [('reception_status', '=', 'partial')]},
                'received': {'label': _('Reception Status = Received'), 'domain': [('reception_status', '=', 'received')]},
            },
            'all',
            "/my/purchase",
            'my_purchases_history',
            'purchase',
            'orders'
        )

    @http.route('/my/purchase/<int:order_id>/export', type='http', auth='user')
    def purchase_export_xls(self, order_id=None, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
            xlsx_data = order_sudo._prepare_po_xlsx_report()
            report_name = 'Purchase Order' if order_sudo.state in ('purchase', 'done', 'cancel') else 'Request for Quotation'
            return request.make_response(
                xlsx_data,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disposition(report_name + '.xlsx'))
                ]
            )
        except (AccessError, MissingError):
            return request.redirect('/my')



