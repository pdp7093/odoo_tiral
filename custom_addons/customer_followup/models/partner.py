from odoo import models, fields
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    followup_date = fields.Date(string="Follow-up Date")
    followup_note = fields.Text(string="Follow-up Note")
    is_followup_done = fields.Boolean(string="Done", default=False)
    
    def _check_followups(self):
        today = date.today()

        partners = self.search(
            [
                ("followup_date", "!=", False),
                ("followup_date", "<=", today),
                ("is_followup_done", "=", False),
            ]
        )

        activity_type = self.env.ref("mail.mail_activity_data_todo")

        for partner in partners:
            existing_activity = self.env["mail.activity"].search(
                [
                    ("res_model", "=", "res.partner"),
                    ("res_id", "=", partner.id),
                    ("activity_type_id", "=", activity_type.id),
                ],
                limit=1,
            )

            if existing_activity:
                continue

            self.env["mail.activity"].create(
                {
                    "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                    "res_id": partner.id,
                    "activity_type_id": activity_type.id,
                    "summary": "Follow-up Reminder",
                    "note": partner.followup_note or "Follow-up required",
                    "date_deadline": today,
                    "user_id": partner.user_id.id or self.env.ref("base.user_admin").id,
                }
            )

            partner.with_context(mail_notify_force_send=False).message_post(
                body="Follow-up Reminder",
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
                partner_ids=[partner.user_id.partner_id.id],
            )

    