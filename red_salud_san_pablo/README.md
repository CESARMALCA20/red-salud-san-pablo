# Red de Salud San Pablo · Plataforma Analítica

## Estructura
```
├── Portada.py          # Servidor Flask principal
├── portada.html        # Diseño de la portada
├── requirements.txt    # Dependencias Python
├── render.yaml         # Configuración Render.com
├── data/               # Aquí va el reporte.parquet
└── pages/              # Tableros Streamlit
    ├── app.py
    ├── 1_Periodo_Prenatal.py
    ├── 2_Nino.py
    ├── 3_Adolescente.py
    ├── 4_Joven.py
    ├── 5_Adulto.py
    └── 6_Adulto_Mayor.py
```

## Credenciales
- admin / sanpablo2026
- cesar / salud2026

## Ejecutar local
```bash
pip install -r requirements.txt
python Portada.py
```
