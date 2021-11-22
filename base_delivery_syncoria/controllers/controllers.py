# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################


from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery
from werkzeug.utils import redirect
from decimal import *

show_services = ['PurolatorExpress','PurolatorExpressU.S.','PurolatorExpressInternational','PurolatorGround']      

class WebsiteSaleDeliveryInherit(WebsiteSaleDelivery):

    @http.route(['/shop/update_carrier'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def update_eshop_carrier(self, **post):
        order = request.website.sale_get_order()
        carrier_id = int(post['carrier_id'])
        if order:
            order._check_carrier_quotation(force_carrier_id=carrier_id)
        service_id = ''
        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))   
        
        #For Delivery Purolator
        purolator_service_rates = []
        minimum_rate = 0
        if carrier.delivery_type == 'purolator':
            choice = request.env['choose.delivery.carrier'].sudo().search([('order_id','=',order.id),('carrier_id','=',order.carrier_id.id)],order='id desc',limit=1)
            purolator_service_type = request.env['purolator.service'].sudo().search([('choise_id','=',choice.id),('active','=',True)])
            select_service = False
            if purolator_service_type:
                minimum_rate = purolator_service_type[0].total_price
                for record in purolator_service_type:
                    if record.service_id in show_services:
                        if record.total_price  < minimum_rate:
                            minimum_rate = record.total_price
                            select_service = record.id
                        name = record.service_id + ',Shipping Cost: \n ' + str(record.total_price) + ',\n Expected Delivery Date: ' + str(record.expected_delivery_date)
                        purolator_service_rates.append({
                            'value':record.id,
                            'name':name,
                            'total_price': record.total_price,
                            'service_id' : record.service_id ,
                            'shipment_date' :   record.shipment_date,
                            'expected_delivery_date' :   record.expected_delivery_date,
                            'expected_transit_days' :   record.expected_transit_days,
                            'base_price' :   record.base_price,
                            'surcharges' :  record.surcharges,
                            'taxes' :   record.taxes,
                            'options' :   record.options,
                            'total_price' :   record.total_price,
                            'order_id' :   record.order_id.id,
                            'choise_id': record.choise_id.id,
                        })
            update_delivery_line = order.update_delivery_line(select_service)
            delivery_line = order.order_line.filtered('is_delivery')
            for service in request.env['purolator.service'].sudo().search([('order_id','=',order.id)]):
                if service.total_price == delivery_line.price_subtotal:   
                    service_id = service.id
            post['service_id'] = service_id

        post['purolator_service_rates'] = purolator_service_rates
        
        #For Delivery Canada Post
        cnpost_service_rates = []
        minimum_rate = 0
        if carrier.delivery_type == 'syncoriacanadapost':
            choice = request.env['choose.delivery.carrier'].sudo().search([('order_id','=',order.id),('carrier_id','=',order.carrier_id.id)],order='id desc',limit=1)
            cnpost_service_type = request.env['canadapost.service'].sudo().search([('choise_id','=',choice.id),('active','=',True)])
            select_service = False
            if cnpost_service_type:
                minimum_rate, select_service = cnpost_service_type[0].total_price, cnpost_service_type[0].id
                for record in cnpost_service_type:
                    if record.total_price  < minimum_rate:
                        minimum_rate, select_service = record.total_price, record.id
                    name = record.service_code + ',Shipping Cost: \n ' + str(record.total_price) + ',\n Expected Delivery Date: ' + str(record.expected_delivery_date)
                    cnpost_service_rates.append({
                        'value':record.id,
                        'name':name,
                        'total_price': record.total_price,
                        'service_code' : record.service_code ,
                        'service_name' : record.service_name ,
                        'shipment_date' :   record.shipment_date,
                        'expected_delivery_date' :   record.expected_delivery_date,
                        'expected_transit_days' :   record.expected_transit_days,
                        'base_price' :   record.base_price,
                        'surcharges' :  record.surcharges,
                        'taxes' :   record.taxes,
                        'options' :   record.options,
                        'total_price' :   record.total_price,
                        'order_id' :   record.order_id.id,
                        'choise_id': record.choise_id.id,
                    })

            update_delivery_line = order.update_delivery_line(select_service)

            delivery_line = order.order_line.filtered('is_delivery')
            for service in request.env['canadapost.service'].sudo().search([('order_id','=',order.id)]):
                if service.total_price == delivery_line.price_subtotal:   
                    service_code = service.id
                    post['service_code'] = service_code
                    post['service_id'] = service_code

        post['cnpost_service_rates'] = cnpost_service_rates

        return self._update_website_sale_delivery_return(order, **post)

    @http.route(['/shop/carrier_rate_shipment'], type='json', auth='public', methods=['POST'], website=True)
    def cart_carrier_rate_shipment(self, carrier_id, **kw):
        order = request.website.sale_get_order(force_create=True)
        assert int(carrier_id) in order._get_delivery_methods().ids, "unallowed carrier"
        Monetary = request.env['ir.qweb.field.monetary']
        res = {'carrier_id': carrier_id}
        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))    
        rate = carrier.rate_shipment(order) 

        #For Delivery Purolator
        service_id = ''
        minimum_rate = 0
        purolator_service_rates = []
        if carrier.delivery_type == 'purolator':
            purolator_service_type = request.env['purolator.service'].sudo().search([('order_id','=',order.id)])
            if purolator_service_type:
                minimum_rate = purolator_service_type[0].total_price
                for record in purolator_service_type:
                    name = record.service_id + ', Shipping Cost: ' + str(record.total_price) + ', Expected Delivery Date: ' + str(record.expected_delivery_date)
                    purolator_service_rates.append({
                        'value':record.id,
                        'name':name
                    })
                    if record.service_id in show_services:
                        if record.total_price  < minimum_rate:
                            minimum_rate = record.total_price
                            service_id = record.id   
                        update_delivery_line = order.update_delivery_line(service_id)

        #For Delivery Canada Post
        cnpost_service_rates = []
        service_code,  minimum_rate = '', 0
        if carrier.delivery_type == 'syncoriacanadapost':
            cnpost_service_type = request.env['canadapost.service'].sudo().search([('order_id','=',order.id)])
            if cnpost_service_type:
                service_code = cnpost_service_type[0].id
                minimum_rate = cnpost_service_type[0].total_price
                for record in cnpost_service_type:
                    name = record.service_code + ', Shipping Cost: ' + str(record.total_price) + ', Expected Delivery Date: ' + str(record.expected_delivery_date)
                    cnpost_service_rates.append({
                        'value':record.id,
                        'name':name
                    })
                    if record.total_price  < minimum_rate:
                        minimum_rate, service_code = record.total_price, record.id   
                    update_delivery_line = order.update_delivery_line(service_code)
                         
        ShipmentEstimate = rate.get('ShipmentEstimate')
        if ShipmentEstimate != None:
            ShipmentEstimate = self.process_rate_purolator(ShipmentEstimate,order)        
        if rate.get('success'):
            res['status'] = True
            res['new_amount_delivery'] = Monetary.value_to_html(minimum_rate, {'display_currency': order.currency_id})
            res['is_free_delivery'] = not bool(minimum_rate)
            res['error_message'] = rate['warning_message']
            res['service_id'] = str(service_id)
            res['ShipmentEstimate'] = rate.get('ShipmentEstimate')
            res['purolator_service_type'] = purolator_service_rates
            res['free_delivery'] = rate.get('free_delivery')
            res['cnpost_service_rates'] = cnpost_service_rates
        else:
            res['status'] = False
            res['new_amount_delivery'] = Monetary.value_to_html(0.0, {'display_currency': order.currency_id})
            res['error_message'] = rate['error_message']
            res['ShipmentEstimate'] = []
            res['purolator_service_type'] = purolator_service_rates
            res['service_id'] = str(service_id)
            res['cnpost_service_rates'] = cnpost_service_rates
        return res

    def _update_website_sale_delivery_return(self, order, **post):
        Monetary = request.env['ir.qweb.field.monetary']
        carrier_id = int(post['carrier_id'])
        currency = order.currency_id
        carrier = request.env['delivery.carrier'].sudo().search([('id','=',carrier_id)])
        free_delivery = False
        if carrier:
            if carrier.delivery_type == 'purolator' or carrier.delivery_type == 'syncoriacanadapost':
                if post.get('purolator_service_rates') and carrier.free_over and order._compute_amount_total_without_delivery() >= carrier.amount:

                    order.amount_delivery = 0.0
                    order._remove_delivery_line()
                    free_delivery = True
            if carrier.delivery_type == 'syncoriacanadapost':
                if post.get('cnpost_service_rates') and carrier.free_over and order._compute_amount_total_without_delivery() >= carrier.amount:

                    order.amount_delivery = 0.0
                    order._remove_delivery_line()
                    free_delivery = True
        if order:
            return {
                'status': order.delivery_rating_success,
                'error_message': order.delivery_message,
                'carrier_id': carrier_id,
                'is_free_delivery': not bool(order.amount_delivery),
                'new_amount_delivery': Monetary.value_to_html(order.amount_delivery, {'display_currency': currency}),
                'new_amount_untaxed': Monetary.value_to_html(order.amount_untaxed, {'display_currency': currency}),
                'new_amount_tax': Monetary.value_to_html(order.amount_tax, {'display_currency': currency}),
                'new_amount_total': Monetary.value_to_html(order.amount_total, {'display_currency': currency}),
                'purolator_service_rates': post['purolator_service_rates'],
                'service_id': post.get('service_id'),
                'free_delivery':free_delivery,
                'cnpost_service_rates': post['cnpost_service_rates'],
            }
        return {}

    @http.route(['/shop/update_carrier_service'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def get_total_price(self, **post):
        order = request.website.sale_get_order()
        Monetary = request.env['ir.qweb.field.monetary']
        currency = order.currency_id
        update_delivery_line = order.update_delivery_line(post['service_id'])
        if post and update_delivery_line['status'] == True:
            data= {
                'status':True,
                'new_amount_delivery': Monetary.value_to_html(update_delivery_line['new_service_rate'], {'display_currency': currency}), 
                'new_amount_untaxed': Monetary.value_to_html(order.amount_untaxed, {'display_currency': currency}), 
                'new_amount_tax': Monetary.value_to_html(order.amount_tax, {'display_currency': currency}), 
                'new_amount_total': Monetary.value_to_html(order.amount_total, {'display_currency': currency}), 
            }
        else:
             data= {
                'status':False,
                'new_amount_delivery':Monetary.value_to_html(0, {'display_currency': currency}),
                'new_amount_untaxed':Monetary.value_to_html(0, {'display_currency': currency}),
                'new_amount_tax':Monetary.value_to_html(0, {'display_currency': currency}),
                'new_amount_total':Monetary.value_to_html(0, {'display_currency': currency}),
            }      
        return data

    def process_rate_purolator(self, datas, order):
        Monetary = request.env['ir.qweb.field.monetary']
        if len(datas) > 0:
            for data in datas:
                surcharges_total = Decimal('0.0')
                try:
                    for item in data['Surcharges']['Surcharge']:
                        surcharges_total += item['Amount']
                    taxes_total = Decimal('0.0')
                    for item in data['Taxes']['Tax']:
                        taxes_total += item['Amount']
                    options_total = Decimal('0.0')
                    for item in data['OptionPrices']['OptionPrice']:
                        options_total += item['Amount']
                    BasePrice = data['BasePrice']
                    TotalPrice = data['TotalPrice']

                except Exception as e:
                    surcharges_total = data.get('price-details').get('due')
                    taxes_total = float(data.get('price-details').get('taxes').get('gst').get('#text')) + \
                        float(data.get('price-details').get('taxes').get('hst')) + float(data.get('price-details').get('taxes').get('pst'))
                    options_total = float(data.get('price-details').get('options').get('option').get('option-price')) 
                    BasePrice = float(data.get('price-details').get('base')) 
                    TotalPrice =  float(data.get('price-details').get('due')) 

                data['surcharges_total'] =  Monetary.value_to_html(float(surcharges_total), {'display_currency': order.currency_id})
                data['taxes_total'] = Monetary.value_to_html(float(taxes_total), {'display_currency': order.currency_id}) 
                data['options_total'] = Monetary.value_to_html(float(options_total), {'display_currency': order.currency_id})
                data['BasePrice'] = Monetary.value_to_html(float(BasePrice), {'display_currency': order.currency_id})
                data['TotalPrice'] = Monetary.value_to_html(float(TotalPrice), {'display_currency': order.currency_id})
        return datas
