"""
Utilidades para el módulo Santander.
Re-exporta funciones comunes desde utils_comunes.
"""
from bancos.utils_comunes import es_cuota, numero_cuotas, calculo_totales

__all__ = ['es_cuota', 'numero_cuotas', 'calculo_totales']
