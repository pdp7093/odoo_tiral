from odoo import models, fields
from odoo.exceptions import UserError


class SalesOrder(models.Model):
    _inherit = "sale.order"

    state = fields.Selection(
        selection_add=[
            ('waiting_approval', 'Waiting Approval'),
            ('waiting_credit_approval','Waiting Credit Approval')
            ],
        tracking=True
    )

    def action_confirm(self):

        for order in self:
            partner = order.partner_id

            credit_limit = partner.customer_credit_limit
            current_due = partner.credit

            # Credit limit check
            if credit_limit and (current_due + order.amount_total) > credit_limit:

                order.state = 'waiting_credit_approval'

                # Sales Manager Group
                # Sales Manager Group
                manager_group = self.env.ref('sales_team.group_sale_manager')
                manager = manager_group.user_ids[:1]

                order.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=manager.id,
                    note=f"Customer {partner.name} exceeded credit limit. Please review the order."
                )
                # raise UserError("Customer credit limit exceeded.")
                return True

            # Margin approval check
            if order.margin_percent < 10:
                order.state = 'waiting_approval'
                return True

        return super().action_confirm()

    def action_manager_approve(self):
        for order in self:
            if order.state == 'waiting_approval':
                order.state = 'draft'

        return super().action_confirm()

    