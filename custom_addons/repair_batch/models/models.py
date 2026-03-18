# from odoo import models, fields, api


# class repair_batch(models.Model):
#     _name = 'repair_batch.repair_batch'
#     _description = 'repair_batch.repair_batch'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

