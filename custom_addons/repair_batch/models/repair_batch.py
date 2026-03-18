from odoo import models, fields, api


class RepairBatch(models.Model):
    _name = 'repair.batch'
    _description = 'Repair Batch'

    name = fields.Char(string="Reference")
    partner_id = fields.Many2one('res.partner', string="Customer")
    sale_order_id = fields.Many2one('sale.order', string="Sales Order")

    state = fields.Selection([
        ('draft', 'Waiting for Material'),
        ('ready', 'Ready for Repair'),
        ('in_progress', 'In Repair'),
        ('done', 'Done'),
    ], default='draft')

    received = fields.Boolean(default=False)

    trolley_ids = fields.One2many('repair.trolley', 'batch_id', string="Trolleys")

    # Buttons
    def action_receive(self):
        for rec in self:
            rec.received = True
            rec.state = 'ready'

    def action_start_repair(self):
        for rec in self:
            if not rec.received:
                raise Exception("Trolley not received yet!")
            rec.state = 'in_progress'

    def action_done(self):
        for rec in self:
            rec.state = 'done'


# NEW MODEL (Trolley)
class RepairTrolley(models.Model):
    _name = 'repair.trolley'
    _description = 'Repair Trolley'

    name = fields.Char(string="Trolley Name")
    batch_id = fields.Many2one('repair.batch')

    work_line_ids = fields.One2many(
        'repair.work.line',
        'trolley_id',
        string="Work Lines"
    )

  
    is_done = fields.Boolean(string="Done")

    # 🔹 Trolley → Work lines sync
    @api.onchange('is_done')
    def _onchange_trolley_done(self):
        for rec in self:
            for line in rec.work_line_ids:
                line.is_done = rec.is_done

    # 🔹 Work lines → Trolley sync
    @api.onchange('work_line_ids')
    def _onchange_work_lines(self):
        for rec in self:
            if rec.work_line_ids:
                rec.is_done = all(line.is_done for line in rec.work_line_ids)
            else:
                rec.is_done = False

    def open_trolley(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'repair.trolley',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
#  NEW MODEL (Work Lines)
class RepairWorkLine(models.Model):
    _name = 'repair.work.line'
    _description = 'Repair Work Line'

    trolley_id = fields.Many2one('repair.trolley')

    name = fields.Char(string="Work")

    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
    ], default='pending')

    is_done = fields.Boolean(string="Done")

    # 🔹 Checkbox → state sync
    @api.onchange('is_done')
    def _onchange_is_done(self):
        for rec in self:
            rec.state = 'done' if rec.is_done else 'pending'
   