from odoo import models, fields, api
from odoo.fields import Date
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = ["res.partner", "mail.thread", "mail.activity.mixin"]

    followup_date = fields.Date(string="Follow-up Date")
    followup_note = fields.Text(string="Follow-up Note")
    is_followup_done = fields.Boolean(string="Done", default=False)

    # Dashboard fields
    today_total = fields.Integer(compute="_compute_followup_stats")
    today_done = fields.Integer(compute="_compute_followup_stats")
    today_pending = fields.Integer(compute="_compute_followup_stats")

    @api.depends("followup_date", "is_followup_done")
    def _compute_followup_stats(self):
        today = Date.today()

        total = self.search_count([("followup_date", "=", today)])

        done = self.search_count(
            [("followup_date", "=", today), ("is_followup_done", "=", True)]
        )

        for rec in self:
            rec.today_total = total
            rec.today_done = done
            rec.today_pending = total - done

    def _check_followups(self):
        """Cron: Create follow-up notifications (chatter + bell, no email)

        NOTE: Allows duplicate notifications for testing purposes.
        Each cron run will send new notifications to eligible partners.
        """

        today = Date.today()

        partners = self.search(
            [
                ("followup_date", "!=", False),
                ("followup_date", "<=", today),
                ("is_followup_done", "=", False),
            ]
        )

        for partner in partners:
            try:
                self._send_followup_notification(partner, today)
            except Exception as e:
                _logger.exception(f"Follow-up error for {partner.id}: {str(e)}")

    def _send_followup_notification(self, partner, today):
        """Send chatter + bell notification"""

        user = self._get_followup_user(partner)
        if not user:
            _logger.warning(f"No user for partner {partner.name}")
            return

        # Ensure user is follower (important for notifications)
        partner.message_subscribe([user.partner_id.id])

        # Post message and get the message object
        message = partner.with_context(
            mail_notify_force_send=False,  # Don't send emails
            mail_auto_delete=False,  # Keep message
            mail_notify_user_signature=False,
        ).message_post(
            body=Markup(self._build_message(partner, today)),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            partner_ids=[user.partner_id.id],
        )

        # Manually create notification to ensure bell icon appears
        if message and user:
            self.env["mail.notification"].create(
                {
                    "mail_message_id": message.id,
                    "res_partner_id": user.partner_id.id,
                    "notification_type": "inbox",
                    "notification_status": "ready",
                }
            )

        _logger.info(f"Notification sent to {user.name} for partner {partner.name}")

    def _get_followup_user(self, partner):
        """Get responsible user"""

        if partner.user_id:
            return partner.user_id

        if hasattr(partner, "team_id") and partner.team_id and partner.team_id.user_id:
            return partner.team_id.user_id

        return self.env.user

    def _build_message(self, partner, today):
        """Generate clean HTML message"""

        date_str = today.strftime("%d %B %Y")
        name = partner.display_name or partner.name

        note = partner.followup_note or "Follow-up required"

        return f"""
        <div style="background:#f8f9fa;padding:12px;border-left:4px solid #007bff;">
            <b>Follow-up Reminder</b><br/>
            <b>Partner:</b> {name}<br/>
            <b>Date:</b> {date_str}<br/>
            <b>Note:</b> {note}
        </div>
        """

    today_followup_count = fields.Integer(compute="_compute_today_followup")

    def _compute_today_followup(self):
        today = fields.Date.today()
        count = self.search_count(
            [("followup_date", "=", today), ("is_followup_done", "=", False)]
        )
        for rec in self:
            rec.today_followup_count = count
