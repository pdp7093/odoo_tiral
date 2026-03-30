from odoo import models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        repair_lines = self.filtered(lambda line: line.order_id.is_repair_order)
        normal_lines = self - repair_lines

        if not normal_lines:
            return True

        return super(SaleOrderLine, normal_lines)._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )

    def _prepare_procurement_values(self):
        self.ensure_one()
        if self.order_id.is_repair_order:
            return {}
        return super()._prepare_procurement_values()

    def _create_repair_order(self):
        normal_lines = self.filtered(lambda line: not line.order_id.is_repair_order)
        if not normal_lines:
            return True
        return super(SaleOrderLine, normal_lines)._create_repair_order()

    def _cancel_repair_order(self):
        normal_lines = self.filtered(lambda line: not line.order_id.is_repair_order)
        if not normal_lines:
            return True
        return super(SaleOrderLine, normal_lines)._cancel_repair_order()
