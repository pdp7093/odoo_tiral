from odoo import models 


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            current_trolley = None 
        
            repair = self.env['repair.batch'].create({
                'partner_id':order.partner_id.id,
                'sale_order_id':order.id,
                'name':order.name
            })

            for line in order.order_line:
                if line.display_type == 'line_section':
                    current_trolley = self.env['repair.trolley'].create({
                        'name':line.name,
                        'batch_id':repair.id,
                    })

                else:
                    if current_trolley:
                        self.env['repair.work.line'].create({
                            'trolley_id':current_trolley.id,
                            'name':line.name,
                        })
            
        return res