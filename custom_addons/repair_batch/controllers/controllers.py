# from odoo import http


# class RepairBatch(http.Controller):
#     @http.route('/repair_batch/repair_batch', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/repair_batch/repair_batch/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('repair_batch.listing', {
#             'root': '/repair_batch/repair_batch',
#             'objects': http.request.env['repair_batch.repair_batch'].search([]),
#         })

#     @http.route('/repair_batch/repair_batch/objects/<model("repair_batch.repair_batch"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('repair_batch.object', {
#             'object': obj
#         })

