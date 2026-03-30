from odoo import models, fields,api
from odoo.exceptions import ValidationError


class RepairBatch(models.Model):
    _name = "repair.batch"
    _description = "Repair Batch"

    name = fields.Char()
    partner_id = fields.Many2one("res.partner")

    sale_id = fields.Many2one("sale.order")
    invoice_id = fields.Many2one("account.move", string="Invoice")

    state = fields.Selection(
        [
            ("draft", "Waiting"),
            ("ready", "Ready"),
            ("in_progress", "In Repair"),
            ("done", "Done"),
            ("to_approve","Waiting Approval"),
        ],
        default="draft",
    )
    
    received = fields.Boolean(default=False)

    total_cost = fields.Float(string="Total Cost",compute="_compute_cost", store=True)

    sale_amount = fields.Float(string="Sale Amount", compute="_compute_cost",store=True)

    profit = fields.Float(string="Profit", compute="_compute_cost",store=True)

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

    @api.depends(
        "trolley_ids.work_line_ids.product_id",
        "trolley_ids.work_line_ids.quantity",
        "sale_id.amount_total"
    )
    def _compute_cost(self):
        for batch in self:
            total = 0 

            for trolley in batch.trolley_ids:
                for line in trolley.work_line_ids:
                    if line.product_id:
                        total += line.product_id.standard_price * line.quantity
            
            batch.total_cost = total 
            batch.sale_amount = batch.sale_id.amount_total if batch.sale_id else 0 
            batch.profit = batch.sale_amount - batch.total_cost 
            

    def _check_approval_rule(self):
        self.ensure_one()

        amount = self.sale_id.amount_total if self.sale_id else 0

        rule = self.env["approval.rule"].search([
            ("model", "=", "repair.batch"),
            ("min_amount", "<=", amount),
        ], order="min_amount desc", limit=1)

        return rule

    def action_approve(self):
        for rec in self:
            rec.state = "in_progress"
            rec.action_done()

    def action_reject(self):
        for rec in self:
            rec.state = "cancel"


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

            # Already created hai to dobara mat bana
            if not rec.trolley_ids:

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
                            current_trolley = self.env['repair.trolley'].create({
                                'name': 'General',
                                'batch_id': rec.id,
                            })

                        self.env['repair.work.line'].create({
                            'trolley_id': current_trolley.id,
                            'product_id': line.product_id.id,
                            'quantity': line.product_uom_qty,
                        })

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

            # ================== 🔥 APPROVAL CHECK (NEW) ==================

            rule = batch._check_approval_rule()
            if rule:
                batch.state = "to_approve"
                continue

            # ================== 🔒 VALIDATION FIRST ==================

            if not batch.trolley_ids:
                raise ValidationError("No trolleys found")

            if any(t.state != "done" for t in batch.trolley_ids):
                raise ValidationError("Complete all trolleys")

            for trolley in batch.trolley_ids:
                if not trolley.work_line_ids:
                    raise ValidationError("Trolley has no products")

                if any(line.quantity <= 0 for line in trolley.work_line_ids):
                    raise ValidationError("Quantity must be greater than zero")

            # 🔒 DUPLICATE STOCK PROTECTION
            if batch.consumption_picking_id:
                raise ValidationError("Stock already consumed for this batch")

            # ================== 🔥 STOCK FLOW ==================

            origin = f"{batch.name} - repair"

            picking_type = self.env["stock.picking.type"].search(
                [("code", "=", "internal")], limit=1
            )

            picking = self.env["stock.picking"].create({
                "picking_type_id": picking_type.id,
                "location_id": batch.source_location_id.id,
                "location_dest_id": batch.consumption_location_id.id,
                "origin": origin,
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
                        "origin": origin,
                    })
                    moves |= move

            if not moves:
                raise ValidationError("No valid products to consume")

            moves._action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                for ml in move.move_line_ids:
                    ml.quantity = move.product_uom_qty
                    ml.picked = True

            picking.button_validate()

            # ================== 🔥 FINAL STATE ==================

            batch.consumption_picking_id = picking
            batch.state = "done"

            # ================== 🔥 INVOICE LOGIC ==================

            sale = batch.sale_id

            if sale:
                if sale.invoice_ids:
                    batch.invoice_id = sale.invoice_ids[0].id
                else:
                    invoices = sale._create_invoices()
                    if invoices:
                        for inv in invoices:
                            inv.action_post()
                        batch.invoice_id = invoices[0].id

                sale.invalidate_recordset()


    def action_view_invoice(self):
        self.ensure_one()

        if not self.invoice_id:
            raise ValidationError("No Invoice found")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
        }