# -*- coding: utf-8 -*-
"""
Modelo: clientes.cliente
Descripción: Administra la cartera de clientes para el módulo de Crédito.
Incluye datos fiscales, de identificación (INE, CURP), domicilio, estado civil y contactos
relacionados. Implementa lógica para:
- Autogenerar un código interno incremental.
- Forzar mayúsculas al crear/editar.
- Ajustar dinámicamente el dominio del régimen fiscal según el tipo de cliente.
- Limpiar el nombre del cónyuge cuando el estado civil no lo requiere.
"""

from odoo import models, fields, api

class cliente(models.Model):
    """
    Modelo principal de cliente.

    Notas:
    - El nombre técnico del modelo es `clientes.cliente`.
    - Utiliza una secuencia `seq_client_code` para generar el campo `codigo`.
    - Implementa `@api.onchange` para actualizar dominios y limpiar campos en la vista.
    - Sobrescribe `create` y `write` para normalizar datos a mayúsculas.
    """
    
    _name='clientes.cliente'  #Modelo.Cliente ("nombre del modulo"."nombre del modelo")
    _description='Cartera de clientes'
    
    codigo = fields.Char( #Código interno del Cliente
        string='Código',
        size=10,
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_code(),
        help="Código interno autogenerado (ej. 000001). Controlado por la secuencia 'seq_client_code'."
    )

    nombre = fields.Char(string="Nombre/Razón social", required=True,help="Nombre completo o razón social del cliente.")

    rfc = fields.Char(string="RFC",size=13, required=True, help="Registro Federal de Contribuyentes")

    tipo = fields.Selection(
        selection = [
            ("0", "Persona Física"),
            ("1", "Persona Moral")
        ], string="Tipo de Cliente", required=True, default = "0",
        help="Define si el cliente es Persona Física o Persona Moral. Afecta el dominio del campo Régimen Fiscal."
    )

    regimen = fields.Many2one('clientes.c_regimenfiscal',
                              string = "Régimen Fiscal",
                              domain="[('tipo', 'in', [tipo == '0' and '0' or '1', '2'])]",
                              help="Régimen fiscal del cliente. El dominio se recalcula dinámicamente en _onchange_tipo."
    )

    # Campos de identificación / Estado civil
    ine = fields.Char(string="INE (Clave de Lector)", size=18, help="Ingrese solo la clave de lector del INE")
    curp = fields.Char(string="CURP", size=18, help="Clave Única de Registro de Población")
    estado_civil = fields.Selection([
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
        ('union_libre', 'Unión Libre')
    ], string="Estado Civil",
        help="Estado civil del cliente. "
    )
    
    conyugue = fields.Char(string="Nombre del Cónyuge", size=100, help="Nombre completo del cónyuge")

    codigop = fields.Char(string="Código Postal", size=5)
    localidad = fields.Many2one('localidades.localidad', string = "Ciudad/Localidad",help="Ciudad o localidad del domicilio del cliente")
    colonia = fields.Char(string = "Colonia", size = 32)
    calle = fields.Char(string = "Calle", size = 32)
    numero = fields.Char(string = "Número", size = 4)

    #Relación con contactos



    contacto = fields.One2many('clientes.contacto_ext', 'cliente_id', string = "Contactos",help="Contactos externos relacionados con este cliente.")

    # ONCHAGE METHODS

    """
        Actualiza el dominio del campo 'regimen' dependiendo del tipo de cliente.
        Además, muestra una advertencia si hay RFC capturado para que se valide
        coherencia con el tipo seleccionado.

        Retorna:
            dict: dominio dinámico para el campo 'regimen' y un warning opcional.
    """

    @api.onchange('tipo')
    def _onchange_tipo(self):
        """Actualiza dominio del campo regimen fiscal dinámicamente"""
        if not self.tipo:
            # Resetear el campo si tipo está vacío
            self.regimen = False
            return {'domain': {'regimen': []}}
        
        # Definir dominio basado en el tipo seleccionado
        domain_map = {
            '0': ['0', '2'],  # Persona Física
            '1': ['1', '2']   # Persona Moral
        }
        return {
            'domain': {
                'regimen': [('tipo', 'in', domain_map.get(self.tipo, []))]
            },
            'warning': {
                'title': "Cambio de Régimen Fiscal",
                'message': "Verifique que el RFC coincida con el tipo seleccionado"
            } if self.rfc else None
        }

    @api.onchange('estado_civil')
    def _onchange_estado_civil(self):
        """Limpia el campo cónyuge si no está casado o en unión libre"""
        if self.estado_civil not in ['casado', 'union_libre']:
            self.conyugue = False
    
    # Logica de negocio / hooks.

    def _generate_code(self):
        """
        Genera el código interno del cliente utilizando la secuencia 'seq_client_code'.
        Formatea el número a 6 dígitos con ceros a la izquierda.

        Returns:
            str: Código formateado, ej. '000001'
        """
        sequence = self.env['ir.sequence'].next_by_code('seq_client_code') or '/'
        number = sequence.split('/')[-1]
        return f"{number.zfill(6)}"
    
    @api.model
    def create(self, vals):
        """
        Sobrescribe create para:
        - Forzar a mayúsculas los campos de texto relevantes antes de crear el registro.

        Args:
            vals (dict): Valores a crear.

        Returns:
            recordset: Registro creado.
        """
        # Convertir a mayúsculas antes de crear
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        if 'ine' in vals:
            vals['ine'] = vals['ine'].upper() if vals['ine'] else False
        if 'curp' in vals:
            vals['curp'] = vals['curp'].upper() if vals['curp'] else False
        if 'conyugue' in vals:
            vals['conyugue'] = vals['conyugue'].upper() if vals['conyugue'] else False
        return super().create(vals)

    def write(self, vals):
        """
        Sobrescribe write para:
        - Forzar a mayúsculas los campos de texto relevantes antes de actualizar el registro.

        Args:
            vals (dict): Valores a escribir.

        Returns:
            bool: True si la operación fue exitosa.
        """
        # Convertir a mayúsculas antes de actualizar
        if 'nombre' in vals:
            vals['nombre'] = vals['nombre'].upper() if vals['nombre'] else False
        if 'rfc' in vals:
            vals['rfc'] = vals['rfc'].upper() if vals['rfc'] else False
        if 'ine' in vals:
            vals['ine'] = vals['ine'].upper() if vals['ine'] else False
        if 'curp' in vals:
            vals['curp'] = vals['curp'].upper() if vals['curp'] else False
        if 'conyugue' in vals:
            vals['conyugue'] = vals['conyugue'].upper() if vals['conyugue'] else False
        return super().write(vals)

    def action_save(self):
        """
        Acción para guardar y volver a la vista de lista.
        Útil si pones un botón 'Guardar' manual en la vista.
        """
        self.ensure_one()
        
        # Retornar a la vista lista
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clientes',
            'res_model': 'clientes.cliente',
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    def action_cancel(self):
        """
        Acción para cancelar y regresar a la vista lista sin guardar cambios (la
        cancelación real depende de si el registro estaba en edición o no).
        """
        # Retornar a la vista lista sin guardar
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clientes',
            'res_model': 'clientes.cliente', 
            'view_mode': 'list,form',
            'target': 'current',
        }