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

    consumption_picking_id = fields.Many2one(
        "stock.picking",
        string="Repair Consumption Picking",
        readonly=True,
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

    def _collect_work_lines(self, batch):
        """Return repair work lines to consume for this batch."""
        moves = self.env['stock.move']
        for trolley in batch.trolley_ids:
            done_lines = trolley.work_line_ids.filtered(lambda l: l.is_done)
            work_lines = done_lines if done_lines else trolley.work_line_ids
            for line in work_lines:
                if not line.product_id and line.name:
                    product = self.env['product.product'].search([('name', 'ilike', line.name)], limit=1)
                    if product:
                        line.product_id = product
                if not line.product_id and batch.sale_id and batch.sale_id.order_line:
                    line.product_id = batch.sale_id.order_line[0].product_id
                if not line.product_id or line.quantity <= 0:
                    continue
                move = self.env['stock.move'].create({
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': batch.source_location_id.id,
                    'location_dest_id': batch.consumption_location_id.id,
                    # picking_id set later once picking exists
                })
                moves |= move
        return moves

    def _create_repair_picking(self, batch):
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise ValidationError("Internal picking type not configured.")
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': batch.source_location_id.id,
            'location_dest_id': batch.consumption_location_id.id,
            'origin': batch.name,
        })
        return picking

    def action_start_repair(self):
        for batch in self:
            if not batch.received:
                raise ValidationError("Trolley not received yet!")

            # 🔥 USE SALE PICKING ONLY
            picking = batch.sale_id.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')
            )

            if not picking:
                raise ValidationError("No delivery picking found for this sale order.")

            picking = picking[0]

            # Reserve stock
            picking.action_assign()

            batch.consumption_picking_id = picking
            batch.state = 'in_progress'

    # 🔥 FINAL FIXED METHOD
    def action_done(self):
        for batch in self:
            batch.ensure_one()

            if not batch.trolley_ids:
                raise ValidationError("No trolley found for this batch.")

            if any(trolley.state != 'done' for trolley in batch.trolley_ids):
                raise ValidationError("All trolleys must be done before closing the batch.")

            picking = batch.consumption_picking_id

            if not picking:
                raise ValidationError("No picking found. Start repair first.")

            # Assign (reserve)
            picking.action_assign()

            # 🔥 MOST IMPORTANT LINE (YOU WERE MISSING THIS)
            for move_line in picking.move_line_ids:
                if move_line.quantity > 0:
                    move_line.qty_done = move_line.quantity

            # Optional UI
            picking.move_line_ids.write({'picked': True})

            # 🔥 FINAL STEP
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
    product_id = fields.Many2one("product.product", string="Product", required=True)
    quantity = fields.Float(default=1, required=True)
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

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if not res.get("product_id") and res.get("trolley_id"):
            trolley = self.env["repair.trolley"].browse(res["trolley_id"])
            sale = trolley.batch_id.sale_id
            if sale and sale.order_line:
                res["product_id"] = sale.order_line[0].product_id.id
        return res

    @api.onchange("name")
    def _onchange_name(self):
        if self.name and not self.product_id:
            product = self.env["product.product"].search([("name", "ilike", self.name)], limit=1)
            if product:
                self.product_id = product

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("product_id") and vals.get("name"):
                product = self.env["product.product"].search([("name", "ilike", vals.get("name"))], limit=1)
                if product:
                    vals["product_id"] = product.id
        return super().create(vals_list)

    def write(self, vals):
        if not vals.get("product_id") and vals.get("name"):
            product = self.env["product.product"].search([("name", "ilike", vals.get("name"))], limit=1)
            if product:
                vals["product_id"] = product.id
        return super().write(vals)

    @api.constrains("product_id")
    def _check_product(self):
        for rec in self:
            if not rec.product_id:
                raise ValidationError("Please select a product for each work line.")

    @api.depends("is_done")
    def _compute_state(self):
        for rec in self:
            rec.state = "done" if rec.is_done else "pending"
    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError("Quantity must be greater than 0!")