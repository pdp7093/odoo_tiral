from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_repair_order = fields.Boolean("Is Repair Order")

    repair_batch_ids = fields.One2many(
        "repair.batch", "sale_id", string="Repair Batches"
    )

    repair_count = fields.Integer(compute="_compute_repair_count")

    def _compute_repair_count(self):
        for rec in self:
            rec.repair_count = self.env['repair.batch'].search_count([
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

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            if not order.is_repair_order:
                continue

            # 🔥 create repair batch
            existing = self.env["repair.batch"].search(
                [("sale_id", "=", order.id)], limit=1
            )

            if not existing:
                self.env["repair.batch"].create({
                    "name": order.name,
                    "partner_id": order.partner_id.id,
                    "sale_id": order.id,
                })

        return res
    
