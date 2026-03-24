from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = "sale.order"
    repair_batch_ids = fields.One2many(
        "repair.batch", "sale_id", string="Repair Batches"
    )
    is_repair_order = fields.Boolean(string="Repair Order", default=False)

    def action_open_repair_batches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Repair Batches",
            "res_model": "repair.batch",
            "view_mode": "list,form",
            "domain": [("sale_id", "=", self.id)],
            "context": {"default_sale_id": self.id},
        }

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            # 🔥 CHECK if already exists
            existing = self.env["repair.batch"].search([("sale_id", "=", order.id)])
            if existing:
                continue  # ❌ duplicate avoid

            current_trolley = None
            repair = self.env["repair.batch"].create(
                {
                    "partner_id": order.partner_id.id,
                    "sale_id": order.id,
                    "name": order.name,
                }
            )

            for line in order.order_line:
                if line.display_type == "line_section":
                    current_trolley = self.env["repair.trolley"].create(
                        {
                            "name": line.name,
                            "batch_id": repair.id,
                        }
                    )
                else:
                    if current_trolley:
                        self.env["repair.work.line"].create(
                            {
                                "trolley_id": current_trolley.id,
                                "name": line.name,
                            }
                        )

            order.is_repair_order = True

        return res
