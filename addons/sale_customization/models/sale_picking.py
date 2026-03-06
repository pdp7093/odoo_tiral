from odoo import models 

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()

        for picking in self:
            if picking.sale_id and picking.state == 'done':
                picking.sale_id.message_post(
                    body=f"Delivery {picking.name} completed."
                )
                sale_order = picking.sale_id

                if sale_order.invoice_status == "to invoice":
                    invoice = sale_order._create_invoices()
                    invoice.action_post()
        
        return res 