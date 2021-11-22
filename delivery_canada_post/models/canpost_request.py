# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import requests
import base64
from ..lib import shipRequest
import xmltodict
import collections
import logging
from pprint import pprint

_logger = logging.getLogger(__name__)

# STATECODE_REQUIRED_COUNTRIES = ['US', 'CA', 'PR ', 'IN']


class CanadaPostRequest():
    """ Low-level object intended to interface Odoo recordsets with Canada Post, through appropriate REST-API requests """

    def __init__(self, request_type="ncshipping", prod_environment=False, customer_number=False, contract_id=False, pin_number=False, language=False):
        self.hasOnePackage = False
        self.prod_environment = prod_environment
        self.headers = {}
        self.customer_number = customer_number
        self.contract_id = contract_id
        self.destpc = ''
        self.originpc = ''
        self.request_type = request_type
        self.sender = None
        self.receiver = None
        self.parcel_characteristics = None
        self.preferences = None
        self.options = None
        self.destination = None
        self.delivery_spec = None
        self.customs = None
        self.pin_number = ''
        self.notification = None
        self.language = 'en-CA' if language == False else language
        self.base_url = 'https://soa-gw.canadapost.ca/rs/' if prod_environment else 'https://ct.soa-gw.canadapost.ca/rs/'
        if request_type == "ncshipping":
            self.base_url = self.base_url + self.customer_number + '/ncshipment'
        if request_type == "shipping":
            self.base_url = self.base_url + self.customer_number + \
                '/' + self.customer_number + '/shipment'
        elif request_type == "rating":
            self.base_url = self.base_url + 'ship/price'
        elif request_type == "label":
            self.base_url = False
        elif request_type == "tracking":
            self.base_url = self.base_url.split(
                "/rs/")[0] + '/vis/track/pin/%s/detail' % self.pin_number

        # elif request_type == "services":
        #     self.base_url= self.base_url +'/service'
        #     self.set_headers()

    def get_authorization(self, username, password):
        message = username + ":" + password
        base64_bytes = base64.b64encode(message.encode('ascii'))
        base64_message = base64_bytes.decode('ascii')
        _logger.info(base64_bytes.decode('ascii'))
        return base64_message

    def web_authentication_detail(self, username, password):
        self.headers = {
            'Accept-language': self.language,
            'Authorization': 'Basic %s' % self.get_authorization(username, password),
        }
        if self.request_type == 'rating':
            self.headers['Accept'] = 'application/vnd.cpc.ship.rate-v4+xml'
            self.headers['Content-Type'] = 'application/vnd.cpc.ship.rate-v4+xml'
        if self.request_type == 'ncshipping':
            self.headers['Accept'] = 'application/vnd.cpc.ncshipment-v4+xml'
            self.headers['Content-Type'] = 'application/vnd.cpc.ncshipment-v4+xml'
        if self.request_type == 'shipping':
            self.headers['Accept'] = 'application/vnd.cpc.shipment-v8+xml'
            self.headers['Content-Type'] = 'application/vnd.cpc.shipment-v8+xml'
        if self.request_type == 'label':
            self.headers['Accept'] = 'application/pdf'
        if self.request_type == 'tracking':
            self.headers['Accept'] = 'application/vnd.cpc.track-v2+xml'

    def set_shipper(self, company_partner, warehouse_partner):
        if self.request_type == 'ncshipping' or self.request_type == 'shipping':
            self.sender = shipRequest.Sender(
                company_partner.name, company_partner.name if company_partner else None, company_partner.phone)
            sender = shipRequest.AddressDetails(company_partner)
            if self.request_type == 'shipping':
                sender.setCountry(company_partner)
            self.sender.setAddress(sender)
        if self.request_type == 'rating':
            self.originpc = warehouse_partner.zip.replace(
                " ", "") if warehouse_partner.zip else ''

    def set_recipient(self, recipient_partner):
        if self.request_type == 'ncshipping' or self.request_type == 'shipping':
            self.destination = shipRequest.Destination(
                recipient_partner.name, recipient_partner.name if recipient_partner else None, recipient_partner.phone)
            DestAdd = shipRequest.AddressDetails(recipient_partner)
            DestAdd.setCountry(recipient_partner)
            self.destination.setAddress(DestAdd)
            self.destination.setAddressInfo(
                additionalainfo=None, cvnumber=recipient_partner.phone)
        if self.request_type == 'rating':
            self.destpc = recipient_partner.zip.replace(
                " ", "") if recipient_partner.zip else ''

    def set_notification(self, recipient_partner, on_shipment, on_exception, on_delivery):
        self.notification = shipRequest.Notification(
            recipient_partner, on_shipment, on_exception, on_delivery)

    def set_packages(self, total_weight, package_count, packages, master_tracking_id=False):
        self.parcel_characteristics = shipRequest.ParcelCharacteristics()
        for pack in packages:
            self.parcel_characteristics.setWeight(pack.shipping_weight)
            self.parcel_characteristics.setDimension(shipRequest.Dimension(
                pack.packaging_id.packaging_length, pack.packaging_id.width, pack.packaging_id.height))

    def set_customs(self, picking, package):

        if self.request_type == 'ncshipping' or self.request_type == 'shipping':
            currency = picking.sale_id.partner_shipping_id.country_id.currency_id.name


            # convfromcad = picking.sale_id.amount_total
            amount_convert = picking.sale_id.currency_id.compute(
                picking.product_id.list_price, picking.sale_id.partner_shipping_id.country_id.currency_id)

            convfromcad = str(round(
                amount_convert/picking.sale_id.amount_total, 2)) if currency != 'CAD' else None
            reasonforexport = picking.sale_id.canadapost_export_reason
            otherreason = picking.sale_id.canadapost_other_reason
            items = []
            for quant in package.quant_ids:
                product = quant.product_id
                cuom = None
                coo = product.country_of_origin.code if product.country_of_origin else None
                poorigin = product.province_of_origin.code if product.province_of_origin else None
                sku = product.default_code[:15] if product.default_code else None
                unit_weight = 0
                cnou = str(int(quant.quantity)) if quant.product_uom_id.name == 'Units' else str(
                    quant.quantity)
                # Item(hscode, sku, cus_des, uweight, customs-value-per-unitl, customs-number-of-units, customs-unit-of-measure#optiona,country-of-origin, province-of-origin)
                item = shipRequest.Item(product.hs_code, product.default_code, product.name, str(
                    product.weight), str(product.list_price), cnou, cuom, coo, poorigin)
                items.append(item)


            sku_list = shipRequest.SkuList(items)
            dutiestaxesprepaid = None
            cert_number = picking.company_id.canadapost_certificate_number or None
            license_no = picking.company_id.canadapost_licence_number or None
            inv_no = picking.sale_id.name
            self.customs = shipRequest.Customs(
                currency, convfromcad, reasonforexport, otherreason, sku_list, dutiestaxesprepaid, cert_number, license_no, inv_no)

    def ship_delivery(self, service_code, sender, destination, parcel_characteristics):
        self.parcel_characteristics = shipRequest.ParcelCharacteristics()
        for pack in packages:
            self.parcel_characteristics.setWeight(pack.shipping_weight)
            self.parcel_characteristics.setDimension(shipRequest.Dimension(
                pack.packaging_id.packaging_length, pack.packaging_id.width, pack.packaging_id.height))

    # Packing Information
    # def set_master_package(self, total_weight, package_count, master_tracking_id=False):
    #     self.Shipment.PackageInformation.TotalWeight.Value = total_weight
    #     self.Shipment.PackageInformation.TotalPieces = package_count

    
    def add_package(self, weight_value, package_code=False, package_height=0, package_width=0, package_length=0, sequence_number=False, mode='shipping'):
        return self._add_package(weight_value=weight_value, package_code=package_code, package_height=package_height, package_width=package_width,
                                 package_length=package_length, sequence_number=sequence_number, mode=mode, po_number=False, dept_number=False)

    def _add_package(self, weight_value, package_code=False, package_height=0, package_width=0, package_length=0, sequence_number=False, mode='shipping', po_number=False, dept_number=False, reference=False):
        if not self.parcel_characteristics:
            self.parcel_characteristics = shipRequest.ParcelCharacteristics()
        self.parcel_characteristics.setWeight(str(weight_value))
        self.parcel_characteristics.setDimension(shipRequest.Dimension(
            str(package_length), str(package_width), str(package_height)))

    def set_preferences(self, spinstructions, sprate, sivalue):
        self.preferences = shipRequest.Preferences(
            spinstructions, sprate, sivalue)

    def rate(self, service_type, packages, weight, order_id, option_type, nhoption):

        formatted_response = {'price': {}, 'ShipmentEstimate': []}
        try:
            ShipDestination = shipRequest.ShipDestination()
            if order_id.partner_shipping_id.country_id.code == 'CA':
                domesctic = shipRequest.Domestic()
                domesctic.setPostalCode(self.destpc)
                ShipDestination.setDestination(domesctic)
            elif order_id.partner_shipping_id.country_id.code == 'US':
                unitedstates = shipRequest.UnitedStates()
                unitedstates.setZipCode(str(order_id.partner_shipping_id.zip))
                ShipDestination.setDestination(unitedstates)
            else:
                international = shipRequest.International(
                    str(order_id.partner_shipping_id.country_id.code))
                if order_id.partner_shipping_id.zip:
                    international.setPostalCode(
                        str(order_id.partner_shipping_id.zip))
                ShipDestination.setDestination(international)
            service_req = shipRequest.CanpostGetRates()
            service_req.setCustNum(self.customer_number)
            service_req.setParcel(self.parcel_characteristics)
            service_req.setOriginPC(self.originpc)
            service_req.setDestination(ShipDestination)
            # -----------------------------------------------------------
            options = []
            if option_type or nhoption:
                self.options = shipRequest.Options()
                for opt in option_type:
                    option_amount = str(order_id.amount_total) if opt.code == 'COV'else None
                    option = shipRequest.Option(opt.name, option_amount)
                    options.append(option)
                if nhoption:
                    option = shipRequest.Option(nhoption, None)
                    options.append(option)
            if len(options) > 0:        
                self.options.set_option(options)
                service_req.setOptions(self.options)
            # -----------------------------------------------------------
            req = shipRequest.canHttpsPost(
                self.base_url, self.headers, service_req, self.request_type)
            req.postRequest()
            self.response = req.getResponse()

            if self.response.get('status_code') == 200:
                if self.response.get('error') == False:
                    if len(self.response.get('response').get('price-quotes', {}).get('price-quote', [])) == 0:
                        raise Exception("No rating found")
                    ShipmentEstimate = self.response.get('response').get(
                        'price-quotes', {}).get('price-quote', [])
                    if len(ShipmentEstimate) > 1:
                        for rating in ShipmentEstimate:
                            if rating.get('service-name') == service_type.name:
                                formatted_response['price']['TotalPrice'] = float(
                                    rating.get('price-details', {}).get('due', None))
                    if len(ShipmentEstimate) == 1:
                        formatted_response['price']['TotalPrice'] = float(
                            ShipmentEstimate[0]['due'])
                    formatted_response['ShipmentEstimate'] = ShipmentEstimate

                else:
                    errors_message = xmltodict.parse(
                        self.response.get('response'))
                    messages = ''
                    if type(errors_message.get('messages')) == collections.OrderedDict:
                        messages = errors_message.get('messages').get(
                            'message').get('description')
                    else:
                        for msg in errors_message.get('messages'):
                            messages += msg.get('message').get('description')
                    formatted_response['errors_message'] = messages
            else:
                errors_message = xmltodict.parse(self.response.get('response'))
                messages = ''
                if type(errors_message.get('messages')) == collections.OrderedDict:
                    messages = errors_message.get('messages').get(
                        'message').get('description')
                else:
                    for msg in errors_message.get('messages'):
                        messages += msg.get('description')
                formatted_response['errors_message'] = messages

        except IOError:
            formatted_response['errors_message'] = "canadapost Server Not Found"
        except Exception as e:
            formatted_response['errors_message'] = e.args[0]
        _logger.info("\nformatted_response")
        _logger.info("\n" + str(formatted_response))
        return formatted_response

    def process_shipment(self, picking, option_type, nhoption, package_name):
        order = picking.sale_id
        formatted_response = {'tracking_number': 0.0,
                              'price': {},
                              'master_tracking_id': None,
                              'date': None,
                              'links': []}

        try:
            self.service_code = order.canadapost_service or order.carrier_id.canadapost_service_code.code
            rs_point = order.company_id.zip.replace(
                " ", "") if order.company_id.zip else ""
            self.delivery_spec = shipRequest.DeliverySpec(
                self.service_code, self.sender, self.destination, self.parcel_characteristics, self.preferences)
            sprate = True if order.partner_shipping_id.country_id.code != 'CA' else False
            sivalue = True if order.partner_shipping_id.country_id.code != 'CA' else False
            if option_type or nhoption:
                self.options = shipRequest.Options()
                for opt in option_type:
                    self.options.set_option(shipRequest.Option(opt.name))
                if nhoption:
                    self.options.set_option(shipRequest.Option(nhoption))
                if self.options:
                    self.delivery_spec.setOptions(self.options)

            if self.customs != None:
                self.delivery_spec.setCustoms(self.customs)

            if self.request_type == 'ncshipping':
                if len(picking.carrier_id.canadapost_option_type) > 0:
                    if picking.sale_id.partner_shipping_id.country_id.code not in ['CA', 'US']:
                        if 'D2PO' in picking.carrier_id.canadapost_option_type.mapped("code"):
                            self.delivery_spec.setNotification(shipRequest.Notification(
                                order.shiiping_partner_id.email, True, True, True))

                ship = shipRequest.NCShipping(rs_point, self.delivery_spec)

            if self.request_type == 'shipping':
                settlement = {}
                if picking.carrier_id.canadapost_contract_id and picking.carrier_id.canadapost_payment_method.name == 'Account':
                    settlement = {
                        'contract-id': picking.carrier_id.canadapost_contract_id,
                        'intended-method-of-payment': picking.carrier_id.canadapost_payment_method.name}

                self.delivery_spec.setSettlement(
                    settlement_info=shipRequest.SettlementInfo(settlement))
                values = {}
                values['customer-request-id'] = package_name  # str(picking.id)
                # values['group-id'] = str(picking.id)#NA
                values['transmit-shipment'] = "true"  # or "false"
                # values['quickship-label-requested'] = "true"#or  "false"
                if picking.carrier_id.canadapost_pickup_indicator == 'pickup':
                    values['cpc-pickup-indicator'] = "true"
                    zip_pt = picking.sale_id.partner_shipping_id.zip or None
                    # (6-character alphanumeric string)
                    values['requested-shipping-point'] = zip_pt.replace(
                        " ", "") or None
                if picking.carrier_id.canadapost_pickup_indicator == 'deposit':
                    # values['cpc-pickup-indicator'] =  "false"
                    # (4-character alphanumeric string)
                    values['shipping-point-id'] = picking.canadapost_shipping_pointid
                # (YYYY-MM-DD - date format)
                values['expected-mailing-date'] = picking.scheduled_date.strftime(
                    "%Y-%m-%d")
                values['provide-pricing-info'] = "true"
                values['provide-receipt-info'] = "true"
                values['delivery-spec'] = self.delivery_spec
                ship = shipRequest.Shipment(values)

            ship_req = shipRequest.canHttpsPost(
                self.base_url, self.headers, ship, self.request_type)
            ship_req.postRequest()
            self.response = ship_req.getResponse()


            if self.response.get('status_code') == 200:
                if picking.carrier_id.canadapost_customer_type == 'counter':
                    if self.response.get('error') == False:
                        formatted_response['master_tracking_id'] = self.response.get(
                            'response', {}).get('non-contract-shipment-info', {}).get('tracking-pin')
                        formatted_response['tracking_number'] = self.response.get(
                            'response', {}).get('non-contract-shipment-info', {}).get('tracking-pin')
                        links = self.response.get('response', {}).get(
                            'non-contract-shipment-info', {}).get('links', {}).get('link')
                        label_urls = list(filter(None, [link.get(
                            '@href') if link.get('@rel') == 'label' else False for link in links]))
                        formatted_response['links'] = links
                    else:
                        errors_message = xmltodict.parse(
                            self.response.get('response'))
                        messages = ''
                        if type(errors_message.get('messages')) == collections.OrderedDict:
                            messages = errors_message.get('messages').get(
                                'message').get('description')
                        else:
                            for msg in errors_message.get('messages'):
                                messages += msg.get('message').get('description')
                        formatted_response['errors_message'] = messages
                else:
                    if self.response.get('error') == False:
                        formatted_response['master_tracking_id'] = self.response.get(
                            'response', {}).get('shipment-info', {}).get('tracking-pin')
                        formatted_response['tracking_number'] = self.response.get(
                            'response', {}).get('shipment-info', {}).get('tracking-pin')
                        links = self.response.get('response', {}).get(
                            'shipment-info', {}).get('links', {}).get('link')
                        label_urls = list(filter(None, [link.get(
                            '@href') if link.get('@rel') == 'label' else False for link in links]))
                        formatted_response['links'] = links
                    else:
                        errors_message = xmltodict.parse(
                            self.response.get('response'))
                        messages = ''
                        if type(errors_message.get('messages')) == collections.OrderedDict:
                            messages = errors_message.get('messages').get(
                                'message').get('description')
                        else:
                            for msg in errors_message.get('messages'):
                                messages += msg.get('message').get('description')
                        formatted_response['errors_message'] = messages
            else:
                errors_message = xmltodict.parse(self.response.get('response'))
                messages = ''
                if type(errors_message.get('messages')) == collections.OrderedDict:
                    if type(errors_message.get('messages').get('message')) == list:
                        for message in errors_message.get('messages').get('message'):
                            messages += '\n Code: ' + \
                                message.get('code') + ', Message: ' + \
                                message.get('description')
                    else:
                        messages = errors_message.get('messages').get(
                            'message').get('description')
                else:
                    for msg in errors_message.get('messages').get('message'):
                        messages += msg.get('description')
                formatted_response['errors_message'] = messages

        except Exception as e:
            formatted_response['errors_message'] = e.args
        except IOError:
            formatted_response['errors_message'] = "CanadaPost Server Not Found"
        except Exception as e:
            formatted_response['errors_message'] = e.args[0]

        return formatted_response

    def get_label_url(self, TrackingPIN, URL, FileFormat):
        pdf_data = requests.get(URL, headers=self.headers)
        return {'pdf_data': pdf_data.content, 'status_code': pdf_data.status_code}

    # def get_services(self, country_code=None, contract_id=None, origpc=None, destpc=None):
    #     formatted_response = {'price': {},'services':[]}
    #     try:
    #         query = '?'
    #         query += 'country='+country_code if country_code else ''
    #         query += '&contract='+contract_id if contract_id else ''
    #         query += '&origpc='+origpc if origpc else ''
    #         query += '&destpc='+destpc if destpc else ''

    #         res = requests.get(self.base_url, headers=self.headers)
    #         self.response = xmltodict.parse(res.text)
    #         print(self.response)

    #         if res.status_code == 200:
    #             if isinstance(self.response, collections.OrderedDict):
    #                 if len(self.response.get('services',{}).get('service',[])) == 0:
    #                     raise Exception("No services found")
    #                 for service in self.response.get('services',{}).get('service',[]):
    #                     print(service.get('service-code'))
    #                     print(service.get('service-name'))
    #                 ServiceOptions = self.response.get('services',{}).get('service',[])
    #                 if len(ServiceOptions) > 1:
    #                     formatted_response['services'] = ServiceOptions
    #         else:
    #             errors_message = '%s' %res.status_code
    #             formatted_response['errors_message'] = errors_message
    #     except Exception as e:
    #         formatted_response['errors_message'] = e.args[0]
    #     return formatted_response
