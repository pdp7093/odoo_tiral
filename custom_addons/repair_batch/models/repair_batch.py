from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RepairBatch(models.Model):
    _name = "repair.batch"
    _description = "Repair Batch"

    name = fields.Char(string="Reference")
    partner_id = fields.Many2one("res.partner", string="Customer")

    sale_id = fields.Many2one("sale.order", string="Sale Order")
    state = fields.Selection(
        [
            ("draft", "Waiting for Material"),
            ("ready", "Ready for Repair"),
            ("in_progress", "In Repair"),
            ("done", "Done"),
        ],
        default="draft",
    )

    received = fields.Boolean(default=False)
    product_id = fields.Many2one("product.product", string="Product")
    quantity = fields.Float(default=1)
    trolley_ids = fields.One2many("repair.trolley", "batch_id", string="Trolleys")

    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sale_id") and self.env.context.get("default_sale_id"):
                vals["sale_id"] = self.env.context.get("default_sale_id")

        print("🔥 CREATE CALLED:", vals_list)
        # return super().create(vals_list)

        return super().create(vals_list)

    _sql_constraints = [("unique_sale", "unique(sale_id)", "Repair already exists!")]

    # Buttons
    def action_receive(self):
        for rec in self:
            rec.received = True
            rec.state = "ready"

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Quotation",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_id.id,
            "target": "current",
        }

    def action_start_repair(self):
        for rec in self:
            if not rec.received:
                raise Exception("Trolley not received yet!")
            rec.state = "in_progress"

    def action_done(self):
        for rec in self:
            for trolley in rec.trolley_ids:
                for line in trolley.work_line_ids:

                    product = line.product_id
                    qty = line.quantity or 1  # 🔥 fallback

                    if not product:
                        continue

                    # 🔥 stock check
                    if product.qty_available < qty:
                        raise ValidationError(f"Not enough stock for {product.name}")

                    # 🔥 get location (simple version)
                    location = self.env.ref("stock.stock_location_stock")

                    # 🔥 reduce stock
                    self.env["stock.quant"]._update_available_quantity(
                        product, location, -qty
                    )

            rec.state = "done"


# NEW MODEL (Trolley)
class RepairTrolley(models.Model):
    _name = "repair.trolley"
    _description = "Repair Trolley"

    name = fields.Char(string="Trolley Name")
    batch_id = fields.Many2one("repair.batch")

    work_line_ids = fields.One2many(
        "repair.work.line", "trolley_id", string="Work Lines"
    )
    is_done = fields.Boolean(string="Done")
    # sale_id = fields.Many2one("sale.order", string="Sale Order")
    state = fields.Selection(
        [("pending", "Pending"), ("in_progress", "In Progress"), ("done", "Done")],
        compute="_compute_state",
        store=True,
    )

    employee_id = fields.Many2one("hr.employee", string="Assigned To")

    @api.constrains("employee_id")
    def _check_employee(self):
        for rec in self:
            if not rec.employee_id:
                raise ValidationError("Assign employee to trolley.")

    def open_trolley(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.trolley",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def write(self, vals):
        res = super().write(vals)

        if "is_done" in vals:
            for rec in self:
                if rec.is_done:
                    rec.work_line_ids.write({"is_done": True})
                else:
                    rec.work_line_ids.write({"is_done": False})

        return res

    # ✅ CLEAN COMPUTE (single source of truth)
    @api.depends("work_line_ids.is_done")
    def _compute_state(self):
        for rec in self:
            if not rec.work_line_ids:
                rec.state = "pending"
            elif all(line.is_done for line in rec.work_line_ids):
                rec.state = "done"
            else:
                rec.state = "in_progress"


#  NEW MODEL (Work Lines)
class RepairWorkLine(models.Model):
    _name = "repair.work.line"
    _description = "Repair Work Line"

    trolley_id = fields.Many2one("repair.trolley")
    product_id = fields.Many2one("product.product", string="Product")  # ✅ ADD
    quantity = fields.Float(default=1)
    name = fields.Char(string="Work")

    is_done = fields.Boolean(string="Done")

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
        ],
        compute="_compute_state",
        store=True,
    )

    @api.depends("is_done")
    def _compute_state(self):
        for rec in self:
            rec.state = "done" if rec.is_done else "pending"
