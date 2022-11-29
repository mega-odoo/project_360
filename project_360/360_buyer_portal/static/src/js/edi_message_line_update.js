odoo.define('360_buyer_portal.edi_message_line_update', function (require) {
'use strict';

    var publicWidget = require('web.public.widget');
    var core = require('web.core');
    var _t = core._t;

    publicWidget.registry.EDIMessageUpdateLineButton = publicWidget.Widget.extend({
        selector: '.o_portal_edi_message_sidebar',

        events: {
            'click .o_confirm_edi_message_btn': '_onConfirmEDIMessage',
            'change .js_product_qty_vendor': '_onChangeQuantity',
            'change .js_price_unit_vendor': '_onChangePrice',
            'blur input.js_change_date_planned': '_onChangePlannedDate',
            'blur input.js_change_date_departure': '_onChangeDepartureDate',
            'change .js_vendor_ref_change': '_onChangeVendorRef',
        },

        /**
         * @override
         * @return {Promise}
         */
        async start() {
            await this._super(...arguments);
            this.edimessageDetail = this.$el.find('table#edi_message_table').data();
        },

        /**
         * @private
         * @param {Event} e
         */
        _onConfirmEDIMessage: function (e) {
            e.preventDefault();
            let self = this;
            this._callConfirmEDIMessageRoute(self.edimessageDetail.messageId, {
                'access_token': self.edimessageDetail.token
            }).then(function(data){
                if (data.force_refresh) {
                    window.location.reload();
                    // no resolve if we reload the page
                    return new Promise(function () { });
                }
            });
        },

        /**
         * @private
         * @param {Event} e
         */
        _onChangeQuantity(ev) {
            ev.preventDefault();
            let self = this,
                $target = $(ev.currentTarget),
                quantity = parseInt($target.val());

            this._callUpdateLineRoute(self.edimessageDetail.messageId, {
                'line_id': $target.data('lineId'),
                'product_qty_vendor': quantity >= 0 ? quantity : false,
                'access_token': self.edimessageDetail.token
            }).then(function(){
                self.displayNotification({
                    message: _t("Line Updated."),
                    type: 'success',
                    sticky: false,
                });
            });
        },

        /**
         * @private
         * @param {Event} e
         */
        _onChangePrice(ev) {
            ev.preventDefault();
            let self = this,
                $target = $(ev.currentTarget),
                price_unit_vendor = parseInt($target.val());

            this._callUpdateLineRoute(self.edimessageDetail.messageId, {
                'line_id': $target.data('lineId'),
                'price_unit_vendor': price_unit_vendor >= 0 ? price_unit_vendor : false,
                'access_token': self.edimessageDetail.token
            }).then(function(){
                self.displayNotification({
                    message: _t("Line Updated."),
                    type: 'success',
                    sticky: false,
                });
            });
        },

        /**
         * @private
         * @param {Event} e
         */
        _onChangePlannedDate(ev){
            ev.preventDefault();
            let self = this,
                momentObj = null,
                $target = $(ev.currentTarget),
                date_value = $target.val();
            momentObj = moment(date_value);
            if (momentObj.isValid()) {
                this._callUpdateDateRoute(self.edimessageDetail.messageId, {
                    'line_id': $target.data('lineId'),
                    'date_planned': date_value,
                    'access_token': self.edimessageDetail.token
                }).then(function(){
                    self.displayNotification({
                        message: _t("Line Updated."),
                        type: 'success',
                        sticky: false,
                    });
                });
            }
        },

        /**
         * @private
         * @param {Event} e
         */
        _onChangeDepartureDate(ev){
            ev.preventDefault();
            let self = this,
                momentObj = null,
                $target = $(ev.currentTarget),
                date_value = $target.val();
            momentObj = moment(date_value);
            if (momentObj.isValid()) {
                this._callUpdateDateRoute(self.edimessageDetail.messageId, {
                    'line_id': $target.data('lineId'),
                    'date_departure': date_value,
                    'access_token': self.edimessageDetail.token
                }).then(function(){
                    self.displayNotification({
                        message: _t("Line Updated."),
                        type: 'success',
                        sticky: false,
                    });
                });
            }
        },
        _callUpdateLineRoute(message_id, params) {
            return this._rpc({
                route: "/my/message/" + message_id + "/update_line_dict",
                params: params,
            });
        },
        _callUpdateDateRoute(message_id, params) {
            return this._rpc({
                route: "/my/message/" + message_id + "/update_dates",
                params: params,
            });
        },
        _callConfirmEDIMessageRoute(message_id, params) {
            return this._rpc({
                route: "/my/message/" + message_id + "/confirm",
                params: params,
            });
        },

        _onChangeVendorRef(ev) {
            ev.preventDefault();
            let self = this,
            $target = $(ev.currentTarget),
            ref_val = $target.val(),
            message_id = self.edimessageDetail.messageId,
            access_token = self.edimessageDetail.token;
            return this._rpc({
                route: "/my/message/" + message_id + "/update_vendor_ref",
                params: {
                    vendor_ref: ref_val,
                    access_token: access_token,
                }
            }).then(function(){
                self.displayNotification({
                    message: _t("Reference Updated."),
                    type: 'success',
                    sticky: false,
                });
            });
        },
    });
});
