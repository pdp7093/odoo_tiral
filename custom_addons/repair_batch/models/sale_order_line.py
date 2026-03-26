from odoo import models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        # ❌ Isse moves ki execution rukti hai
        if self.order_id.is_repair_order:
            return True
        return super()._action_launch_stock_rule(previous_product_uom_qty)

    def _prepare_procurement_values(self, group_id=False):
        # ❌ Isse move creation ki planning (MTO/Rules) rukti hai
        if self.order_id.is_repair_order:
            return {}
        return super()._prepare_procurement_values(group_id=group_id)