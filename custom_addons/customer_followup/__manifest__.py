{
    'name':'Customer Follow-up',
    'version':'1.0',
    'depends':['base','contacts'],
    'data':[
        'views/followup_views.xml',
        'views/partner_view.xml',
        
        'data/cron.xml',
    ],
    'installable':True,
    'application':True,

}