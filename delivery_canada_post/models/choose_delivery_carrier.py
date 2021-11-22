# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, models, fields, _

class Providercanadapost(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    canadapost_shipping_date =  fields.Date(string='Shipping Date', default=fields.Date.today()) 
    canadapost_service = fields.Char(string="canadapost Service")
    canadapost_service_type = fields.Many2one(comodel_name="canadapost.service", string="Select Service Type")
      
    @api.onchange("canadapost_service_type")
    def onchange_canadapost_service_type(self):
        self.delivery_price = self.canadapost_service_type.total_price
        self.display_price = self.canadapost_service_type.total_price
        self.order_id.canadapost_service = self.canadapost_service_type.service_code

    @api.onchange("carrier_id")
    def onchange_carrier_id(self):
        sers = self.env['canadapost.service'].sudo().search([])
        for ser in sers:
            ser.sudo().write({'active':False})

# class ChooseDeliveryPackage(models.TransientModel):
#     _inherit = 'choose.delivery.package'

#     @api.onchange("shipping_weight")
#     def onchange_shipping_weight(self):
#         print(self.picking_id.package_ids)
#         print(self.picking_id.sale_id)
#         import pdb;pdb.set_trace();
        

class MySelectionModel(models.TransientModel):
    _name = "canadapost.service"
    _description = "Canada Post Services"

    service_name = fields.Char(string="Service Name")
    service_code = fields.Char(string="Service Code")
    service_link = fields.Char()
    shipment_date =  fields.Date(string='Shipment Date')  
    expected_delivery_date =  fields.Date(string='Expected Delivery Date')
    expected_transit_days =  fields.Integer(string='EstimatedTransitDays')
    surcharges = fields.Float(string="Surcharges")   
    taxes = fields.Float(string="Taxes") 
    options = fields.Float(string="Optional") 
    base_price = fields.Float(string="Base Price")  
    total_price = fields.Float(string="Display Price")   
    order_id = fields.Many2one('sale.order')
    choise_id = fields.Many2one('choose.delivery.carrier')
    active = fields.Boolean(string='Status', default=True)

    def name_get(self):
        res = []
        for record in self:
            name = record.service_name + ', Shipping Cost: ' + str(record.total_price) + ', Expected Delivery Date: ' + str(record.expected_delivery_date)
            res.append((record.id,  name))    
        return res
