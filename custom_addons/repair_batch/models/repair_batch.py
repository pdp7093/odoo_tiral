from odoo import models, fields
from odoo.exceptions import ValidationError


class RepairBatch(models.Model):
    _name = "repair.batch"
    _description = "Repair Batch"

    name = fields.Char()
    partner_id = fields.Many2one("res.partner")

    sale_id = fields.Many2one("sale.order")

    state = fields.Selection(
        [
            ("draft", "Waiting"),
            ("ready", "Ready"),
            ("in_progress", "In Repair"),
            ("done", "Done"),
        ],
        default="draft",
    )

    received = fields.Boolean(default=False)

    trolley_ids = fields.One2many("repair.trolley", "batch_id")

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

    consumption_picking_id = fields.Many2one("stock.picking")

    def _auto_create_trolley(self):
        for batch in self:
            if batch.trolley_ids:
                continue

            self.env["repair.trolley"].create(
                {
                    "name": "Trolley 1",
                    "batch_id": batch.id,
                }
            )

    def _auto_create_work_lines(self):
        for batch in self:
            if not batch.sale_id:
                continue

            # Use the first trolley as the default auto-generated work container.
            trolley = batch.trolley_ids.sorted("id")[:1]
            if not trolley:
                continue
            trolley = trolley[0]

            sale_lines = batch.sale_id.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            )

            existing_lines = self.env["repair.work.line"].search(
                [
                    ("trolley_id.batch_id", "=", batch.id),
                    ("sale_line_id", "in", sale_lines.ids),
                ]
            )
            existing_by_sale_line_id = set(existing_lines.mapped("sale_line_id").ids)

            to_create = []
            for line in sale_lines:
                if line.id in existing_by_sale_line_id:
                    continue
                to_create.append(
                    {
                        "trolley_id": trolley.id,
                        "sale_line_id": line.id,
                        "product_id": line.product_id.id,
                        "quantity": line.product_uom_qty,
                    }
                )

            if to_create:
                self.env["repair.work.line"].create(to_create)

    # ---------------- BUTTONS ---------------- #

    def action_receive(self):
        for rec in self:
            rec.received = True
            rec.state = "ready"

    def action_start_repair(self):
        for rec in self:
            if not rec.received:
                raise ValidationError("Receive first")

            if rec.trolley_ids:
                rec.state = "in_progress"
                continue

            current_trolley = False

            for line in rec.sale_id.order_line:

                # 🔹 SECTION → CREATE TROLLEY
                if line.display_type == 'line_section':
                    current_trolley = self.env['repair.trolley'].create({
                        'name': line.name,
                        'batch_id': rec.id,
                    })

                # 🔹 PRODUCT → CREATE WORK LINE
                elif not line.display_type:
                    if not current_trolley:
                        # fallback (no section case)
                        current_trolley = self.env['repair.trolley'].create({
                            'name': 'General',
                            'batch_id': rec.id,
                        })

                    self.env['repair.work.line'].create({
                        'trolley_id': current_trolley.id,
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                    })

            rec.state = "in_progress"

    def action_open_sale_order(self):
        self.ensure_one()

        if not self.sale_id:
            raise ValidationError("No Sale Order linked.")

        return {
            "type": "ir.actions.act_window",
            "name": "Quotation",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_id.id,
        }

    def action_done(self):
        for batch in self:
            if any(t.state != "done" for t in batch.trolley_ids):
                raise ValidationError("Complete all trolleys")

            # 🔥 INTERNAL PICKING TYPE
            picking_type = self.env["stock.picking.type"].search(
                [("code", "=", "internal")], limit=1
            )

            # 🔥 NEW PICKING (CONSUMPTION)
            picking = self.env["stock.picking"].create({
                "picking_type_id": picking_type.id,
                "location_id": batch.source_location_id.id,
                "location_dest_id": batch.consumption_location_id.id,
                "origin": batch.name,
            })

            moves = self.env["stock.move"]

            for trolley in batch.trolley_ids:
                for line in trolley.work_line_ids:
                    if not line.product_id or line.quantity <= 0:
                        continue

                    move = self.env["stock.move"].create({
                        "product_id": line.product_id.id,
                        "product_uom_qty": line.quantity,
                        "product_uom": line.product_id.uom_id.id,
                        "location_id": batch.source_location_id.id,
                        "location_dest_id": batch.consumption_location_id.id,
                        "picking_id": picking.id,
                    })
                    moves |= move

            # 🔥 STANDARD FLOW
            moves._action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                for ml in move.move_line_ids:
                    # In Odoo 17+, use 'quantity' instead of 'qty_done'
                    ml.quantity = move.product_uom_qty
                    ml.picked = True # Required in v17+ to validate successfully

            picking.button_validate()

            # 🔥 UPDATE SALE ORDER PROGRESS
            # Since we blocked the standard delivery picking, we must manually 
            # set qty_delivered so the Sale Order shows as 'Fully Delivered'.
            for trolley in batch.trolley_ids:
                for line in trolley.work_line_ids:
                    if line.sale_line_id:
                        line.sale_line_id.qty_delivered = line.quantity

            batch.consumption_picking_id = picking
            batch.state = "done"

