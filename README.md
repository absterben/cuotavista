# Cuotavista

Herramienta web open source para analizar estados de cuenta de tarjetas de crédito uruguayas. Particularmente, ahora funciona con BROU (tarjeta BROU Recompensa) e Itaú (Volar)

## ¿Qué problema resuelve?

Cuando tenés compras en cuotas repartidas en varios meses, es difícil saber:
- Cuántas cuotas activas tenés
- Cuánto dinero se te libera cada mes cuando vencen
- Qué porcentaje de tu estado de cuenta son cuotas vs. consumos corrientes

Cuotavista toma tu estado de cuenta y te muestra un resumen de tus cuotas activas y una proyección de cuánto vas a pagar mes a mes.

## Bancos soportados

| Banco | Formato de archivo |
|-------|-------------------|
| BROU | Excel (.xls) |
| Itaú | PDF |

## Flujo de uso

1. Descargá el estado de cuenta desde tu homebanking
2. Entrá a Cuotavista y elegí tu banco
3. Subí el archivo
4. Revisá el resumen de cuotas
5. (Opcional) Descargá el Excel con los detalles

## Privacidad y manejo de datos

**Los archivos que subís nunca se guardan.**

- Se procesan en memoria del servidor
- Se eliminan inmediatamente después de generar el resultado
- No hay base de datos ni almacenamiento de información personal

**Este proyecto no tiene ningún fin comercial.**

## Cómo correr localmente

### Requisitos
- Python 3.11+
- pip

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/cuotavista.git
cd cuotavista

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python app.py
```

## Estado del proyecto

🚧 **Experimental**

Este es un proyecto personal en desarrollo. Funciona, pero puede tener bugs. Si encontrás algún problema, podés reportarlo en los issues del repositorio.

## Contribuir

Las contribuciones son bienvenidas. Si querés colaborar:

1. Hacé un fork del proyecto
2. Creá una rama para tu feature (`git checkout -b feature/mi-mejora`)
3. Commiteá tus cambios (`git commit -m 'Agrega mi mejora'`)
4. Pusheá a la rama (`git push origin feature/mi-mejora`)
5. Abrí un Pull Request

## Contacto

cuotavista@gmail.com
