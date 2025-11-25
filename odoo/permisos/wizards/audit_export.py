# permisos/wizard/audit_export.py
# -*- coding: utf-8 -*-
import io
import xlsxwriter
import base64
from odoo import models, fields

class PermAuditExportWiz(models.TransientModel):
    _name = 'permisos.audit.export.wiz'
    _description = 'Export de auditoría a XLSX'

    file_data = fields.Binary('Archivo', readonly=True)
    file_name = fields.Char('Nombre', default='auditoria_seguridad.xlsx')

    def action_export(self):
        logs = self.env['permisos.audit.log'].sudo().search([], limit=5000, order='id desc')
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('audit')

        headers = ['Fecha/hora','Usuario','Acción','Modelo','ID','Valores antes','Valores después','Origen']
        for col, h in enumerate(headers):
            ws.write(0, col, h)
        row = 1
        for l in logs:
            ws.write(row, 0, str(l.when or ''))
            ws.write(row, 1, l.user_id.display_name or '')
            ws.write(row, 2, l.action or '')
            ws.write(row, 3, l.model or '')
            ws.write(row, 4, l.res_id or 0)
            ws.write(row, 5, l.vals_before or '')
            ws.write(row, 6, l.vals_after or '')
            ws.write(row, 7, l.origin or '')
            row += 1
        wb.close()
        output.seek(0)
        file_content = output.read()

        # Odoo espera base64 en campos Binary
        self.write({
            'file_data': base64.b64encode(file_content),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{self._name}/{self.id}/file_data/{self.file_name}?download=1",
            'target': 'self',
        }
