# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import time
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from decimal import *
from .canpost_request import CanadaPostRequest
from odoo import http
import logging
from odoo.tools import pdf
from odoo.service import common

_logger = logging.getLogger(__name__)
version_info = common.exp_version()
server_serie = version_info.get('server_serie')


def _convert_weight(weight, unit='KG'):
    ''' Convert picking weight (always expressed in KG) into the specified unit '''
    if unit != False:
        if unit.upper() == 'KG':
            return weight
        elif unit.upper() == 'LB':
            return round(weight / 0.45359237, 2)
        else:
            raise ValueError
    else:
        raise ValueError


class CanadapostServiceType(models.Model):
    _name = "canadapost.service.code"
    _description = "Canada Post Service Type"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)


class CanadapostOptionType(models.Model):
    _name = "canadapost.option.type"
    _description = "Canada Post Option Type"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)


class CanadapostPaymentMethod(models.Model):
    _name = "canadapost.payment.method"
    _description = "Canada Post Payment Method"

    name = fields.Char(string='Name', required=True)


class Providercanadapost(models.Model):
    _inherit = 'delivery.carrier'
    


    if server_serie == '13.0':
        delivery_type = fields.Selection(selection_add=[('fedex', "FedEx")])
    if server_serie == '14.0':
        delivery_type = fields.Selection(selection_add=[('syncoriacanadapost', _("Canada Post"))],
                                     ondelete={'syncoriacanadapost': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})
    if server_serie == '15.0':
        delivery_type = fields.Selection(selection_add=[('syncoriacanadapost', _("Canada Post"))],
                                     ondelete={'syncoriacanadapost': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})
    canadapost_developer_username = fields.Char(
        string="Developer Username", groups="base.group_system")
    canadapost_developer_password = fields.Char(
        string="Developer Password", groups="base.group_system")
    canadapost_production_username = fields.Char(
        string="Production Username", groups="base.group_system")
    canadapost_production_password = fields.Char(
        string="Production Password", groups="base.group_system")
    canadapost_service_code = fields.Many2one(string="Service Type", comodel_name="canadapost.service.code",
                                              ondelete='set null')
    canadapost_default_packaging_id = fields.Many2one(
        'stock.package.type', string="Default Package Type")
    canadapost_weight_unit = fields.Selection(selection=[('kg', _('KG')), ('lb', _('LB'))],
                                              string="Package Weight Unit", default='kg', required=True)
    canadapost_distance_unit = fields.Selection(selection=[('in', _('IN')), ('cm', _('CM'))],
                                                string="Package Dimension Unit", default='cm', required=True)
    canadapost_option_type = fields.Many2many(
        string="Options", comodel_name="canadapost.option.type")
    canadapost_nondelivery_handling = fields.Selection(selection=[
        ('RASE', _('Return at Sender’s Expense')),
        ('RTS', _('Return to Sender')),
        ('ABAN', _('Abandon'))],
        string="Non-delivery Handling", default="RTS")
    canadapost_customer_type = fields.Selection(selection=[(
        'commercial', 'Commercial'), ('counter', 'Counter')], string="Customer Type", default='counter')
    canadapost_customer_number = fields.Char(string="Customer Number")
    canadapost_contract_id = fields.Char(string="Contract ID")
    canadapost_promo_code = fields.Char(string="Promo Code")
    canadapost_payment_method = fields.Many2one(string="Payment Method", comodel_name="canadapost.payment.method",
                                                ondelete='set null')
    canadapost_mailed_on_behalf_of = fields.Char(string="Mailed on Behalf of")
    canadapost_label_image_format = fields.Selection(selection=[('pdf', _('PDF')), ('zpl', _('ZPL'))],
                                                     string="Label Format", default='pdf')
    canadapost_void_shipment = fields.Boolean(string='Void Shipment')
    canadapost_pickup_indicator = fields.Selection(selection=[('pickup', _(
        'Pick-up')), ('deposit', _('Deposit'))], string='Pick Indicator', default='pickup')
    canadapost_country_flag = fields.Boolean(
        string='canadapost_country_flag', default=False
    )

    @api.onchange('canadapost_weight_unit')
    def _onchange_canadapost_weight_unit(self):
        if self.canadapost_weight_unit == False:
            raise UserError(_('Package Weight Unit cannot be empyty!'))

    @api.onchange('canadapost_distance_unit')
    def _onchange_canadapost_distance_unit(self):
        if self.canadapost_distance_unit == False:
            raise UserError(_('Package Dimension Unit cannot be empyty!'))

    @api.onchange('country_ids')
    def _onchange_country_ids_cnpost(self):
        if self.country_ids:
            for country in self.country_ids:
                if country.code == 'CA':
                    self.canadapost_country_flag = True

    @api.onchange('canadapost_option_type')
    def _onchange_option_type(self):
        if len(self.canadapost_option_type) > 0:
            option_codes =self.canadapost_option_type.mapped('code')
            if 'HFP' in option_codes and 'D2PO' in option_codes:
                raise UserError(_('Select one: Card for pickup or Deliver to Post Office'))

          

    @api.model
    def _set_weight_unit(self):
        uom = self.env["uom.uom"].search([('name', 'in', ['kg'])], limit=1)
        self.canadapost_weight_unit = uom.id

    def _set_pack_dimension(self):
        uom = self.env["uom.uom"].search([('name', 'in', ['cm'])], limit=1)
        self.canadapost_distance_unit = uom.id

    def get_services(self):
        superself = self.sudo()
        KEY = superself.canadapost_production_username if superself.prod_environment == True else superself.canadapost_developer_username
        PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
        des_country = superself.country_ids
        contract_id = superself.canadapost_contract_id
        origpc = superself.zip_from
        destpc = superself.zip_to

        country_code = []
        if len(des_country) > 0:
            for cn in des_country:
                country_code.append(cn.code)
        services = []
        response = {'services': []}

        css = CanadaPostRequest(request_type="services",
                                prod_environment=self.prod_environment)
        css.web_authentication_detail(KEY, PASS)
        if country_code:
            if len(country_code) > 0:
                for code in country_code:
                    response['services'] += css.get_services(
                        code, contract_id, origpc, destpc)
        if not country_code:
            response = css.get_services(
                country_code, contract_id, origpc, destpc)
        Service = self.env['canadapost.service.code'].sudo()
        if response.get('services'):
            services = response.get('services')
            if len(services) > 0:
                for service in services:
                    if len(Service.search([('code', '=', service.get('service-code'))])) == 0:
                        Service.create({
                            'code': service.get('service-code'),
                            'name': service.get('service-name'),
                        })

    def _compute_can_generate_return(self):
        super(Providercanadapost, self)._compute_can_generate_return()
        for carrier in self:
            if not carrier.can_generate_return:
                if carrier.delivery_type == 'canadapost':
                    carrier.can_generate_return = True

    # def canadapost_service_options(self, order, ship_date):
    #     superself = self.sudo()
    #     KEY = superself.canadapost_production_key if superself.prod_environment == True else superself.canadapost_developer_key
    #     PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
    #     val = canadapostRequest(self.log_xml, request_type="services", prod_environment=self.prod_environment,canadapost_activation_key=self.canadapost_activation_key)
    #     val.web_authentication_detail(KEY, PASS)
    #     val_req = val.address_validate(order.company_id.partner_id, order.partner_id)
    #     if not val_req.get('errors_message'):
    #         srm = canadapostRequest(self.log_xml, request_type="services", prod_environment=self.prod_environment,canadapost_activation_key=self.canadapost_activation_key)
    #         srm.web_authentication_detail(KEY, PASS)
    #         request = srm.service_options(order.warehouse_id.partner_id, order.partner_shipping_id, self.canadapost_billing_account,ship_date )
    #         warnings = request.get('warnings_message')
    #         if warnings:
    #             _logger.info(warnings)
    #         if not request.get('errors_message'):
    #             services = request.get('services')
    #         else:
    #             if request.get('errors_message') == (401, 'Unauthorized'):
    #                 request['errors_message'] = "Wrong canadapost Credentials. Please provide correct credentials in canadapost Confirguration."
    #             return {'success': False,
    #                     'services':services,
    #                     'error_message': _('Error:\n%s') % str(request['errors_message']),
    #                     'warning_message': False}
    #     else:
    #         return {'success': False,
    #                     'services': services,
    #                     'error_message': _('Error:\n%s') % str(val_req['errors_message']),
    #                     'warning_message': False}
    #     return {'success': True,
    #             'services': services,
    #             'error_message': False,
    #             'warning_message': _('Warning:\n%s') % warnings if warnings else False}

    def syncoriacanadapost_rate_shipment(self, order):
        max_weight = self._syncoriacanadapost_convert_weight(
            self.canadapost_default_packaging_id.max_weight, self.canadapost_weight_unit)
        price = 0.0
        # Issue here
        if order.carrier_id:
            choice = self.env['choose.delivery.carrier'].search(
                [('order_id', '=', order.id), ('carrier_id', '=', order.carrier_id.id)], order='id desc', limit=1)
        else:
            choice = self.env['choose.delivery.carrier'].search(
                [('order_id', '=', order.id), ('carrier_id', '=', self.id)], order='id desc', limit=1)
        # if len(choice) == 1 and choice.canadapost_total_weight:
        # if len(choice) == 1:
        #     est_weight_value = max_weight
        # else:
        est_weight_value = sum([(line.product_id.weight * line.product_uom_qty)
                                for line in order.order_line if not line.display_type]) or 0.0
        weight_value = self._syncoriacanadapost_convert_weight(
            est_weight_value, self.canadapost_weight_unit)



        if weight_value == 0.0:
            weight_value = 0.45 if self.canadapost_weight_unit == 'KG' else 1.00

        superself = self.sudo()

        # Authentication stuff
        KEY = superself.canadapost_production_username if superself.prod_environment == True else superself.canadapost_developer_username
        PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
        des_country = superself.country_ids
        contract_id = superself.canadapost_contract_id
        origpc = superself.zip_from
        destpc = superself.zip_to
        service_type = superself.canadapost_service_code
        srm = CanadaPostRequest(request_type="rating", prod_environment=superself.prod_environment,
                                customer_number=superself.canadapost_customer_number, contract_id=superself.canadapost_contract_id)
        if srm:
            srm.web_authentication_detail(KEY, PASS)
            srm.set_shipper(order.company_id.partner_id,
                            order.warehouse_id.partner_id)
            srm.set_recipient(order.partner_shipping_id)
            # Notification
            # if 'D2PO' in order.carrier_id.canadapost_option_type.mapped('code'):
            #     srm.set_notification(order.partner_shipping_id, "true", "true", "true")

            pkg = self.canadapost_default_packaging_id
            if max_weight and weight_value > max_weight:
                total_package = int(weight_value / max_weight)
                last_package_weight = round(weight_value % max_weight,2)

                for sequence in range(1, total_package + 1):
                    srm.add_package(
                        max_weight,
                        package_code=pkg.shipper_package_code,
                        package_height=pkg.height,
                        package_width=pkg.width,
                        package_length=pkg.packaging_length,
                        sequence_number=sequence,
                        mode='rating',
                    )
                if last_package_weight:
                    total_package = total_package + 1
                    srm.add_package(
                        last_package_weight,
                        package_code=pkg.shipper_package_code,
                        package_height=pkg.height,
                        package_width=pkg.width,
                        package_length=pkg.packaging_length,
                        sequence_number=total_package,
                        mode='rating',
                    )
                # srm.set_master_package(weight_value, total_package)
            else:
                srm.add_package(
                    weight_value,
                    package_code=pkg.shipper_package_code,
                    package_height=pkg.height,
                    package_width=pkg.width,
                    package_length=pkg.packaging_length,
                    mode='rating',
                )
            #     srm.set_master_package(weight_value, 1)
            packages = []
            request = srm.rate(self.canadapost_service_code, packages,
                               weight_value, order, self.canadapost_option_type, self.canadapost_nondelivery_handling)
            warnings = request.get('warnings_message')
            if warnings:
                _logger.warning(warnings)
            if not request.get('errors_message'):
                ShipmentEstimate = request.get('ShipmentEstimate')
                if len(ShipmentEstimate) > 0:
                    price = ShipmentEstimate[0].get(
                        'price-details', {}).get('due')
                choice = self.env['choose.delivery.carrier'].search(
                    [('order_id', '=', order.id), ('carrier_id', '=', self.id)], order='id desc', limit=1)
                choice.canadapost_service_type = False  # self.canadapost_service_code
                sers = self.env['canadapost.service'].sudo().search(
                    [('order_id', '=', order.id)])
                for ser in sers:
                    ser.sudo().write({'active': False})
                for rating in ShipmentEstimate:
                    surcharges_total = Decimal('0.0')
                    if rating.get('Surcharges',{}).get('Surcharge'):
                        for item in rating['Surcharges']['Surcharge']:
                            surcharges_total += item['Amount']
                    taxes_total = Decimal('0.0')
                    if rating.get('Taxes',{}).get('Tax'):
                        for item in rating['Taxes']['Tax']:
                            taxes_total += item['Amount']
                    options_total = Decimal('0.0')
                    if rating.get('OptionPrices',{}).get('OptionPrice'):
                        for item in rating['OptionPrices']['OptionPrice']:
                            options_total += item['Amount']
                  
                    rates = []
                    
                    
                    rate = self.env['canadapost.service'].sudo().create(
                        {
                            'service_name': rating.get('service-name'),
                            'service_code': rating.get('service-code'),
                            'shipment_date':   rating.get('ShipmentDate') or order.commitment_date,
                            'expected_delivery_date':   rating.get('service-standard', {}).get('expected-delivery-date') or rating.ExpectedDeliveryDate,
                            'expected_transit_days':   rating.get('service-standard', {}).get('expected-transit-time') or rating.EstimatedTransitDays,
                            'base_price':   rating.get('price-details').get('base') or rating.BasePrice,
                            'surcharges':   float(surcharges_total),
                            'taxes':   float(taxes_total),
                            'options':   float(options_total),
                            'total_price':   rating.get('price-details', {}).get('due') or rating.TotalPrice,
                            'order_id':   order.id,
                            'choise_id': choice.id,
                        })
                    if rate:
                        rates.append(rate.id)
                        rating['service_id'] = str(rate.id)
                    if rating.get('service-name') == self.canadapost_service_code.name:
                        choice.canadapost_service_type = rate.id
                canadapost_service_type = self.env['canadapost.service'].sudo().search(
                    [('order_id', '=', order.id), ('active', '=', True)])
            else:
                if request.get('errors_message') == (401, 'Unauthorized'):
                    request['errors_message'] = "Wrong canadapost Credentials. Please provide correct credentials in canadapost Confirguration."
                return {'success': False,
                        'price': 0.0,
                        'ShipmentEstimate': [],
                        'error_message': _('Error:\n%s') % str(request['errors_message']),
                        'canadapost_service_type': [],
                        'warning_message': False}
        else:
            return {'success': False,
                    'price': 0.0,
                    'ShipmentEstimate': [],
                    'error_message': _('Error:'),
                    'canadapost_service_type': [],
                    'warning_message': False}

        return {'success': True,
                'price': price,
                'ShipmentEstimate': ShipmentEstimate,
                'error_message': False,
                'canadapost_service_type': canadapost_service_type,
                'warning_message': _('Warning:\n%s') % warnings if warnings else False}

    def syncoriacanadapost_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            superself = self.sudo()
            KEY = superself.canadapost_production_username if superself.prod_environment == True else superself.canadapost_developer_username
            PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
            des_country = superself.country_ids
            contract_id = superself.canadapost_contract_id
            origpc = superself.zip_from
            destpc = superself.zip_to
            service_type = superself.canadapost_service_code
            request_type = "ncshipping" if superself.canadapost_customer_type == 'counter' else "shipping"
            srm = CanadaPostRequest(request_type=request_type, prod_environment=superself.prod_environment,
                                    customer_number=superself.canadapost_customer_number, contract_id=superself.canadapost_contract_id)
            srm.web_authentication_detail(KEY, PASS)
            
            packages = picking.package_ids
            est_weight_value = sum([pack.weight for pack in packages])
            weight_value = self._syncoriacanadapost_convert_weight(
                est_weight_value, self.canadapost_weight_unit)
            package_type = picking.package_ids and picking.package_ids[
                0].package_type_id.shipper_package_code or self.canadapost_default_packaging_id.shipper_package_code
            if weight_value == 0.0:
                if self.canadapost_weight_unit == 'KG':
                    weight_value = 0.45
                else:
                    weight_value = 1.00

            order = picking.sale_id
            company = order.company_id or picking.company_id or self.env.company
            order_currency = picking.sale_id.currency_id or picking.company_id.currency_id
            net_weight = self._syncoriacanadapost_convert_weight(
                picking.shipping_weight, self.canadapost_weight_unit)
            srm.set_shipper(picking.sale_id.company_id,
                            picking.sale_id.warehouse_id)
            srm.set_recipient(picking.sale_id.partner_shipping_id)
            sprate = True if picking.sale_id.partner_shipping_id.country_id.code != 'CA' else False
            sivalue = True if picking.sale_id.partner_shipping_id.country_id.code != 'CA' else False
            srm.set_preferences(True, sprate, sivalue)
            # Add options

            # 
            package_count = len(picking.package_ids) or 1

            po_number = order.display_name or False
            dept_number = False
            carrier_price = 0.0
            for line in order.order_line:
                if line.is_delivery == True:
                    carrier_price = line.price_subtotal

            ################
            # Multipackage #
            ################
            if package_count > 1:
                # Create multiple shipments for Packages
                master_tracking_id = False
                package_labels = []
                carrier_tracking_ref = ""

                for sequence, package in enumerate(picking.package_ids, start=1):
                    package_weight = self._syncoriacanadapost_convert_weight(
                        package.shipping_weight, self.canadapost_weight_unit)
                    packaging = package.packaging_id

                    srm._add_package(
                        package_weight,
                        package_code=packaging.shipper_package_code,
                        package_height=packaging.height,
                        package_width=packaging.width,
                        package_length=packaging.packaging_length,
                        sequence_number=sequence,
                        po_number=po_number,
                        dept_number=dept_number,
                        reference=picking.display_name,
                    )
                    # srm.set_master_package(net_weight, package_count, master_tracking_id=master_tracking_id)
                    package_name = package.name or sequence
                    request = srm.process_shipment(
                        picking, self.canadapost_option_type, self.canadapost_nondelivery_handling, package_name)

                    warnings = request.get('warnings_message')
                    if warnings:
                        _logger.info(warnings)

                    if sequence == 1:
                        if not request.get('errors_message'):
                            master_tracking_id = request['master_tracking_id']
                            carrier_tracking_ref = request.get(
                                'master_tracking_id')
                            picking._set_links(request.get('links')) if request.get(
                                'links') else False
                            label_urls = list(filter(None, [link.get(
                                '@href') if link.get('@rel') == 'label' else False for link in request.get('links')]))
                            for url in label_urls:
                                bytepdf = self.get_pdf_byte(
                                    carrier_tracking_ref, url, '.pdf')
                                if bytepdf != False:
                                    # PDF_NAME = 'LabelCanadaPost-%s.%s' % (carrier_tracking_ref, self.canadapost_label_image_format)
                                    package_labels.append(
                                        (package_name, bytepdf))
                            carrier_tracking_ref = request['tracking_number']

                        else:
                            raise UserError(request['errors_message'])
                    # Intermediary packages
                    elif sequence > 1 and sequence < package_count:
                        if not request.get('errors_message'):
                            for url in get_label_url['url']:
                                bytepdf = self.get_pdf_byte(url)
                                # PDF_NAME = 'LabelCanadaPost-%s.%s' % (carrier_tracking_ref, self.canadapost_label_image_format)
                                package_labels.append((package_name, bytepdf))
                            carrier_tracking_ref = carrier_tracking_ref + \
                                "," + request['tracking_number']
                        else:
                            raise UserError(request['errors_message'])
                    # Last package
                    elif sequence == package_count:
                        if not request.get('errors_message'):
                            picking._set_links(request.get('links')) if request.get(
                                'links') else False

                            label_urls = list(filter(None, [link.get(
                                '@href') if link.get('@rel') == 'label' else False for link in request.get('links')]))
                            for url in label_urls:
                                bytepdf = self.get_pdf_byte(
                                    carrier_tracking_ref, url, '.pdf')
                                if bytepdf != False:
                                    # PDF_NAME = 'LabelCanadaPost-%s.%s' % (carrier_tracking_ref, self.canadapost_label_image_format)
                                    package_labels.append(
                                        (package_name, bytepdf))
                                    order_currency = picking.sale_id.currency_id or self.company_id.currency_id

                            carrier_tracking_ref = carrier_tracking_ref + \
                                "," + request['tracking_number']

                            logmessage = _("Shipment created into Canadapost<br/>"
                                           "<b>Tracking Numbers:</b> %s<br/>"
                                           "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join([pl[0] for pl in package_labels]))
                            attachments = [('Labelcanadapost-' + carrier_tracking_ref +
                                            '.pdf', pdf.merge_pdf([pl[1] for pl in package_labels]))]
                            picking.message_post(
                                body=logmessage, attachments=attachments)
                            shipping_data = {'exact_price': carrier_price,
                                             'tracking_number': carrier_tracking_ref}
                            res = res + [shipping_data]
                        else:
                            raise UserError(request['errors_message'])

            ###############
            # One package #
            ###############
            elif package_count == 1:

                packaging = picking.package_ids[:1].package_type_id or picking.carrier_id.canadapost_default_packaging_id
                srm._add_package(
                    net_weight,
                    package_code=packaging.shipper_package_code,
                    package_height=packaging.height,
                    package_width=packaging.width,
                    package_length=packaging.packaging_length,
                    po_number=po_number,
                    dept_number=dept_number,
                    reference=picking.display_name,
                )
                if picking.sale_id.partner_shipping_id.country_id.code not in ['CA']:
                    srm.set_customs(picking, picking.package_ids)

                # srm.set_master_package(net_weight, 1)
                package_name = picking.package_ids.name
                request = srm.process_shipment(
                    picking, self.canadapost_option_type, self.canadapost_nondelivery_handling,package_name)
                warnings = request.get('errors_message')
                if warnings:
                    _logger.warning(warnings)
                if not request.get('errors_message'):
                    carrier_tracking_ref = request.get('master_tracking_id')
                    if order.order_line[-1].name.split(" ")[0] == 'syncoriacanadapost':
                        carrier_price = order.order_line[-1].price_subtotal
                    if carrier_tracking_ref:
                        package_labels = []
                        picking._set_links(request.get('links')) if request.get(
                            'links') else False
                        label_urls = list(filter(None, [link.get(
                            '@href') if link.get('@rel') == 'label' else False for link in request.get('links')]))
                        for url in label_urls:
                            bytepdf = self.get_pdf_byte(
                                carrier_tracking_ref, url, '.pdf')
                            if bytepdf != False:
                                package_labels.append((package_name, bytepdf))
                                order_currency = picking.sale_id.currency_id or self.company_id.currency_id
                                logmessage = _("Shipment created into Canadapost<br/>"
                                               "<b>Tracking Numbers:</b> %s<br/>"
                                               "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join([pl[0] for pl in package_labels]))
                                attachments = [('Labelcanadapost-' + carrier_tracking_ref +
                                                '.pdf', pdf.merge_pdf([pl[1] for pl in package_labels]))]
                                picking.message_post(
                                    body=logmessage, attachments=attachments)
                        shipping_data = {'exact_price': carrier_price,
                                         'tracking_number': carrier_tracking_ref}
                        res = res + [shipping_data]
                else:
                    raise UserError(request.get('errors_message'))

            ##############
            # No package #
            ##############
            else:
                raise UserError(_('No packages for this picking'))
            return res

    def syncoriacanadapost_get_tracking_link(self, picking):
        return 'https://www.canadapost-postescanada.ca/track-reperage/en#/resultList?searchFor=%s' % picking.carrier_tracking_ref

    def syncoriacanadapost_cancel_shipment(self, picking):
        raise UserError(_("You can't cancel canadapost shipping."))
        # picking.message_post(body=_(u"You can't cancel canadapost shipping."))
        # picking.write({'carrier_tracking_ref': '', 'carrier_price': 0.0})

    def _syncoriacanadapost_convert_weight(self, weight, unit='KG'):
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter(
        )
        if unit.upper() == 'KG':
            return weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_kgm'), round=False)
        elif unit.upper() == 'LB':
            return weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_lb'), round=False)
        else:
            raise ValueError

    def get_pdf_byte(self, TrackingPIN, url, FileFormat):
        srm = CanadaPostRequest(request_type="label")
        superself = self.sudo()
        KEY = superself.canadapost_production_username if superself.prod_environment == True else superself.canadapost_developer_username
        PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
        srm.web_authentication_detail(KEY, PASS)
        try:
            myfile = srm.get_label_url(TrackingPIN, url, '.pdf')
            if myfile.get('status_code') == 200:
                bytepdf = bytearray(myfile.get('pdf_data'))
                return bytepdf
            else:
                return False
        except Exception as e:
            print(e.args)

    # @api.model
    # def get_canadapost_rates(self, order, partner_shipping_id, partner_id, packages, customer_number):
    #     is_frontend = False if http.request.is_frontend == False else True
    #     if not packages:
    #         raise UserError(_('Select packages for this shipment.'))
    #     product_weight = sum([(line.product_qty*line.product_id.weight) for line in order.order_line]) or 0.0
    #     packages_weight = sum([(pack.shipping_weight) for pack in packages]) or 0.0
    #     if packages_weight < product_weight:
    #         raise UserError(_('Package Weights must be same or greater than Product Weights. Increase Package Weight.'))
    #     parcels = []
    #     # _convert_weight(weight,unit)
    #     for package in packages:
    #         packaging_id = package.packaging_id
    #         parcel = {
    #             "length": str(packaging_id.packaging_length),
    #             "width": str(packaging_id.width),
    #             "height": str(packaging_id.height),
    #             "distance_unit": self.canadapost_distance_unit,
    #             "mass_unit": self.canadapost_weight_unit
    #         }
    #         if packaging_id.shipper_package_code:
    #             parcel['template'] = packaging_id.shipper_package_code
    #         parcel['weight'] = _convert_weight(package.shipping_weight,self.canadapost_weight_unit) if package.shipping_weight else _convert_weight(packaging_id.max_weight,self.canadapost_weight_unit)
    #         parcels.append(parcel)

    #     # Call Rating
    #     order_currency = order.currency_id
    #     superself = self.sudo()
    #     # Authentication stuff
    #     KEY = superself.canadapost_production_username if superself.prod_environment == True else superself.canadapost_developer_username
    #     PASS = superself.canadapost_production_password if superself.prod_environment == True else superself.canadapost_developer_password
    #     des_country = superself.country_ids
    #     contract_id = superself.canadapost_contract_id
    #     origpc = superself.zip_from
    #     destpc = superself.zip_to
    #     service_type = superself.canadapost_service_code

    #     srm = CanadaPostRequest(request_type="rating", prod_environment=superself.prod_environment,customer_number=superself.canadapost_customer_number)
    #     if srm:
    #         srm.web_authentication_detail(KEY, PASS)
    #         srm.set_shipper(order.company_id.partner_id, order.warehouse_id.partner_id)
    #         srm.set_recipient(order.partner_shipping_id)
    #         packages = []
    #         weight_value = '1'
    #         rateRes = srm.rate(self.canadapost_service_code, packages, weight_value, order)
    #         if rateRes.get('errors_message'):
    #             warnings = rateRes.get('errors_message')
    #             _logger.warning(warnings)
    #             UserError(_(rateRes.get('errors_message')))
    #         else:
    #             ShipmentEstimate = rateRes.get('ShipmentEstimate')
    #             # price = rateRes['price']['TotalPrice']
    #             # choice = self.env['choose.delivery.carrier'].search([('order_id','=',order.id),('carrier_id','=',self.id)],order='id desc',limit=1)
    #             # choice.canadapost_service_code = self.canadapost_service_code.id
    #             return rateRes
