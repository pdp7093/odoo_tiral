from odoo import models, fields, api


class RepairTrolley(models.Model):
    _name = "repair.trolley"
    _description = "Repair Trolley"

    name = fields.Char()
    batch_id = fields.Many2one("repair.batch")

    work_line_ids = fields.One2many(
        "repair.work.line", "trolley_id"
    )

    is_done = fields.Boolean()
    employee_id = fields.Many2one("hr.employee", string="Assigned To")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
        ],
        compute="_compute_state",
        store=True,
    )

    def write(self, vals):
        res = super().write(vals)

        if "is_done" in vals and not self.env.context.get("skip_trolley_line_sync"):
            for rec in self:
                rec.work_line_ids.with_context(skip_line_trolley_sync=True).write(
                    {"is_done": rec.is_done}
                )

        return res

    @api.depends("work_line_ids.is_done")
    def _compute_state(self):
        for rec in self:
            if not rec.work_line_ids:
                rec.state = "pending"
            elif all(l.is_done for l in rec.work_line_ids):
                rec.state = "done"
            else:
                rec.state = "in_progress"

    def open_trolley(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.trolley",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
