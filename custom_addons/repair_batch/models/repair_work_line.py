from odoo import models, fields, api


class RepairWorkLine(models.Model):
    _name = "repair.work.line"
    _description = "Repair Work Line"

    trolley_id = fields.Many2one("repair.trolley")
    sale_line_id = fields.Many2one("sale.order.line", copy=False, readonly=True)

    product_id = fields.Many2one("product.product", required=True)
    quantity = fields.Float(default=1)

    is_done = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for trolley in lines.mapped("trolley_id"):
            work_lines = trolley.work_line_ids
            all_done = bool(work_lines) and all(work_lines.mapped("is_done"))
            if trolley.is_done != all_done:
                trolley.with_context(skip_trolley_line_sync=True).write(
                    {"is_done": all_done}
                )
        return lines

    def unlink(self):
        trolleys = self.mapped("trolley_id")
        res = super().unlink()
        for trolley in trolleys:
            work_lines = trolley.work_line_ids
            all_done = bool(work_lines) and all(work_lines.mapped("is_done"))
            if trolley.is_done != all_done:
                trolley.with_context(skip_trolley_line_sync=True).write(
                    {"is_done": all_done}
                )
        return res

    def write(self, vals):
        trolleys = self.mapped("trolley_id")
        res = super().write(vals)

        if "is_done" in vals and not self.env.context.get("skip_line_trolley_sync"):
            for trolley in trolleys:
                lines = trolley.work_line_ids
                all_done = bool(lines) and all(lines.mapped("is_done"))
                if trolley.is_done != all_done:
                    trolley.with_context(skip_trolley_line_sync=True).write(
                        {"is_done": all_done}
                    )

        return res

