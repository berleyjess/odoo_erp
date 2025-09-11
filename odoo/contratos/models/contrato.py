from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

import logging
_logger = logging.getLogger(__name__)

class contrato(models.Model):
    _name='contratos.contrato'
    _description='Contratos agrícolas a clientes'
    _rec_name = 'display_name'

    tipocredito = fields.Selection(
        selection = [
            ('0', "AVIO"),
            ('1', "Parcial"),
            ('2', "Especial")
        ], string = "Tipo de crédito", default = "0", required = True
    )
    ciclo = fields.Many2one('ciclos.ciclo', string="Ciclo", required=True)    
    cultivo = fields.Many2one('cultivos.cultivo', string="Cultivo")
    aporte = fields.Integer(string="Aporte por Hectárea")
    
    limiteinsumos = fields.One2many(
        'contratos.limiteinsumo_ext', 'contrato_id', string="Límites de Insumos")
    
    display_name = fields.Char(compute='_compute_display_name', store=True, string="Contrato")

    cargos = fields.One2many('cargosdetail.cargodetail', 'contrato_id', string = "Cargos")
    #creditos = fields.One2many('creditos.credito', 'contrato', string = "Créditos asociados")

    def write(self, vals):
        # Guardar los créditos relacionados antes de hacer el write
        _logger.info("*-*-*-*-*-* EH, WE, SI ENTRA EN WRITE *-*-*-*-*-*")
        creditos_afectados = self.env['creditos.credito']
        if 'cargos' in vals:
            creditos_afectados = self.env['creditos.credito'].search([
                ('contrato', 'in', self.ids)
            ])
        
        result = super().write(vals)
        
        # Ejecutar sincronización después del write
        if creditos_afectados:
            _logger.info("*-*-*-*-*-* EH, WE, SI ENTRA EN WRITE PERO EN LOS CREDITOS *-*-*-*-*-*")
            creditos_afectados._gen_cargosbycontrato()
        
        return result
    
    @api.onchange('tipocredito')
    def _cambiotipo(self):
        self.cultivo = False

    @api.depends('ciclo', 'cultivo', 'tipocredito')
    def _compute_display_name(self):
        for record in self:
            tipocredito_label = dict(self._fields['tipocredito'].selection).get(record.tipocredito) or ""
            label_cultivo = record.cultivo.nombre or ""
            label_ciclo = record.ciclo.label or ""

            record.display_name = f"{tipocredito_label} {label_ciclo} {label_cultivo}"

    _sql_constraints = [
        ('unique_display_name', 'unique(display_name)', 'Ya existe un Contrato con el mismo <<Tipo de Crédito>> y el mismo <<Ciclo>>.')
    ]

