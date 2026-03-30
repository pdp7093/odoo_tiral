from odoo import models,fields  

class ApprovalRule(models.Model):
    _name = 'approval.rule'
    _description = 'Approval Rule'

    name = fields.Char(required=True)

    model = fields.Selection([ 
        ('sale.order', 'Sales Order'),
        ('purchase.order', 'Purchase Order'),
        ('repair.batch', 'Repair Batch'),
    ], required=True)

    min_amount = fields.Float(string='Minimum Amount', default=0.0) 

    group_id = fields.Many2one('res.groups', string='Approver Group', required=True)


