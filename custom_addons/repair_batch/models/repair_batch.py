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

    source_location_id = fields.Many2one(
        "stock.location",
        default=lambda self: self.env.ref("stock.stock_location_stock"),
    )

    consumption_location_id = fields.Many2one(
        "stock.location",
        default=lambda self: self.env["stock.location"].search(
            [("name", "=", "Repair Consumption")], limit=1
        ),
    )

    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("sale_id") and self.env.context.get("default_sale_id"):
                vals["sale_id"] = self.env.context.get("default_sale_id")

        return super().create(vals_list)

    _sql_constraints = [("unique_sale", "unique(sale_id)", "Repair already exists!")]

    # ---------------- BUTTONS ---------------- #

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
                raise ValidationError("Trolley not received yet!")
            rec.state = "in_progress"

    
    # 🔥 FINAL FIXED METHOD
    def action_done(self):
        for batch in self:

            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': batch.source_location_id.id,
                'location_dest_id': batch.consumption_location_id.id,
                'origin': batch.name,
            })

            moves = self.env['stock.move']

            for trolley in batch.trolley_ids:
                for line in trolley.work_line_ids:

                    if not line.product_id or line.quantity <= 0:
                        continue

                    move = self.env['stock.move'].create({
                        'name': line.product_id.display_name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': line.product_id.uom_id.id,
                        'location_id': batch.source_location_id.id,
                        'location_dest_id': batch.consumption_location_id.id,
                        'picking_id': picking.id,
                    })

                    moves |= move

            if not moves:
                raise ValidationError("No valid products to consume!")

            # 🔥 IMPORTANT FLOW
            moves._action_confirm()
            moves._action_assign()

            # 🔥 SET qty_done
            for move in moves:
                move.quantity_done = move.product_uom_qty 

            # 🔥 FINAL
            picking._action_done()

            batch.state = 'done'

# ---------------- TROLLEY ---------------- #

class RepairTrolley(models.Model):
    _name = "repair.trolley"
    _description = "Repair Trolley"

    name = fields.Char(string="Trolley Name")
    batch_id = fields.Many2one("repair.batch")

    work_line_ids = fields.One2many(
        "repair.work.line", "trolley_id", string="Work Lines"
    )

    is_done = fields.Boolean(string="Done")

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
                rec.work_line_ids.write({"is_done": rec.is_done})

        return res

    @api.depends("work_line_ids.is_done")
    def _compute_state(self):
        for rec in self:
            if not rec.work_line_ids:
                rec.state = "pending"
            elif all(line.is_done for line in rec.work_line_ids):
                rec.state = "done"
            else:
                rec.state = "in_progress"


# ---------------- WORK LINE ---------------- #

class RepairWorkLine(models.Model):
    _name = "repair.work.line"
    _description = "Repair Work Line"

    trolley_id = fields.Many2one("repair.trolley")
    product_id = fields.Many2one("product.product",string="Product",required=True)
    quantity = fields.Float(default=1,required=True)
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
    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError("Quantity must be greater than 0!")