{
    "name": "Customer Follow-up",
    "version": "1.0",
    "depends": ["base", "contacts", "mail"],
    "data": [
        "views/followup_views.xml",
        "views/partner_view.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": True,
    "assets": {
        "web.assets_backend": [
            "customer_followup/static/src/js/followup_dashboard.js",
        ],
        "web.assets_qweb": [
            "customer_followup/static/src/xml/followup_dashboard.xml",
            "customer_followup/static/src/xml/control_panel_extend.xml",
        ],
    },
}
