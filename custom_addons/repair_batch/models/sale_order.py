from odoo import fields, models
from odoo.addons.sale.models.sale_order import SaleOrder as BaseSaleOrder


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_repair_order = fields.Boolean("Is Repair Order")

    repair_batch_ids = fields.One2many(
        "repair.batch", "sale_id", string="Repair Batches"
    )

    repair_batch_count = fields.Integer(compute="_compute_repair_batch_count")

    def _compute_repair_batch_count(self):
        for rec in self:
            rec.repair_batch_count = self.env['repair.batch'].search_count([
                ('sale_id', '=', rec.id)
            ])

    def action_open_repair_batches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Repair Batches",
            "res_model": "repair.batch",
            "view_mode": "list,form",
            "domain": [("sale_id", "=", self.id)],
        }

    def _create_repair_batches(self):
        for order in self.filtered("is_repair_order"):
            existing = self.env["repair.batch"].search(
                [("sale_id", "=", order.id)], limit=1
            )
            if existing:
                continue

            self.env["repair.batch"].create(
                {
                    "name": order.name,
                    "partner_id": order.partner_id.id,
                    "sale_id": order.id,
                }
            )

    def _action_confirm(self):
        repair_orders = self.filtered("is_repair_order")
        normal_orders = self - repair_orders

        if repair_orders:
            BaseSaleOrder._action_confirm(repair_orders)
            repair_orders._create_repair_batches()

        if normal_orders:
            super(SaleOrder, normal_orders)._action_confirm()

        return True
